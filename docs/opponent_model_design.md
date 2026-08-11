# 对手模型训练方案

## 数据结构分析

Replay JSON 结构:
- steps: 720步/场
- 每步包含2个玩家数据
- 每个玩家有 action 和 observation

## 训练流程

### Phase 1: 数据解析
从replay提取(state, action)对

### Phase 2: 特征提取
- money, market_prices, shed_contents, day, hour

### Phase 3: 动作编码
| Action ID | 含义 |
|-----------|------|
| 0 | HOLD |
| 1 | HIRE |
| 2 | SELL |
| 3 | BUY |
| 4 | PASS |

### Phase 4: 训练模型
RandomForest 或 MLP

### Phase 5: 集成环境
修改 KagricultureEnv opponent=trained

## 文件结构


## 实现步骤
1. extract.py - 解析replay
2. features.py - 特征提取
3. model.py - 训练模型
4. train_opponent.py - 批量训练
5. 修改 KagricultureEnv 支持 trained 对手
6. 重新训练 PPO
