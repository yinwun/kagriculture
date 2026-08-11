# Kagriculture RL — 设计文档

> 用强化学习训练 Kagriculture 农业 agent，目标进入 Kaggle top 5

---

## 📋 文档结构

| 文档 | 内容 |
|------|------|
| [01-DESIGN-SPEC.md](./01-DESIGN-SPEC.md) | 总体设计规范、算法选型 |
| [02-OBSERVATION-SPACE.md](./02-OBSERVATION-SPACE.md) | Observation 空间设计 |
| [03-ACTION-SPACE.md](./03-ACTION-SPACE.md) | Action 空间设计 (基于统计数据) |
| [04-REWARD-DESIGN.md](./04-REWARD-DESIGN.md) | Reward 函数设计 |
| [05-DATA-MANAGEMENT.md](./05-DATA-MANAGEMENT.md) | 每日数据下载与管理 |
| [06-ACTION-SPACE-REFERENCE.md](./06-ACTION-SPACE-REFERENCE.md) | Action 统计参考 (1,282 episodes) |

---

## 🚀 快速开始

### 1. 环境配置

```bash
# 激活 conda 环境
source /data/app/miniconda3/bin/activate kaggle

# 验证依赖
python scripts/test_env.py
```

### 2. 测试环境

```bash
cd /data/app/sandbox/kaggle/kg-rl
python scripts/test_env.py
```

### 3. 训练 (Phase 1: 10M steps)

```bash
python scripts/train.py --total_steps 10000000
```

---

## 📁 项目目录结构

```
/data/app/sandbox/kaggle/kg-rl/
├── .claude/                      # Claude AI 配置
│   ├── CLAUDE.md
│   └── WORKFLOW.md               # 开发流程 (必须 follow)
│
├── docs/                         # 设计文档
│   ├── 01-DESIGN-SPEC.md
│   ├── 02-OBSERVATION-SPACE.md
│   ├── 03-ACTION-SPACE.md
│   ├── 04-REWARD-DESIGN.md
│   ├── 05-DATA-MANAGEMENT.md
│   └── 06-ACTION-SPACE-REFERENCE.md
│
├── data/                         # 数据目录
│   ├── kagriculture-episodes-*.zip
│   └── extracted/               # 解压后数据
│       ├── 2026-08-07/
│       └── 2026-08-08/
│
├── src/                         # 代码
│   ├── envs/
│   │   └── kagriculture_env.py  # ✅ Gymnasium 环境 (已实现)
│   ├── models/
│   │   └── policy.py            # ✅ Policy Network (已实现)
│   ├── algos/
│   │   └── ppo.py               # ✅ PPO Agent (已实现)
│   └── utils/
│
├── scripts/                     # 脚本
│   ├── train.py                 # ✅ 训练入口 (已实现)
│   ├── test_env.py              # ✅ 环境测试 (已验证)
│   └── eval.py                  # ⬜ 评估入口
│
├── configs/                     # 配置文件
│   └── wheat_only.yaml          # ✅ Phase 1 配置
│
├── models/                      # 保存的模型
│
└── logs/                       # 训练日志
```

---

## 📊 当前状态

### ✅ 已完成

| 模块 | 状态 | 说明 |
|------|------|------|
| 环境注册 | ✅ | Kagriculture (kaggriculture 拼写) |
| KagricultureEnv | ✅ | Gymnasium wrapper，32-dim obs |
| Policy Network | ✅ | SimplePolicy, 128 hidden dim |
| PPO Agent | ✅ | 基于 Stable Baselines3 |
| 测试脚本 | ✅ | 720 steps 完整 episode 通过 |
| Phase 1 Actions | ✅ | 5 actions: HOLD/HIRE/SELL_WHEAT/BUY_WHEAT/PASS |

### ⬜ 待实现

| 模块 | 说明 |
|------|------|
| Action Masking | 禁止非法 action |
| 评估脚本 | 对比 baseline |
| Observation 扩展 | 加入更多 market/farm 信息 |
| Phase 2 Actions | + Seeds/Animals |

---

## 📈 Phase 设计 (基于数据)

### Phase 1: Market Core (95%+)
- 4 actions: HOLD, HIRE, SELL_WHEAT, BUY_PRODUCT_WHEAT
- ✅ 已实现

### Phase 2: + Seeds/Animals (~99%)
- +8 actions: BUY_SEED, SELL_STRAWBERRY, SELL_MILK, BUY_ANIMAL
- ⬜ 待实现

### Phase 3: + High-WIN-Rate Actions
- +3 actions: FERTILIZE (76% WIN), DIG (74% WIN), SELL_FERTILIZER (77% WIN)
- ⬜ 待实现

---

## 🔧 开发流程

所有开发必须 follow `WORKFLOW.md`:

```
代码修改 → Code Review → 修复 P0/P1 → 本地评估 → 训练
```

### 评估标准 (Gate 3)

| 条件 | 通过标准 |
|------|----------|
| Win rate vs random | > 50% |
| Win rate vs heuristic | > 40% |
| Win rate vs v22 | > 30% (optional) |

---

## 📚 参考资料

- [Orbit Wars 1st Place](https://github.com/IsaiahPressman/kaggle-orbit-wars)
- [Orbit Wars 2nd Place](https://github.com/SimJeg/orbit-wars)
- [Stable Baselines3](https://stable-baselines3.readthedocs.io/)
- [PPO Paper](https://arxiv.org/abs/1707.06347)

---

## ⚠️ 已知问题

1. **Kaggle 拼写**: 环境名是 `kaggriculture` (两个 g)，不是 `kagriculture`
2. **Observation 结构**: 使用 Struct 类，字段访问方式不同于 dict
3. **Tiles 结构**: 可以是 `None`, `"LOCKED"`, 或 `dict`
4. **Private.shed**: 是 dict，直接访问 `shed.get("WHEAT")`

---

## 下一步

1. ✅ 环境验证通过
2. ⬜ 实现 action masking
3. ⬜ 短训练 (1M steps) 验证 RL 能学到东西
4. ⬜ 扩展到 Phase 2 actions
