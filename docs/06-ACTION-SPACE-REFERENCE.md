# Kagriculture Action Space 参考文档

> 基于 episode-89950852-replay.json 分析
> Episode 共 720 步，统计所有 action 出现次数

---

## 1. Action 结构

```python
action = {
    "farmer": ["ACTION", ...],      # Farmer 的动作列表
    "hands": [["ACTION"], ...],      # 每个 hand 的动作列表
    "market": [["ORDER", ...], ...] # 市场订单列表
}
```

**关键约束**：
- Market orders 最多 10 个
- Hands 数量可变（可通过 HIRE 增加）

---

## 2. Farmer Actions

### 2.1 完整列表（按频率排序）

| Action | 次数 | 说明 |
|--------|------|------|
| PASS | 245 | 跳过 |
| NORTH | 203 | 向北移动 |
| WEST | 203 | 向西移动 |
| EAST | 189 | 向东移动 |
| SOUTH | 144 | 向南移动 |
| WATER | 152 | 浇水 |
| FEED | 119 | 喂养动物 |
| PICKUP | 38 | 捡起物品 |
| COLLECT_FERTILIZER | 36 | 收集肥料 |
| CARE | 35 | 照顾 |
| HARVEST | 31 | 收获 |
| WHEAT | 25 | 收小麦 |
| DROP | 14 | 放下物品 |
| COW | 12 | 放牛 |
| PLANT | 12 | 种植 |
| PLACE | 10 | 放置 |
| SHEEP | 8 | 放羊 |
| STRAWBERRY | 6 | 种草莓 |
| CARROT | 5 | 种胡萝卜 |
| FERTILIZE | 4 | 施肥 |
| DIG | 3 | 挖掘 |
| FERTILIZER | 3 | 使用肥料 |
| BUILD_PASTURE | 2 | 建牧场 |
| MELON | 1 | 种瓜 |

**共 25 种 farmer actions**

### 2.2 Action 分类

| 类别 | Actions |
|------|---------|
| **移动** | NORTH, SOUTH, EAST, WEST |
| **农业** | PLANT, WATER, HARVEST, FERTILIZE, DIG |
| **畜牧** | FEED, COW, SHEEP, BUILD_PASTURE |
| **物品** | PICKUP, DROP, PLACE |
| **肥料** | COLLECT_FERTILIZER, FERTILIZER |
| **销售** | WHEAT, CARROT, STRAWBERRY, MELON |
| **其他** | PASS, CARE |

---

## 3. Hands Actions

### 3.1 完整列表（按频率排序）

| Action | 次数 | 说明 |
|--------|------|------|
| PASS | 2755 | 跳过 |
| NORTH | 2502 | 向北移动 |
| WEST | 2133 | 向西移动 |
| SOUTH | 1773 | 向南移动 |
| EAST | 1767 | 向东移动 |
| WATER | 1066 | 浇水 |
| COLLECT_FERTILIZER | 613 | 收集肥料 |
| FEED | 522 | 喂养 |
| CARE | 483 | 照顾 |
| HARVEST | 405 | 收获 |
| WHEAT | 168 | 收小麦 |
| PLANT | 154 | 种植 |
| PICKUP | 145 | 捡起 |
| DROP | 140 | 放下 |
| FERTILIZE | 127 | 施肥 |
| STRAWBERRY | 62 | 种草莓 |
| DIG | 47 | 挖掘 |
| MELON | 35 | 种瓜 |
| BUILD_PASTURE | 28 | 建牧场 |
| COW | 22 | 放牛 |
| SHEEP | 22 | 放羊 |
| PLACE | 20 | 放置 |
| CARROT | 10 | 种胡萝卜 |

**共 24 种 hands actions**

### 3.2 与 Farmer Actions 的区别

- Hands 是 **workers**，执行具体任务
- Farmer 指挥，Hands 执行
- Hands 的动作与 Farmer 高度重叠（除了没有 CARE）

---

## 4. Market Actions

### 4.1 订单类型总览

| 订单类型 | 格式 | 示例 |
|----------|------|------|
| HIRE | `["HIRE"]` | 雇佣 1 人 |
| BUY_LAND | `["BUY_LAND"]` | 购买土地 |
| BUY_ANIMAL | `["BUY_ANIMAL", "COW/SHEEP", qty]` | 购买动物 |
| BUY_PRODUCT | `["BUY_PRODUCT", "WHEAT", qty]` | 购买产品 |
| BUY_SEED | `["BUY_SEED", "MELON/STRAWBERRY/WHEAT/CARROT", qty]` | 购买种子 |
| SELL | `["SELL", "WHEAT/MELON/STRAWBERRY/CARROT/FERTILIZER/EGG/MILK/WOOL", qty]` | 卖出 |

### 4.2 HIRE 订单

| 格式 | 次数 |
|------|------|
| `("HIRE",)` | 650 |

**注意**：HIRE 没有数量参数，每次只能雇佣 1 人

### 4.3 BUY_PRODUCT 订单

| 格式 | 次数 |
|------|------|
| `("BUY_PRODUCT", "WHEAT", 1)` | 294 |
| `("BUY_PRODUCT", "WHEAT", 2)` | 102 |
| `("BUY_PRODUCT", "WHEAT", 3)` | 22 |
| `("BUY_PRODUCT", "WHEAT", 30)` | 14 |

**主要购买 WHEAT，数量 1-30**

### 4.4 BUY_SEED 订单

| 格式 | 次数 |
|------|------|
| `("BUY_SEED", "CARROT", 1)` | 22 |
| `("BUY_SEED", "WHEAT", 1)` | 22 |
| `("BUY_SEED", "STRAWBERRY", 1)` | 16 |
| `("BUY_SEED", "WHEAT", 2)` | 11 |
| `("BUY_SEED", "MELON", 1)` | 8 |

### 4.5 BUY_ANIMAL 订单

| 格式 | 次数 |
|------|------|
| `("BUY_ANIMAL", "COW", 1)` | 8 |
| `("BUY_ANIMAL", "SHEEP", 1)` | 6 |

### 4.6 SELL 订单

| 格式 | 次数 |
|------|------|
| `("SELL", "FERTILIZER", 1)` | 46 |
| `("SELL", "STRAWBERRY", 4)` | 17 |
| `("SELL", "FERTILIZER", 2)` | 16 |
| `("SELL", "WHEAT", 3)` | 16 |
| `("SELL", "CARROT", 3)` | 15 |
| `("SELL", "WOOL", 4)` | 14 |
| `("SELL", "WHEAT", 30)` | 14 |
| `("SELL", "FERTILIZER", 3)` | 12 |
| `("SELL", "MILK", 3)` | 12 |
| `("SELL", "WOOL", 6)` | 11 |
| `("SELL", "MILK", 6)` | 9 |
| `("SELL", "MILK", 9)` | 9 |
| `("SELL", "FERTILIZER", 14)` | 9 |
| `("SELL", "WOOL", 3)` | 9 |
| `("SELL", "MILK", 12)` | 7 |
| `("SELL", "WHEAT", 2)` | 7 |
| `("SELL", "STRAWBERRY", 2)` | 8 |
| `("SELL", "WHEAT", 4)` | 6 |

**主要出售 FERTILIZER、WHEAT、MILK、WOOL、STRAWBERRY**

---

## 5. Market Actions 完整统计

共 **128 种不同的 market actions**

### 5.1 按产品分类

| 产品 | BUY 次数 | SELL 次数 |
|------|----------|-----------|
| WHEAT | 465 | 60 |
| FERTILIZER | 0 | 106 |
| MILK | 0 | 37 |
| WOOL | 0 | 38 |
| STRAWBERRY | 16 | 25 |
| CARROT | 22 | 15 |
| MELON | 8 | 0 |
| COW | 8 | 0 |
| SHEEP | 6 | 0 |

**结论**：
- 主要 BUY WHEAT（买饲料）
- 主要 SELL FERTILIZER、MILK、WOOL（卖出产品）
- HIRE 是最频繁的 action（650 次）

### 5.2 Quantity 分布

| 产品 | 常见数量 |
|------|----------|
| WHEAT | 1, 2, 3, 30 |
| FERTILIZER | 1, 2, 3, 14 |
| MILK | 3, 6, 9, 12 |
| WOOL | 3, 4, 6 |
| STRAWBERRY | 2, 4 |
| CARROT | 1, 3 |

---

## 6. RL Action Space 建议

### 6.1 简化版（Phase 1 推荐）

```python
# 只学习 Market 决策，其他用 heuristic
SIMPLE_MARKET_ACTIONS = [
    "HOLD",                    # 0: 什么都不做
    "BUY_WHEAT",               # 1: 买小麦
    "SELL_WHEAT",              # 2: 卖小麦
    "BUY_FERTILIZER",          # 3: 买肥料
    "SELL_FERTILIZER",         # 4: 卖肥料
    "BUY_ANIMAL",              # 5: 买动物
    "SELL_MILK",               # 6: 卖牛奶
    "SELL_WOOL",               # 7: 卖羊毛
    "SELL_STRAWBERRY",         # 8: 卖草莓
    "HIRE",                    # 9: 雇佣
]
```

### 6.2 中等版（Phase 2）

```python
# 扩展 market + 简化 field
MEDIUM_ACTIONS = [
    # Market (10)
    "HOLD",
    "BUY_WHEAT", "SELL_WHEAT",
    "BUY_FERTILIZER", "SELL_FERTILIZER",
    "BUY_ANIMAL", "SELL_MILK", "SELL_WOOL",
    "SELL_STRAWBERRY", "HIRE",
    
    # Field (5)
    "PLANT_MELON", "PLANT_STRAWBERRY", "PLANT_CARROT",
    "HARVEST_ALL", "FEED_ALL",
]
```

### 6.3 完整版（Phase 3，需大量训练）

```python
# 完整的离散化 action space
FULL_ACTIONS = {
    "market_type": Discrete(5),      # HOLD, BUY, SELL, HIRE, LAND
    "market_product": Discrete(8),   # WHEAT, FERTILIZER, MILK, WOOL, STRAWBERRY, CARROT, MELON, ANIMAL
    "market_qty": Discrete(5),       # 1, 2, 4, 8, 16
    "field_action": Discrete(6),      # PLANT, WATER, HARVEST, FEED, PASS, CARE
    "crop_type": Discrete(4),        # MELON, STRAWBERRY, CARROT, WHEAT
}
```

---

## 7. 总结

| 维度 | 原始数量 | RL 可行性 |
|------|----------|-----------|
| Farmer Actions | 25 | ❌ 需简化 |
| Hands Actions | 24 | ❌ 需简化 |
| Market Actions | 128 | ⚠️ 需简化 |
| **建议简化后** | **10-15** | ✅ 可行 |

**推荐 Phase 1 只学 Market (10 actions)**，其他用预设规则。


---

## 8. Phase 设计的统计方法论

### 8.1 数据来源

```bash
# 从 daily zip 提取 episode 进行分析
/data/app/sandbox/kaggle/kg-rl/data/kagriculture-episodes-2026-08-04.zip  (9MB, ~80 episodes)
```

### 8.2 分析脚本模板

```python
#!/usr/bin/env python3
"""分析 market action 与胜负的相关性"""

import zipfile
import json
from collections import defaultdict

def analyze_actions(zip_path, n_samples=100):
    """分析 n_samples 个 episode"""
    
    action_wins = defaultdict(int)  # Winner 使用的次数
    action_losses = defaultdict(int) # Loser 使用的次数
    
    with zipfile.ZipFile(zip_path, "r") as zf:
        episodes = [f for f in zf.namelist() if f.endswith("-replay.json")]
        
        for fname in episodes[:n_samples]:
            with zf.open(fname) as f:
                data = json.load(f)
            
            rewards = data["rewards"]
            winner_idx = 0 if rewards[0] > rewards[1] else 1
            
            for step in data["steps"]:
                for agent_idx, agent_step in enumerate(step):
                    action = agent_step.get("action", {})
                    market = action.get("market", [])
                    
                    for order in market:
                        if isinstance(order, list) and len(order) > 0:
                            key = tuple(order)  # 完整 action
                            if agent_idx == winner_idx:
                                action_wins[key] += 1
                            else:
                                action_losses[key] += 1
    
    return action_wins, action_losses
```

### 8.3 Phase 设计标准

基于统计数据，设计原则：

1. **频率优先**：高频 action 先学
2. **胜负相关**：与 WIN 正相关的 action 优先
3. **边际价值**：低频率但高价值的 action 不能忽略

### 8.4 待补充分析

**当前数据不足**，建议后续补充：

- [ ] 分析 100+ episodes 的 WIN/LOSE 差异
- [ ] 分析不同阶段的 action 分布（day 0-10 vs day 20-30）
- [ ] 分析不同金钱水平玩家的 action 差异
- [ ] 分析 top 10% vs bottom 10% 玩家的 action 差异

### 8.5 预期 Phase 划分

基于现有数据（1 episode, 720 steps）：

| Phase | Actions | 频率占比 | 优先级 |
|-------|---------|---------|--------|
| 1 | HIRE, BUY_PRODUCT, SELL | 95%+ | ⭐⭐⭐⭐⭐ |
| 2 | + Seeds | ~5% | ⭐⭐⭐ |
| 3 | + Animals | ~1% | ⭐⭐⭐ |
| 4 | + Land | <1% | ⭐⭐ |

**但需要更多数据验证这个划分是否合理。**

---

## 9. 基于 1,282 Episodes 的统计分析 (2026-08-07 + 2026-08-08)

### 9.1 数据规模

```
总 episodes: 1,282
Winner avg money: 96,227
Loser avg money: 93,182
Margin: 3,045
```

### 9.2 Market Actions 频率统计

| Action | Count | % | 累计% |
|--------|--------|---|--------|
| HIRE | 679,725 | 38.6% | 38.6% |
| SELL | 532,475 | 30.2% | 68.8% |
| BUY_PRODUCT | 461,617 | 26.2% | **95.0%** |
| BUY_SEED | 59,665 | 3.4% | 98.4% |
| BUY_ANIMAL | 20,957 | 1.2% | 99.6% |
| BUY_LAND | 5,205 | 0.3% | 99.9% |

**结论**: HIRE + SELL + BUY_PRODUCT 占 95%，是核心 action。

### 9.3 SELL 产品分布

| Product | Count | % |
|---------|-------|---|
| WHEAT | 152,116 | 28.6% |
| MILK | 112,997 | 21.2% |
| FERTILIZER | 94,629 | 17.8% |
| STRAWBERRY | 82,646 | 15.5% |
| WOOL | 62,300 | 11.7% |

### 9.4 WIN Rate 相关性

| Action | WIN% | Diff (W-L) | 优先级 |
|--------|-------|-------------|--------|
| CARROT | 87.5% | +12 | ⭐⭐⭐⭐⭐ |
| STRAWBERRY | 79.2% | +193 | ⭐⭐⭐⭐ |
| FERTILIZER (sell) | 77.4% | +225 | ⭐⭐⭐⭐ |
| FERTILIZE | 76.2% | +335 | ⭐⭐⭐⭐ |
| DIG | 73.7% | +56 | ⭐⭐⭐ |
| SHEEP | 56.4% | +658 | ⭐⭐ |
| WEST | 49.4% | -2,217 | ❌ |
| COLLECT_FERTILIZER | 49.3% | -2,653 | ❌ |

**关键发现**: 使用 FERTILIZE、DIG 的玩家 WIN% 显著更高！

### 9.5 最终 Phase 设计（基于数据）

#### Phase 1: Market Core (必须, 95%+)

```python
MARKET_CORE = {
    0: "HOLD",
    1: "HIRE",                  # 38.6%
    2: "SELL",                  # 30.2%  # 需要指定产品
    3: "BUY_PRODUCT_WHEAT",     # 26.2%
}
```

#### Phase 2: + Seeds & Animals (~5%)

```python
MARKET_EXTENDED = {
    4: "BUY_SEED",             # 3.4%
    5: "SELL_STRAWBERRY",      # 15.5% of SELL
    6: "SELL_MILK",           # 21.2% of SELL
    7: "BUY_ANIMAL",           # 1.2%
}
```

#### Phase 3: + High-WIN-Rate Actions

```python
HIGH_VALUE = {
    8: "FERTILIZE",            # WIN% 76.2%
    9: "DIG",                   # WIN% 73.7%
}
```

### 9.6 Farmer Actions (非 Market)

| Action | % | WIN% | 建议 |
|--------|---|------|------|
| PASS | 18.7% | 51.5% | 基础 |
| WHEAT | 10.5% | 50.7% | 基础 |
| FEED | 8.8% | ~50% | Phase 3 |
| FERTILIZE | — | 76.2% | **优先** |
| DIG | — | 73.7% | **优先** |
| CARROT | — | 87.5% | **优先** |

### 9.7 数据来源

```bash
# 解压后的目录
/data/app/sandbox/kaggle/kg-rl/data/extracted/
├── 2026-08-07/   (675 episodes)
└── 2026-08-08/   (675 episodes)
```

