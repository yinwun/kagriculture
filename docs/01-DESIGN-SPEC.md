# Kagriculture RL — 设计规范

> **Version**: 0.1
> **Date**: 2026-08-09
> **Goal**: 用 RL 训练 Kagriculture agent，目标进入 top 5

---

## 1. 目标与约束

### 1.1 最终目标

- 训练一个 RL agent，能在 Kagriculture 中打败大多数对手
- 目标：进入 Kaggle LB top 5
- 参考：Orbit Wars 1st place 用 200M 参数 transformer + 15B steps RL

### 1.2 硬件约束

| 资源 | 规格 |
|------|------|
| **训练服务器** | RTX 5090 (用户自有) |
| **开发服务器** | 2x V100 16GB (nlv100@192.168.1.101) |
| **Kaggle submit 限制** | ~1 秒/步推理时间 |

### 1.3 时间约束

- Phase 1 (验证): 1-2 周
- Phase 2 (扩展): 2-4 周  
- Phase 3 (优化): 2-4 周

---

## 2. 算法选型

### 2.1 候选算法对比

| 算法 | 优点 | 缺点 | 推荐度 |
|------|------|------|--------|
| **PPO** | 稳定、sample efficient | 稍慢 | ⭐⭐⭐⭐⭐ |
| **IMPALA** | 高吞吐、易扩展 | 需要分布式 | ⭐⭐⭐⭐ |
| **SAC** | 连续动作友好 | 离散动作稍慢 | ⭐⭐⭐ |
| **DQN** | 简单 | 离散动作、不稳定 | ⭐⭐ |

### 2.2 推荐：PPO + Stable Baselines3

**理由：**
1. **稳定** — PPO 是最稳定的 Policy Gradient 算法
2. **成熟** — SB3 实现完善，debug 工具全
3. **足够快** — 适合 10M-500M steps 的训练规模
4. **易扩展** — 以后可以迁移到 IMPALA 如果需要

### 2.3 算法参数 (初始配置)

```python
ppo_config = {
    "learning_rate": 3e-4,
    "n_steps": 2048,           # 每个 env 收集的 steps
    "batch_size": 64,
    "n_epochs": 10,
    "gamma": 0.99,              # discount factor
    "gae_lambda": 0.95,         # GAE lambda
    "clip_range": 0.2,         # PPO clipping
    "ent_coef": 0.01,          # entropy coefficient (鼓励探索)
    "vf_coef": 0.5,            # value function coefficient
}
```

### 2.4 备选：IMPALA (如果 PPO 不够快)

如果 PPO 在 RTX 5090 上只能达到 ~1000 steps/s，考虑迁移到 IMPALA：
- 分布式 rollout (多个 CPU actor)
- GPU learner
- 目标：10,000+ steps/s

---

## 3. Observation Space 设计

### 3.1 完整 Observation (Phase 3)

```python
class KagricultureObs:
    # === 全局状态 ===
    step: int           # 0-719
    day: int            # 0-29
    money: float        # 当前金钱
    
    # === Farm 状态 (10x10 grid) ===
    tiles: np.array    # shape (10, 10, 4)
                        # [row, col, channel]
                        # channel 0: tile_type (0=empty, 1=crop, 2=animal)
                        # channel 1: crop_type / animal_type
                        # channel 2: planted_day / animal_yield
                        # channel 3: state (growing/ready/empty)
    
    # === Market 状态 ===
    market_prices: dict        # {item: price}
    market_inventory: dict      # {item: quantity}
    
    # === 私有状态 (自己) ===
    private_shed: dict          # {item: quantity}
    private_hands: int         # 当前 hired hands
    private_hires_left: int    # 今天还能 hire 几次
    
    # === 对手可见状态 (从 public tiles) ===
    opponent_tiles: np.array    # 对手的 public tiles
    
    # === 汇总统计 ===
    summary: {
        "plantable_tiles": int,
        "at_risk_animals": int,
        "unfed_animals": int,
        "crops_ready": int,
        "weed_density": float,
    }
```

**总维度估算**：~500-1000 floats

### 3.2 简化 Observation (Phase 1-2)

```python
class SimplifiedObs:
    """Phase 1-2 使用的简化版本"""
    step: int           # 0-719
    day: int            # 0-29
    money: float        # 当前金钱
    
    # Market (最重要)
    wheat_price: float
    wheat_inventory: int
    wheat_market_inv: int
    
    melon_price: float
    strawberry_price: float
    fertilizer_price: float
    
    # Farm 汇总
    total_plants: int
    plants_ready: int
    plantable_tiles: int
    
    # Animals
    cow_count: int
    sheep_count: int
    unfed_animals: int
    
    # Hands
    hands: int
    
    # 对手估算 (从 visible tiles)
    opponent_money_est: float  # 从对手 farm size 估算
```

**总维度估算**：~30-50 floats

### 3.3 Observation 处理

```python
class ObsProcessor:
    """处理 raw observation 到 neural network 输入"""
    
    def __init__(self):
        self.net = nn.Sequential(
            nn.Linear(input_dim, 256),
            nn.ReLU(),
            nn.Linear(256, 128),
            nn.ReLU(),
        )
    
    def forward(self, obs: dict) -> torch.Tensor:
        # 1. 归一化数值
        normalized = {
            "step": obs["step"] / 720.0,
            "day": obs["day"] / 30.0,
            "money": obs["money"] / 100000.0,  # 假设最大 100k
            ...
        }
        
        # 2. concatenate
        x = torch.cat([torch.tensor(v) for v in normalized.values()])
        
        # 3. MLP encode
        return self.net(x)
```

---

## 4. Action Space 设计

### 4.1 Phase 1: WHEAT-only (3 actions)

```python
class WheatOnlyAction:
    """最简化的 WHEAT 交易"""
    HOLD = 0           # 什么都不做
    BUY_WHEAT = 1      # 买入小麦
    SELL_WHEAT = 2     # 卖出小麦
```

**理由**：
- WHEAT 是最核心的交易品
- 简化后 RL 更容易学到
- 可以验证 RL 框架是否 work

### 4.2 Phase 2: Market Actions (7 actions)

```python
class MarketAction:
    HOLD = 0
    
    # WHEAT
    BUY_WHEAT = 1
    SELL_WHEAT = 2
    
    # Crops
    BUY_MELON = 3
    SELL_MELON = 4
    BUY_STRAWBERRY = 5
    SELL_STRAWBERRY = 6
```

### 4.3 Phase 3: Full Actions (15-20 actions)

```python
class FullAction:
    # === Market (8 actions) ===
    HOLD = 0
    
    BUY_WHEAT = 1
    SELL_WHEAT = 2
    BUY_MELON = 3
    SELL_MELON = 4
    BUY_STRAWBERRY = 5
    SELL_STRAWBERRY = 6
    BUY_FERTILIZER = 7
    SELL_FERTILIZER = 8
    
    # === Field (5 actions) ===
    PLANT_MELON = 9
    PLANT_STRAWBERRY = 10
    PLANT_CARROT = 11
    PLANT_TOMATO = 12
    HARVEST_ALL = 13
    
    # === Animals (2 actions) ===
    BUY_ANIMAL = 14    # 自动选择 COW 或 SHEEP
    FEED = 15
    
    # === Hiring (1 action) ===
    HIRE = 16
```

### 4.4 Multi-Head Action (推荐)

为了处理不同类型的 action，使用 **multi-head output**：

```python
class MultiHeadPolicy(nn.Module):
    """每个 head 负责一个 action category"""
    
    def __init__(self, obs_dim, action_dims):
        super().__init__()
        
        # 共享 encoder
        self.encoder = nn.Sequential(
            nn.Linear(obs_dim, 256),
            nn.ReLU(),
        )
        
        # 每个 category 一个 head
        self.heads = nn.ModuleDict({
            "market": nn.Linear(256, action_dims["market"]),
            "field": nn.Linear(256, action_dims["field"]),
            "animal": nn.Linear(256, action_dims["animal"]),
            "hiring": nn.Linear(256, action_dims["hiring"]),
        })
    
    def forward(self, obs):
        encoded = self.encoder(obs)
        return {name: head(encoded) for name, head in self.heads.items()}
```

**最终 action 是所有 heads 的组合**：
```python
action = {
    "market": categorical_sample(market_logits),   # e.g., BUY_WHEAT
    "field": categorical_sample(field_logits),    # e.g., PLANT_MELON
    "animal": categorical_sample(animal_logits), # e.g., FEED
    "hiring": categorical_sample(hiring_logits), # e.g., HIRE
}
```

---

## 5. Reward 设计

### 5.1 Phase 1: Terminal Reward (最简单)

```python
def compute_reward(obs, action, next_obs, done):
    """只用最终金钱作为 reward"""
    if done:
        return next_obs["money"]  # 或 next_obs["money"] / 1000.0 归一化
    return 0
```

**问题**：信号非常稀疏（只在 episode 结束时）

### 5.2 Phase 2: Dense Reward (改进版)

```python
def compute_reward(obs, action, next_obs, done):
    """每步 dense reward"""
    
    # 1. 主要信号：金钱变化
    money_delta = next_obs["money"] - obs["money"]
    
    # 2. 可选：辅助信号
    harvest_bonus = 0
    if obs.get("plants_ready", 0) > 0:
        harvest_bonus = 10  # 有可收获的作物但没收，惩罚
    
    death_penalty = 0
    if next_obs.get("animals_died", 0) > 0:
        death_penalty = -50 * next_obs["animals_died"]
    
    # 3. 终局额外奖励
    terminal_bonus = 0
    if done:
        # 根据最终排名给 bonus
        final_money = next_obs["money"]
        if final_money > baseline:
            terminal_bonus = (final_money - baseline) / 1000.0
    
    return money_delta + harvest_bonus + death_penalty + terminal_bonus
```

### 5.3 Phase 3: Self-Play Reward

```python
def compute_bt_reward(episode_result):
    """用 Bradley-Terry 估计的 win probability 作为 reward"""
    # 需要对战多个对手，计算胜率
    pass
```

---

## 6. 训练流程

### 6.1 Phase 1: 环境验证

```python
# 测试环境能正常运行
from kg_rl.envs import KagricultureEnv

env = KagricultureEnv()
obs = env.reset()

for _ in range(720):
    action = env.action_space.sample()  # 随机
    obs, reward, done, info = env.step(action)
    if done:
        obs = env.reset()

print("环境正常运行")
```

### 6.2 Phase 2: RL 训练循环

```python
from kg_rl.envs import KagricultureEnv
from kg_rl.models import MultiHeadPolicy
from kg_rl.algos import PPOAgent

# 1. 创建环境
env = KagricultureEnv()

# 2. 创建 agent
agent = PPOAgent(
    policy=MultiHeadPolicy,
    env=env,
    config=ppo_config,
)

# 3. 训练
agent.learn(total_timesteps=10_000_000)

# 4. 保存
agent.save("/data/app/sandbox/kaggle/kg-rl/models/ppo_wheat_v1")
```

### 6.3 评估流程

```python
from kg_rl.eval import evaluate_agent

# 对战多个 baseline
results = evaluate_agent(
    agent=trained_agent,
    opponents=[
        "random",
        "simple_heuristic",
        "v22_rule_based",
    ],
    n_episodes=100,
)

for name, stats in results.items():
    print(f"{name}: win_rate={stats[\"win_rate\"]:.2%}, avg_money={stats[\"avg_money\"]}")
```

---

## 7. 目录结构

```
/data/app/sandbox/kaggle/kg-rl/
├── docs/                          # 设计文档
│   ├── 01-DESIGN-SPEC.md         # 本文档
│   ├── 02-OBSERVATION-SPACE.md  # Observation 详细设计
│   ├── 03-ACTION-SPACE.md      # Action 详细设计
│   └── 04-REWARD-DESIGN.md     # Reward 详细设计
│
├── src/                           # 代码
│   ├── __init__.py
│   ├── envs/                     # 环境
│   │   ├── __init__.py
│   │   ├── kagriculture_env.py   # Gymnasium 环境
│   │   └── obs_processor.py     # Observation 处理
│   │
│   ├── models/                   # 模型
│   │   ├── __init__.py
│   │   ├── policy.py             # Multi-head policy
│   │   └── value.py              # Value function
│   │
│   ├── algos/                    # 算法
│   │   ├── __init__.py
│   │   └── ppo.py                # PPO 实现
│   │
│   └── utils/                    # 工具
│       ├── __init__.py
│       ├── logger.py
│       └── checkpoint.py
│
├── configs/                       # 配置文件
│   ├── ppo_default.yaml
│   └── experiments/
│       ├── wheat_only.yaml
│       └── full_game.yaml
│
├── models/                        # 训练好的模型
│
├── logs/                          # 训练日志
│
├── scripts/                       # 脚本
│   ├── train.py                   # 训练入口
│   ├── eval.py                   # 评估入口
│   └── export.py                  # 导出 Kaggle submit 格式
│
└── README.md
```

---

## 8. 下一步计划

### Week 1: 环境搭建
- [ ] 实现 KagricultureEnv (Gymnasium wrapper)
- [ ] 实现 SimplifiedObs
- [ ] 实现 WheatOnly action space
- [ ] 验证环境能跑 720 步

### Week 2: 最小 RL 实验
- [ ] 接入 SB3 PPO
- [ ] 训练 10M steps
- [ ] 对比 random baseline

### Week 3-4: 扩展与验证
- [ ] 扩展到 full action space
- [ ] 训练 100M steps
- [ ] 对比 v22 rule-based

---

## 9. 参考资料

- [Stable Baselines3](https://stable-baselines3.readthedocs.io/)
- [Orbit Wars 1st Place](https://github.com/IsaiahPressman/kaggle-orbit-wars)
- [Orbit Wars 2nd Place](https://github.com/SimJeg/orbit-wars)
- [PPO Paper](https://arxiv.org/abs/1707.06347)

---

## 10. 运行环境

### 10.1 Conda 环境

项目运行在 conda 的 `kaggle` 环境下：

```bash
# 激活
source /data/app/miniconda3/bin/activate kaggle

# 路径
/data/app/miniconda3/envs/kaggle/
```

### 10.2 关键依赖

```bash
# 激活后验证
python --version    # Python 3.11
kaggle --version    # Kaggle CLI
```

| 包 | 用途 |
|-----|------|
| kaggle-environments==1.32.6 | Kagriculture 游戏环境 |
| stable-baselines3 | PPO RL |
| gymnasium | GYM 接口 |
| torch | 神经网络 (GPU 版在 RTX 5090 服务器) |

### 10.3 安装额外依赖

```bash
source /data/app/miniconda3/bin/activate kaggle

# 开发/训练
pip install stable-baselines3 gymnasium numpy pandas

# GPU 服务器 (RTX 5090)
pip install torch --index-url https://download.pytorch.org/whl/cu121
```
