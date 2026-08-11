# Kagriculture RL — 项目进度

> **Last Updated**: 2026-08-09
> **目标**: 进入 Kaggle Leaderboard Top 5

---

## 1. 整体流程图

```
┌─────────────────────────────────────────────────────────────────────────┐
│                        数据收集与处理                                    │
│  (每日 675 episodes × 7 天 ≈ 4,725 episodes)                            │
└────────────────────────────────┬────────────────────────────────────────┘
                                 │
                                 ▼
┌─────────────────────────────────────────────────────────────────────────┐
│                     阶段 1: 行为克隆 (BC)                                │
│  ┌─────────────────────────────────────────────────────────────────┐    │
│  │  输入: Winner 的 (observation, action) pairs                     │    │
│  │  目标: 最大化 log P(action|obs)                                  │    │
│  │  输出: 预训练的 policy                                           │    │
│  └─────────────────────────────────────────────────────────────────┘    │
└────────────────────────────────┬────────────────────────────────────────┘
                                 │
                                 ▼
┌─────────────────────────────────────────────────────────────────────────┐
│                     阶段 2: PPO 在线强化学习                             │
│  ┌─────────────────────────────────────────────────────────────────┐    │
│  │  输入: BC 预训练的 policy + 对手模型 self-play                   │    │
│  │  目标: 最大化 expected cumulative reward                         │    │
│  │  输出: 训练好的 RL agent                                         │    │
│  └─────────────────────────────────────────────────────────────────┘    │
└────────────────────────────────┬────────────────────────────────────────┘
                                 │
                                 ▼
┌─────────────────────────────────────────────────────────────────────────┐
│                     阶段 3: 导出与提交                                   │
│  ┌─────────────────────────────────────────────────────────────────┐    │
│  │  导出为 main.py + src/ + 模型权重                                │    │
│  │  提交到 Kaggle: kaggle competitions submit                      │    │
│  └─────────────────────────────────────────────────────────────────┘    │
└─────────────────────────────────────────────────────────────────────────┘
```

---

## 2. 数据用途详解

### 2.1 数据来源

| 来源 | 数量 | 路径 |
|------|------|------|
| 2026-08-07 | 675 episodes | `/data/app/sandbox/kaggle/kg-rl/data/extracted/2026-08-07/` |
| 2026-08-08 | 675 episodes | `/data/app/sandbox/kaggle/kg-rl/data/extracted/2026-08-08/` |
| **总计** | **1,350 episodes** | |

### 2.2 数据结构

```python
{
    rewards: [54528.0, 52963.0],  # P0, P1 最终 money
    steps: [                      # 720 步 (30 days × 24 hours)
        [
            {   # Player 0
                action: {farmer: [...], market: [...]},
                observation: {...},
                reward: 0,
                status: ACTIVE
            },
            {   # Player 1
                action: {...},
                observation: {...},
                reward: 0,
                status: ACTIVE
            }
        ],
        ...
    ]
}
```

### 2.3 数据使用方法

| 方法 | 用途 | 状态 | 说明 |
|------|------|------|------|
| **Behavioral Cloning** | 预训练 policy | ⬜ 未实现 | 直接模仿 winner action |
| **Value Function 预训练** | 预测最终 reward | ⬜ 未实现 | 帮助 RL 评估状态 |
| **Reward Shaping** | 中间状态给 reward | ⬜ 未实现 | 从数据中学到好状态特征 |
| **对手建模** | 预测对手行为 | ⬜ 未实现 | 用于 self-play |
| **Offline RL** | Dataset RL | ⬜ 未实现 | 需要更多数据 |

---

## 3. Action Space Phase 设计

基于 1,282 episodes 统计分析

### Phase 1: Market Core (95%+ 覆盖) ✅ 已实现

```python
ACTIONS = [HOLD, HIRE, SELL_WHEAT, BUY_PRODUCT_WHEAT, PASS]
```

### Phase 2: + Seeds/Animals (~99%) ⬜ 待实现

```python
+ [BUY_SEED, SELL_STRAWBERRY, SELL_MILK, BUY_ANIMAL]
```

### Phase 3: + High-WIN-Rate Actions ⬜ 待实现

```python
+ [FERTILIZE (WIN% 76%), DIG (WIN% 74%), SELL_FERTILIZER (WIN% 77%)]
```

### Phase 4: Full Action Space (~20) ⬜ 待实现

```python
Market(10) + Farmer(5) + Hands(5)
```

---

## 4. 当前项目状态

### ✅ 已完成

| 模块 | 文件 | 状态 | 说明 |
|------|------|------|------|
| 环境注册 | `src/envs/kagriculture_env.py` | ✅ | kaggriculture (两个 g) |
| KagricultureEnv | `src/envs/kagriculture_env.py` | ✅ | Gymnasium wrapper, 32-dim obs |
| Policy Network | `src/models/policy.py` | ✅ | SimplePolicy (128 hidden) |
| PPO Agent | `src/algos/ppo.py` | ✅ | 基于 Stable Baselines3 |
| 训练脚本 | `scripts/train.py` | ✅ | 入口已实现 |
| 测试脚本 | `scripts/test_env.py` | ✅ | 720 steps 通过 |
| 导出脚本 | `scripts/export.py` | ✅ | tar.gz 格式 |
| 配置文件 | `configs/wheat_only.yaml` | ✅ | Phase 1 配置 |
| 环境验证 | — | ✅ | 644 steps/sec |

### ⬜ 进行中

| 模块 | 优先级 | 说明 |
|------|--------|------|
| 修复 Reward 计算 | P0 | 当前 reward 始终为 0 |
| Action Masking | P1 | 禁止非法 action |
| 1M steps 短训练 | P1 | 验证 RL 能学到东西 |

### ⬜ 待实现

| 模块 | 说明 |
|------|------|
| Behavioral Cloning 脚本 | BC 预训练 |
| Value Function 预训练 | 预测最终 reward |
| 评估脚本 | 对比 random/v22 |
| Phase 2 Actions | + Seeds/Animals |
| 对手模型 | 预测对手行为 |

---

## 5. 开发流程

遵循 `.claude/WORKFLOW.md`:

```
代码修改 → Code Review → 修复 P0/P1 → 本地评估 → 训练 → 提交
```

### 评估标准

| Gate | 条件 | 标准 |
|------|------|------|
| Gate 1 | 环境验证 | 720 steps 正常运行 |
| Gate 2 | 短训练 (1M steps) | Win rate > random (20%) |
| Gate 3 | 中等训练 (10M steps) | Win rate vs v22 > 30% |
| Gate 4 | 完整训练 (100M steps) | Win rate vs top players > 30% |

---

## 6. 下一步计划

### 立即 (本周)

1. **修复 Reward 计算** (P0)
   - 当前 `money_delta / 10000` 太小
   - 建议改为 `money_delta / 1000` 或更大的 scale

2. **BC 预训练脚本** (P1)
   ```bash
   python scripts/train_bc.py --epochs 10 --data_dir data/extracted/
   ```

3. **1M steps 短训练验证** (P1)
   ```bash
   python scripts/train.py --total_steps 1000000
   ```

### 中期 (2-4 周)

1. Phase 2 Actions 扩展
2. 对手模型实现
3. Self-play 训练
4. 10M-100M steps 训练

### 长期 (目标)

1. 进入 Kaggle Top 5
2. 分析 top players 策略
3. 持续优化

---

## 7. 关键文件路径

```
/data/app/sandbox/kaggle/kg-rl/
├── src/
│   ├── envs/kagriculture_env.py    # 环境 + reward
│   ├── models/policy.py            # Policy Network
│   └── algos/ppo.py                # PPO Agent
├── scripts/
│   ├── train.py                    # 训练入口
│   ├── train_bc.py                 # ⬜ BC 预训练 (待实现)
│   ├── test_env.py                 # 环境测试
│   ├── eval.py                     # ⬜ 评估脚本 (待实现)
│   └── export.py                   # 导出提交
├── configs/
│   └── wheat_only.yaml             # Phase 1 配置
├── data/
│   └── extracted/                  # Replay 数据
│       ├── 2026-08-07/             # 675 episodes
│       └── 2026-08-08/             # 675 episodes
├── docs/
│   ├── 01-DESIGN-SPEC.md           # 设计规范
│   ├── 03-ACTION-SPACE.md          # Action 设计
│   ├── 04-REWARD-DESIGN.md         # Reward 设计
│   ├── 06-ACTION-SPACE-REFERENCE.md # 统计数据
│   └── 07-PROJECT-PROGRESS.md      # 本文档
├── models/                         # 保存的模型
└── .claude/
    └── WORKFLOW.md                 # 开发流程
```

---

## 8. 参考资料

- [Orbit Wars 1st Place](https://github.com/IsaiahPressman/kaggle-orbit-wars)
- [Orbit Wars 2nd Place](https://github.com/SimJeg/orbit-wars)
- [Stable Baselines3](https://stable-baselines3.readthedocs.io/)
- [Behavioral Cloning Survey](https://arxiv.org/abs/1909.03599)
