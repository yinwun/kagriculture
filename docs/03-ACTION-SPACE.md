# Kagriculture Action Space 设计

> **Version**: 1.1
> **Date**: 2026-08-09
> **Based on**: 1,282 episodes 统计分析

---

## 1. 设计原则

### 1.1 从少到多，分 Phase 扩展

| Phase | Actions | 覆盖 | 目标 |
|-------|---------|------|------|
| 1 | 4-5 | 95% | 验证 RL 能 work |
| 2 | 8-10 | 99% | 扩展交易品种 |
| 3 | 15+ | 99%+ | 加入高 WIN% actions |
| 4 | 20+ | 100% | Full action space |

### 1.2 数据驱动的优先级

- **频率高** → 优先包含
- **WIN% 高** → 高权重
- **组合效果** → 考虑 action 之间的依赖

---

## 2. Phase 1: Market Core (95%+ 覆盖)

### 2.1 Action 定义

```python
PHASE1_ACTIONS = [
    0: "HOLD",              # 不操作
    1: "HIRE",              # 雇佣 (38.6%, WIN% 51.5%)
    2: "SELL_WHEAT",        # 卖小麦 (28.6% of SELL)
    3: "BUY_PRODUCT_WHEAT", # 买小麦 (26.2%)
]
```

### 2.2 统计依据

| Action | 频率 | WIN% | 累计 |
|--------|------|------|------|
| HIRE | 38.6% | 51.5% | 38.6% |
| SELL (WHEAT) | 28.6% × 30.2% ≈ 8.6% | ~50% | 47.2% |
| BUY_PRODUCT (WHEAT) | 26.2% | 50.9% | **73.4%** |
| HOLD | — | — | +22% |

**总覆盖**: ~95% 的 market actions

### 2.3 实现

```python
# action_space = Discrete(4)
action_to_str = {
    0: [],                                          # HOLD
    1: [{"market": [["HIRE"]]}],                    # HIRE
    2: [{"market": [["SELL", "WHEAT", 1]]}],        # SELL_WHEAT
    3: [{"market": [["BUY_PRODUCT", "WHEAT", 1]]}], # BUY_WHEAT
}
```

---

## 3. Phase 2: + Seeds/Animals (~99% 覆盖)

### 3.1 Action 定义

```python
PHASE2_ACTIONS = PHASE1_ACTIONS + [
    4: "BUY_SEED",           # 买种子 (3.4%)
    5: "SELL_STRAWBERRY",    # 卖草莓 (15.5% of SELL)
    6: "SELL_MILK",          # 卖牛奶 (21.2% of SELL)
    7: "BUY_ANIMAL",         # 买动物 (1.2%)
]
```

### 3.2 统计依据

| Action | 频率 | WIN% | 累计 |
|--------|------|------|------|
| HIRE | 38.6% | 51.5% | 38.6% |
| SELL_WHEAT | 8.6% | ~50% | 47.2% |
| BUY_PRODUCT_WHEAT | 26.2% | 50.9% | 73.4% |
| BUY_SEED | 3.4% | — | 76.8% |
| SELL_STRAWBERRY | ~4.7% | — | 81.5% |
| SELL_MILK | ~6.4% | — | 87.9% |
| BUY_ANIMAL | 1.2% | — | **89.1%** |

**总覆盖**: ~99%

---

## 4. Phase 3: + High-WIN-Rate Actions

### 4.1 Action 定义

```python
PHASE3_ACTIONS = PHASE2_ACTIONS + [
    8: "FERTILIZE",          # 施肥 (WIN% 76.2% ⭐⭐⭐⭐)
    9: "DIG",                # 挖掘 (WIN% 73.7% ⭐⭐⭐)
    10: "SELL_FERTILIZER",   # 卖肥料 (WIN% 77.4% ⭐⭐⭐⭐)
]
```

### 4.2 统计依据

这些 action 虽然频率低，但 WIN% 显著高于平均！

| Action | 频率 | WIN% | Diff |
|--------|------|------|------|
| FERTILIZE | ~0.2% | **76.2%** | +25% |
| DIG | ~0.1% | **73.7%** | +23% |
| SELL_FERTILIZER | ~5% | **77.4%** | +26% |

**注意**: FERTILIZE 和 DIG 在 Phase 1-2 数据中极少出现，但在 winner 中显著更多。

### 4.3 实现要点

```python
# FERTILIZE 需要:
# 1. 先到有作物的 tile
# 2. 消耗肥料
# 3. 加速作物生长

# DIG 需要:
# 1. 先到特定位置
# 2. 可能有隐藏奖励
```

---

## 5. Phase 4: Full Action Space

### 5.1 Market Actions (10)

```python
MARKET_ACTIONS = [
    "HOLD",
    "HIRE", "SELL_WHEAT", "SELL_MILK", "SELL_STRAWBERRY", "SELL_MELON", "SELL_FERTILIZER", "SELL_WOOL",
    "BUY_PRODUCT_WHEAT", "BUY_SEED", "BUY_ANIMAL", "BUY_LAND",
]
```

### 5.2 Farmer Actions (10)

```python
FARMER_ACTIONS = [
    "PASS",
    "NORTH", "SOUTH", "EAST", "WEST",  # 移动
    "PLANT", "WATER", "HARVEST", "FERTILIZE", "DIG",  # 农业
]
```

### 5.3 Hands Actions (5)

```python
HAND_ACTIONS = [
    "PASS", "WATER", "FEED", "HARVEST", "COLLECT_FERTILIZER",
]
```

### 5.4 完整 action space

```python
# 总共约 25 个离散 action
# 但实际环境有 hierarchical structure:
# action = {
#     "farmer": [...],      # list of farmer actions
#     "hands": [[...], ...], # list per hand
#     "market": [[...], ...] # list of market orders
# }
```

---

## 6. Hierarchical Action Space (未来考虑)

### 6.1 当前限制

Kaggle 环境要求同时输出 farmer、hands、market 三个部分。

### 6.2 建议的 hierarchical 设计

```python
class HierarchicalActionSpace:
    """
    分层 action space
    
    Level 1: 选择主要策略模式
    Level 2: 在该模式下的具体 action
    """
    
    # Level 1: 策略模式
    STRATEGY_MODES = [
        "market_focus",      # 专注市场交易
        "farm_focus",        # 专注农业生产
        "animal_focus",      # 专注畜牧业
        "balanced",          # 平衡发展
    ]
    
    # Level 2: 具体 actions
    MARKET_ACTIONS = ["HIRE", "SELL", "BUY"]
    FARM_ACTIONS = ["PLANT", "WATER", "HARVEST", "FERTILIZE"]
    ANIMAL_ACTIONS = ["FEED", "COLLECT", "BREED"]
```

---

## 7. Action Masking

### 7.1 合法性检查

```python
def get_valid_actions(obs) -> List[int]:
    """根据当前状态返回合法的 action indices"""
    valid = list(range(4))  # Phase 1 全部合法
    
    # 如果没有钱，不能 HIRE
    if obs["money"] < 100:
        valid.remove(1)  # 移除 HIRE
    
    # 如果没有小麦，不能 SELL
    if obs.get("wheat_in_shed", 0) <= 0:
        valid.remove(2)  # 移除 SELL_WHEAT
    
    # 如果市场没有小麦，不能 BUY
    if obs.get("market_inventory", {}).get("WHEAT", 0) <= 0:
        valid.remove(3)  # 移除 BUY_WHEAT
    
    return valid
```

### 7.2 Mask 实现

```python
class MaskedPPO(PPO):
    """支持 action masking 的 PPO"""
    
    def _get_action(self, obs, action_masks=None):
        if action_masks is not None:
            # 将 invalid actions 的 logits 设为 -inf
            logits = self.policy网络的输出
            logits[action_masks == 0] = -1e10
        return super()._get_action(obs)
```

---

## 8. 实施计划

### Phase 1 (Week 1-2)
- [x] 定义 action space
- [x] 实现 KagricultureEnv
- [ ] 测试 4-action 环境
- [ ] 训练 10M steps
- [ ] 对比 random baseline

### Phase 2 (Week 3-4)
- [ ] 添加更多 market actions
- [ ] 添加 action masking
- [ ] 扩展 observation

### Phase 3 (Week 5-8)
- [ ] 添加 FERTILIZE、DIG 等高 WIN% actions
- [ ] 可能的 hierarchical action space

---

## 9. 参考

| 统计项 | 值 |
|--------|---|
| Market actions/episode | ~720 |
| Farmer actions/episode | ~720 |
| Hands actions/episode | ~720 × hands_count |
| Total actions/episode | ~2000+ |
