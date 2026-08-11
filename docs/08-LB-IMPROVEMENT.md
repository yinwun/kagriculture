# Kagriculture RL — Kaggle 成绩分析与改进

> **目标**: 根据 Kaggle Leaderboard 成绩改进 RL Agent

---

## 1. 成绩诊断框架

### 1.1 成绩组成

```
LB Score = Win Rate × Base Score + Margin Bonus

示例:
- Win Rate = 50%
- Base Score = 2000
- Margin = +1000
- LB Score = 0.5 × 2000 + 1000 = 2000
```

### 1.2 差距分析

| 差距 | 诊断 | 改进方向 |
|------|------|----------|
| **Gap < 100** | 接近 top level | 微调，细优化 |
| **Gap 100-300** | 策略基本正确 | 优化 reward，调整 action |
| **Gap 300-500** | 有明显弱项 | 扩展 action，分析对手 |
| **Gap > 500** | 策略有问题 | 重新设计 reward 或 BC 预训练 |

---

## 2. 分析流程

```
┌─────────────────────────────────────────────────────────────────┐
│  Step 1: 提交 Kaggle → 获得 LB 成绩                              │
└────────────────────────────────┬────────────────────────────────┘
                                 │
                                 ▼
┌─────────────────────────────────────────────────────────────────┐
│  Step 2: 分析成绩差距                                            │
│     - Win rate vs Top players                                   │
│     - Margin 差距                                               │
│     - 不稳定的 round                                            │
└────────────────────────────────┬────────────────────────────────┘
                                 │
                                 ▼
┌─────────────────────────────────────────────────────────────────┐
│  Step 3: 下载 replay，分析问题                                   │
│     - 输在哪 step?                                              │
│     - 输给的对手类型?                                            │
│     - 缺少什么 action?                                          │
└────────────────────────────────┬────────────────────────────────┘
                                 │
                                 ▼
┌─────────────────────────────────────────────────────────────────┐
│  Step 4: 实施改进                                                │
└────────────────────────────────┬────────────────────────────────┘
                                 │
                                 ▼
┌─────────────────────────────────────────────────────────────────┐
│  Step 5: 重新训练 → 重新提交                                      │
└────────────────────────────────┬────────────────────────────────┘
                                 │
                                 └──→ Loop until Top 5
```

---

## 3. 下载并分析 Replay

### 3.1 获取提交记录

```bash
# 查看所有提交
kaggle competitions submissions -c kagriculture

# 下载特定提交的 replay
kaggle competitions download -c kagriculture -f replays/submission_v1.tar.gz
```

### 3.2 分析脚本

```python
#!/usr/bin/env python3
"""
分析 Kaggle 提交的 replay

Usage:
    python scripts/analyze_submission.py --replay_dir data/replays/v1/
"""

import json
import os
from collections import defaultdict

def analyze_replay(replay_path):
    """分析单个 replay"""
    with open(replay_path) as f:
        data = json.load(f)
    
    rewards = data["rewards"]
    p0_win = rewards[0] > rewards[1]
    margin = rewards[0] - rewards[1]
    
    # 分析每 step
    money_history = []
    for step in data["steps"]:
        p0_obs = step[0]["observation"]
        p0_farm = p0_obs.farms[0]
        money_history.append(p0_farm.get("money", 0))
    
    return {
        "win": p0_win,
        "margin": margin,
        "money_curve": money_history,
        "final_money": money_history[-1] if money_history else 0,
    }

def find_diverge_point(curve_a, curve_b):
    """找出两条曲线开始分歧的 point"""
    for i in range(min(len(curve_a), len(curve_b))):
        if abs(curve_a[i] - curve_b[i]) > 1000:
            return i
    return -1

def analyze_losing_episodes(replay_dir):
    """分析输的 episodes"""
    losing_episodes = []
    
    for fname in os.listdir(replay_dir):
        if not fname.endswith(".json"):
            continue
        
        result = analyze_replay(os.path.join(replay_dir, fname))
        
        if not result["win"]:
            losing_episodes.append(result)
    
    # 统计输的原因
    avg_margin = sum(e["margin"] for e in losing_episodes) / len(losing_episodes)
    avg_final_money = sum(e["final_money"] for e in losing_episodes) / len(losing_episodes)
    
    print(f"Losing episodes: {len(losing_episodes)}")
    print(f"Avg margin: {avg_margin:.0f}")
    print(f"Avg final money: {avg_final_money:.0f}")
    
    return losing_episodes
```

---

## 4. 问题诊断清单

### 4.1 Win Rate 问题

| 症状 | 可能原因 | 改进方法 |
|------|----------|----------|
| Win rate < 30% | Policy 太差 | 增加训练 steps，或 BC 预训练 |
| Win rate 30-50% | 策略一般 | 调整 reward，优化 action space |
| Win rate > 50% 但 margin 负 | 能赢但赢得少 | 优化赚钱效率 |
| Win rate 波动大 | Variance 高 | 降低 learning rate，加 entropy |

### 4.2 Margin 问题

| 症状 | 可能原因 | 改进方法 |
|------|----------|----------|
| Margin < -1000 | 赚钱能力差 | 分析 market strategy |
| Margin -500 ~ 0 | 小劣 | 优化细节 |
| Margin > 0 但小 | 险胜 | 增强优势策略 |
| Margin 波动大 | 不稳定 | 增加训练，多样本评估 |

### 4.3 对手相关问题

```python
# 统计输给的对手类型
opponent_stats = {
    "aggressive": {"win": 3, "lose": 7},  # 输多
    "passive": {"win": 8, "lose": 2},     # 赢多
    "balanced": {"win": 5, "lose": 5},   # 五五开
}

# 针对弱项改进
if opponent_stats["aggressive"]["lose_rate"] > 0.7:
    # 需要学更激进的策略
    # 增加 HIRE, BUY_PRODUCT 频率
```

---

## 5. 改进方法库

### 5.1 Reward Function 调整

```python
# 基础 reward (可能太小)
reward = money_delta / 10000  # ❌ scale 太小

# 改进 reward
def compute_reward(obs, done=False, won=False):
    # 1. 金钱变化 (主要) - 放大 scale
    money_reward = money_delta / 1000  # ✅ 放大 10x
    
    # 2. 存活奖励
    survival_reward = 0.01 if not dead else -1.0
    
    # 3. 效率奖励 (鼓励快速赚钱)
    efficiency_reward = money_delta / (step + 1) * 0.1
    
    # 4. WIN bonus (最终)
    win_bonus = 10.0 if won else -10.0
    
    # 5. 高 WIN% action 奖励
    high_win_action_reward = 0.1 if action in [FERTILIZE, DIG] else 0
    
    return money_reward + survival_reward + efficiency_reward + win_bonus + high_win_action_reward
```

### 5.2 Action Space 扩展

```python
# 如果发现某个高 WIN% action 从没用过
HIGH_WIN_ACTIONS = {
    "FERTILIZE": {"win_rate": 0.76, "usage": 0},
    "DIG": {"win_rate": 0.74, "usage": 0},
    "SELL_FERTILIZER": {"win_rate": 0.77, "usage": 0},
}

# 统计当前 usage
for episode in replays:
    for step in episode["steps"]:
        if step["action"]["farmer"] == "FERTILIZE":
            HIGH_WIN_ACTIONS["FERTILIZE"]["usage"] += 1

# 如果 usage == 0，说明需要扩展 action space
if HIGH_WIN_ACTIONS["FERTILIZE"]["usage"] == 0:
    print("WARNING: FERTILIZE 从未使用，考虑扩展到 Phase 3")
```

### 5.3 Entropy / Exploration 调整

```python
# 如果策略太确定 (entropy 太低)
if policy_entropy < 0.5:
    # 增加探索
    ent_coef = 0.01  # 原始
    ent_coef = 0.05  # 加大探索
    
# 如果策略太随机 (entropy 太高)
if policy_entropy > 2.0:
    # 减少探索
    ent_coef = 0.01  # 原始
    ent_coef = 0.005  # 减少探索
```

### 5.4 对手针对性训练

```python
# 1. 分析对手类型
def classify_opponent(opponent_actions):
    """分类对手类型"""
    hire_count = opponent_actions.count("HIRE")
    sell_count = opponent_actions.count("SELL")
    
    if hire_count / len(opponent_actions) > 0.3:
        return "aggressive"
    elif sell_count / len(opponent_actions) > 0.3:
        return "trader"
    else:
        return "balanced"

# 2. 针对弱项调整
if opponent_type == "aggressive" and lose_rate > 0.7:
    # 对手激进，我方也需要激进
    # 提高 HIRE action 概率
```

---

## 6. 快速验证改进

### 6.1 本地评估

```bash
# 在本地评估改进效果
python scripts/eval.py \
    --model_path models/updated_v1 \
    --n_episodes 100 \
    --opponent random

# 对比改进前后
python scripts/eval.py --model_path models/baseline --n_episodes 100
```

### 6.2 评估表格

| Metric | Before | After | Delta | Status |
|--------|--------|-------|-------|--------|
| Win rate vs random | 45% | 55% | +10% | ✅ |
| Win rate vs v22 | 30% | 40% | +10% | ✅ |
| Avg margin | -500 | +200 | +700 | ✅ |
| Variance | 2000 | 1500 | -500 | ✅ |

### 6.3 提交标准

| 条件 | 说明 |
|------|------|
| Win rate vs baseline > 50% | 可以提交 |
| Margin 提升 > 200 | 改进有效 |
| Variance 降低 | 更稳定 |

---

## 7. 迭代改进循环

```
                    ┌─────────────────────┐
                    │   提交 Kaggle        │
                    │   获得 LB 成绩       │
                    └──────────┬──────────┘
                               │
                               ▼
                 ┌────────────────────────────┐
                 │   分析差距                  │
                 │   下载 replay               │
                 └──────────┬─────────────────┘
                            │
              ┌─────────────┼─────────────┐
              │             │             │
              ▼             ▼             ▼
        ┌──────────┐  ┌──────────┐  ┌──────────┐
        │ Reward   │  │ Action   │  │ 对手     │
        │ 问题     │  │ Space    │  │ 分析     │
        └────┬─────┘  └────┬─────┘  └────┬─────┘
             │             │             │
             └─────────────┼─────────────┘
                           │
                           ▼
                 ┌────────────────────────────┐
                 │   实施改进                  │
                 │   - 调整 reward            │
                 │   - 扩展 action            │
                 │   - 针对训练               │
                 └──────────┬─────────────────┘
                            │
                            ▼
                 ┌────────────────────────────┐
                 │   本地评估通过?             │
                 └──────────┬─────────────────┘
                            │
                   ┌────────┴────────┐
                   │                 │
                  YES               NO
                   │                 │
                   ▼                 ▼
            ┌──────────┐      ┌──────────┐
            │ 重新提交  │      │ 分析原因  │
            └──────────┘      └──────────┘
```

---

## 8. 常见问题与解决方案

| 问题 | 诊断 | 解决方案 |
|------|------|----------|
| Win rate 50% 但 margin 负 | 能赢但赢得少 | 优化赚钱效率 |
| 某个 action 从未使用 | action space 太小 | 扩展到 Phase 2/3 |
| 对手激进就输 | 策略不够灵活 | 加 entropy，多样化 |
| 训练 loss 下降但 win rate 不涨 | reward 不够 dense | 增加 dense reward |
| 训练 NaN | 梯度爆炸 | 减小 learning rate |
| 提交后成绩比本地差 | overfitting | 增加 regularization |

---

## 9. 下一步决策树

```
LB 成绩 < Top 5?
        │
        ├── YES: Gap > 500?
        │         │
        │         ├── YES → 需要重新设计
        │         │         - BC 预训练
        │         │         - 重新设计 reward
        │         │
        │         └── NO: Gap 100-500
        │                   - 分析 replay
        │                   - 调整 reward
        │                   - 扩展 action
        │
        └── YES: Gap < 100 (接近 top)
                  - 微调
                  - 优化细节
```

---

## 10. 参考命令

```bash
# 查看提交
kaggle competitions submissions -c kagriculture

# 下载 replay
kaggle competitions download -c kagriculture -f replays/v1.tar.gz

# 提交
kaggle competitions submit -c kagriculture -f submission.tar.gz -m "RL v2 improved reward"

# 本地评估
python scripts/eval.py --model_path models/v2 --n_episodes 100
```
