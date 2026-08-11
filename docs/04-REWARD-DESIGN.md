# Reward 设计

> 本文档详细定义 Kagriculture RL 的 reward function

---

## 1. Reward 设计原则

### 1.1 Sparse vs Dense

| 类型 | 优点 | 缺点 | 推荐场景 |
|------|------|------|----------|
| **Sparse** | 简单、目标清晰 | 训练慢 | Phase 1 |
| **Dense** | 训练快、信号丰富 | 可能引导错误行为 | Phase 2+ |

### 1.2 Reward Scaling

RL 训练需要合理的 reward magnitude：
- 不要太大 (explosion)
- 不要太小 (gradient 消失)
- 建议：控制在 -1 到 1 范围内

---

## 2. Phase 1: Terminal Reward

### 2.1 最简版本

```python
def terminal_reward(episode_end_obs) -> float:
    """只用最终金钱作为 reward"""
    return episode_end_obs["money"] / 1000.0  # 归一化到 ~0-100
```

### 2.2 优缺点

**优点**：
- 简单
- 直接优化目标

**缺点**：
- 非常稀疏（720 步后才有一个 reward）
- 训练可能需要很长时间

### 2.3 预期效果

```
训练 10M steps 后:
- 比随机策略好 (随机 ~0 win rate)
- 比固定 heuristic 差 (因为信号太稀疏)
```

---

## 3. Phase 2: Dense Reward

### 3.1 设计

```python
def dense_reward(
    prev_obs: dict,
    action: dict,
    obs: dict,
    done: bool,
) -> float:
    """每步的 dense reward"""
    
    total_reward = 0.0
    
    # 1. 主要信号：金钱变化 (核心)
    money_delta = obs["money"] - prev_obs["money"]
    money_reward = money_delta / 1000.0  # 归一化
    total_reward += money_reward
    
    # 2. 辅助信号：Harvest bonus
    if obs.get("plants_ready", 0) > prev_obs.get("plants_ready", 0):
        # 有新作物成熟
        harvest_bonus = 0.1 * (obs["plants_ready"] - prev_obs["plants_ready"])
        total_reward += harvest_bonus
    
    # 3. 惩罚：未喂养的动物
    unfed_delta = obs.get("unfed_animals", 0) - prev_obs.get("unfed_animals", 0)
    if unfed_delta > 0:
        # 动物没喂饱，可能饿死
        death_penalty = -0.05 * unfed_delta
        total_reward += death_penalty
    
    # 4. 惩罚：没有行动
    if action == "HOLD" and obs["money"] > 1000:
        # 有钱但什么都不做，惩罚
        idle_penalty = -0.01
        total_reward += idle_penalty
    
    return total_reward
```

### 3.2 权重调优

```python
REWARD_WEIGHTS = {
    "money_delta": 1.0,        # 主要信号
    "harvest_bonus": 0.1,      # 辅助信号
    "death_penalty": -0.05,     # 惩罚
    "idle_penalty": -0.01,      # 惩罚
    "win_bonus": 1.0,          # 终局胜奖励
    "lose_penalty": -1.0,       # 终局败惩罚
}
```

---

## 4. Phase 3: 对战胜 Reward

### 4.1 Self-Play Reward

```python
def compute_win_reward(
    player_money: float,
    opponent_money: float,
) -> float:
    """基于对战胜负的 reward"""
    
    if player_money > opponent_money:
        return 1.0   # WIN
    elif player_money < opponent_money:
        return -1.0  # LOSE
    else:
        return 0.0   # TIE
```

### 4.2 Bradley-Terry Reward

```python
def compute_bt_reward(
    player_money: float,
    opponent_money: float,
    player_bt_score: float,  # 当前 BT 分数
    opponent_bt_score: float,
) -> float:
    """Bradley-Terry 预期的 reward"""
    
    # 预期胜率
    expected_win_prob = player_bt_score / (player_bt_score + opponent_bt_score)
    
    # 实际结果
    actual_win = 1.0 if player_money > opponent_money else 0.0
    
    # Reward = 实际 - 预期 (正值表示超出预期)
    return actual_win - expected_win_prob
```

### 4.3 Margin-based Reward

```python
def compute_margin_reward(
    player_money: float,
    opponent_money: float,
    margin_threshold: float = 10000.0,
) -> float:
    """基于金钱差距的 reward"""
    
    margin = player_money - opponent_money
    
    # Sigmoid 归一化
    normalized = 2.0 / (1.0 + np.exp(-margin / margin_threshold)) - 1.0
    
    return normalized  # -1 到 1
```

---

## 5. Reward Clipping

### 5.1 为什么需要 Clipping

避免极端 reward 导致训练不稳定。

### 5.2 实现

```python
def clip_reward(reward: float, min_val=-1.0, max_val=1.0) -> float:
    return max(min_val, min(max_val, reward))
```

### 5.3 不同阶段

| Phase | Clip Range | 说明 |
|-------|------------|------|
| Phase 1 | -10, 10 | 宽松，允许大 signal |
| Phase 2 | -5, 5 | 中等 |
| Phase 3 | -1, 1 | 严格，训练稳定 |

---

## 6. Reward Normalization

### 6.1 Running Mean Normalization

```python
class RewardNormalizer:
    def __init__(self, gamma=0.99, epsilon=1e-8):
        self.gamma = gamma
        self.epsilon = epsilon
        self.running_mean = 0
        self.running_var = 1
    
    def update(self, rewards):
        """更新 running statistics"""
        batch_mean = np.mean(rewards)
        batch_var = np.var(rewards)
        
        self.running_mean = self.gamma * self.running_mean + (1 - self.gamma) * batch_mean
        self.running_var = self.gamma * self.running_var + (1 - self.gamma) * batch_var
    
    def normalize(self, reward):
        """归一化 reward"""
        return (reward - self.running_mean) / (np.sqrt(self.running_var) + self.epsilon)
```

---

## 7. Final Reward Function

```python
class KagricultureReward:
    def __init__(self, config):
        self.gamma = config.get("gamma", 0.99)
        self.clip_range = config.get("clip_range", (-1.0, 1.0))
        self.use_dense = config.get("use_dense_reward", True)
    
    def compute(self, prev_obs, action, obs, done, opponent_money=None) -> float:
        """计算 reward"""
        
        if not done:
            # Step reward
            reward = self._compute_step_reward(prev_obs, action, obs)
        else:
            # Terminal reward
            reward = self._compute_terminal_reward(obs, opponent_money)
        
        # Clip
        reward = np.clip(reward, *self.clip_range)
        
        return reward
    
    def _compute_step_reward(self, prev_obs, action, obs) -> float:
        """每步 reward"""
        if not self.use_dense:
            return 0.0
        
        reward = 0.0
        
        # 1. Money delta
        money_delta = obs["money"] - prev_obs["money"]
        reward += money_delta / 1000.0
        
        # 2. Harvest bonus
        # ... (省略细节)
        
        return reward
    
    def _compute_terminal_reward(self, obs, opponent_money) -> float:
        """终局 reward"""
        reward = obs["money"] / 1000.0  # 主要：最终金钱
        
        if opponent_money is not None:
            # 胜败额外 reward
            if obs["money"] > opponent_money:
                reward += 10.0  # WIN bonus
            else:
                reward -= 10.0  # LOSE penalty
        
        return reward
```

---

## 8. 实现检查清单

- [ ] 实现 TerminalReward
- [ ] 实现 DenseReward
- [ ] 实现 WinReward
- [ ] 实现 RewardClipping
- [ ] 实现 RewardNormalizer (可选)
- [ ] 验证 reward magnitude 合理
- [ ] 调优 reward weights

---

## 9. 参考资料

- [Reward Shaping 论文](https://docs.google.com/document/d/1x3XXYWL)
- [Stable Baselines3 Reward Scaling](https://stable-baselines3.readthedocs.io/)
