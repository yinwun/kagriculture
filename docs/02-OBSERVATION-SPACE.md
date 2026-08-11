# Observation Space 详细设计

> 本文档详细定义 Kagriculture RL 的 observation space

---

## 1. Kagriculture 环境状态

### 1.1 游戏基本参数

```python
GAME_CONFIG = {
    "episode_steps": 720,      # 30 days × 24 turns
    "starting_money": 3000,
    "shed_capacity": 100,
    "board_size": 10,          # 10x10 grid per farm
    "max_market_orders": 10,
}
```

### 1.2 状态来源

Kagriculture 的 observation 来自两部分：

1. **Public State** — 双方都能看到
   - step, day
   - market prices/inventory
   - public tiles

2. **Private State** — 只有自己能看
   - shed inventory
   - hired hands
   - 具体作物种植时间

---

## 2. Phase 1: Simplified Observation

```python
SimplifiedObs = {
    # === 全局 (4 dims) ===
    "step": Float,           # 0-719, normalized to 0-1
    "day": Float,             # 0-29, normalized to 0-1
    "left": Float,            # 剩余步数, normalized
    "money": Float,          # 当前金钱, / 100000
    
    # === Market - WHEAT (4 dims) ===
    "wheat_price": Float,     # 当前价格
    "wheat_inventory": Float, # 自己库存
    "wheat_market_inv": Float, # 市场库存
    "wheat_price_delta": Float, # 价格变化趋势
    
    # === Market - Other (6 dims) ===
    "melon_price": Float,
    "strawberry_price": Float,
    "fertilizer_price": Float,
    "milk_price": Float,
    "wool_price": Float,
    "egg_price": Float,
    
    # === Farm Summary (5 dims) ===
    "plantable_tiles": Float, # 可种植格子
    "plants_ready": Float,      # 可收获作物
    "cow_count": Float,
    "sheep_count": Float,
    "unfed_animals": Float,
    
    # === Operations (3 dims) ===
    "hands": Float,           # 当前 hands
    "hires_left": Float,      # 今天还能 hire 几次
    
    # === 对手估算 (2 dims) ===
    "opponent_tile_count": Float,  # 从 public tiles 估算
    "opponent_money_est": Float,  # 估算对手金钱
}

# Total: ~24 dims
```

### 2.1 归一化参数

```python
NORMALIZATION = {
    "step": (0, 720),
    "day": (0, 30),
    "left": (0, 720),
    "money": (0, 100000),  # 假设最大 100k
    "wheat_inventory": (0, 10000),
    "wheat_market_inv": (0, 20000),
    # ...
}
```

---

## 3. Phase 2: Extended Observation

```python
ExtendedObs = {
    # === Global (5 dims) ===
    "step": Float,
    "day": Float,
    "left": Float,
    "money": Float,
    "money_delta": Float,      # 新增：金钱变化
    
    # === Market - All Products (21 dims) ===
    # WHEAT (4)
    "wheat_price": Float,
    "wheat_inventory": Float,
    "wheat_market_inv": Float,
    "wheat_price_delta": Float,
    
    # MELON (4)
    "melon_price": Float,
    "melon_inventory": Float,
    "melon_market_inv": Float,
    "melon_price_delta": Float,
    
    # STRAWBERRY (4)
    "strawberry_price": Float,
    "strawberry_inventory": Float,
    "strawberry_market_inv": Float,
    "strawberry_price_delta": Float,
    
    # OTHER (5)
    "fertilizer_price": Float,
    "milk_price": Float,
    "wool_price": Float,
    "egg_price": Float,
    "carrot_price": Float,
    
    # === Farm Grid (100 dims) ===
    # 10x10 grid, 每个格子 1 dim (tile state)
    "tile_states": FloatTensor,  # shape (100,)
    
    # === Animal Status (4 dims) ===
    "cow_count": Float,
    "sheep_count": Float,
    "unfed_cows": Float,
    "unfed_sheep": Float,
    
    # === Operations (5 dims) ===
    "hands": Float,
    "hires_left": Float,
    "shed_used": Float,
    "shed_capacity": Float,
    "hired_today": Float,
    
    # === 对手 (3 dims) ===
    "opponent_tile_count": Float,
    "opponent_money_est": Float,
    "opponent_hands_est": Float,
}

# Total: ~142 dims
```

---

## 4. Phase 3: Full Observation

```python
FullObs = {
    # === Global (6 dims) ===
    "step": Float,
    "day": Float,
    "hour": Float,          # 0-23
    "left": Float,
    "money": Float,
    "money_delta": Float,
    
    # === Market (28 dims) ===
    # 每个 product: price, inventory, market_inv, price_delta (7 products)
    "wheat": {...},
    "melon": {...},
    "strawberry": {...},
    "carrot": {...},
    "tomato": {...},
    "milk": {...},
    "egg": {...},
    "wool": {...},
    "fertilizer": {...},
    
    # === Private State (15 dims) ===
    "shed": {
        "wheat": Float,
        "melon": Float,
        "strawberry": Float,
        "carrot": Float,
        "tomato": Float,
        "milk": Float,
        "egg": Float,
        "wool": Float,
        "fertilizer": Float,
    },
    "hands": Float,
    "hires_left": Float,
    "hired_today": Float,
    "shed_used": Float,
    "shed_capacity": Float,
    
    # === Farm Grid (10x10 = 100 dims) ===
    "tiles": FloatTensor,  # shape (10, 10)
    
    # === Crop Details (per planted crop) ===
    "crop_details": [
        # 每种 crop 的详细信息
        {"type": "melon", "tile": (x,y), "planted_day": d, "yield": y},
        ...
    ]
    
    # === Animal Details (4 dims per animal type) ===
    "animals": {
        "cow": {"count": n, "unfed": u, "yield": y},
        "sheep": {"count": n, "unfed": u, "yield": y},
        "goose": {"count": n, "unfed": u, "yield": y},
    }
    
    # === Opponent Estimation (5 dims) ===
    "opponent": {
        "tile_count": Float,
        "tile_types": FloatTensor,  # 估算对手种了什么
        "money_est": Float,
        "hands_est": Float,
    }
}

# Total: ~200+ dims
```

---

## 5. Observation Processor

```python
class ObservationProcessor(nn.Module):
    """处理 raw observation 到 neural network 输入"""
    
    def __init__(self, obs_dim, hidden_dim=256):
        super().__init__()
        
        self.encoder = nn.Sequential(
            nn.Linear(obs_dim, hidden_dim),
            nn.LayerNorm(hidden_dim),
            nn.ReLU(),
            nn.Linear(hidden_dim, hidden_dim),
            nn.LayerNorm(hidden_dim),
            nn.ReLU(),
        )
    
    def forward(self, obs: dict) -> torch.Tensor:
        # 1. 提取数值特征
        features = []
        for key, value in obs.items():
            if isinstance(value, (int, float)):
                features.append(self.normalize(value, key))
            elif isinstance(value, np.ndarray):
                features.append(torch.tensor(value).flatten())
        
        # 2. concatenate
        x = torch.cat(features)
        
        # 3. encode
        return self.encoder(x)
    
    def normalize(self, value, key):
        """根据 key 归一化"""
        bounds = NORMALIZATION.get(key, (0, 1))
        normalized = (value - bounds[0]) / (bounds[1] - bounds[0])
        return torch.tensor(normalized, dtype=torch.float32)
```

---

## 6. 实现检查清单

- [ ] 实现 SimplifiedObs (24 dims)
- [ ] 实现 ExtendedObs (142 dims)
- [ ] 实现 FullObs (200+ dims)
- [ ] 实现 ObservationProcessor
- [ ] 验证 observation shape 正确
- [ ] 验证归一化正确
