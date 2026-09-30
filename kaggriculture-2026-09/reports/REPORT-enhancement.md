# 增强实验报告:13 个变体 + 测量系统的天花板

生成 2026-09-12 | 基线 = v37(`ahmedberatozer/more-yield-smarter-labor`,sha256 `94c1c2c0…`)

## 1. 可用杠杆盘点

v37 源码里 `DEFAULT_SETTINGS` 把 **9 个开关全设为 True**,但发布时 `_SETTINGS` 覆盖关掉了 6 个:

| 开关 | 机制(源码自带注释的归属) | v37 发布态 |
| --- | --- | --- |
| hand_align | 把 hands 补齐/截断到真实工人数(fieldbook_logic) | 开 |
| weed_repair | DIG 挡住 PLANT/BUILD 的杂草(tetsutani) | 开 |
| sell_lead | 提前一步卖出下一回合的货(fieldbook `_lead_sale`) | 开 |
| front_run | 抢在对手计划卖出之前卖(需 opponent_plan) | **关** |
| budget_guard | 为每个 72 步区块的采购备钱(six_day_budget_guard.hpp) | **关** |
| room_guard | 23 点把仓库压到 ≤99(tetsutani) | **关** |
| clamp_sells | 把 SELL 数量夹到投影库存(tetsutani) | **关** |
| dead_stock | 卖掉路线永远不会卖的库存(tetsutani) | **关** |
| terminal_liquidation | step≥718 清空投影库存(fieldbook `_terminal_sale`) | **关** |

数值超参:`block_turns=72`、`min_sell_price=2`、`shed_capacity=100`、`max_orders=10`。

## 2. 第一轮:6 个开关逐个翻回来(vs v37 基线,30 种子 × 正反座位 = 60 局)

| 变体 | W | L | T | 胜率 | 95% CI | 判定 |
| --- | --- | --- | --- | --- | --- | --- |
| **on_clamp_sells** | **48** | 10 | 2 | **81.7%** | 70.1-89.4 | ✅ 真增强 |
| on_front_run | 5 | 5 | 50 | 50.0% | 37.7-62.3 | 惰性(不触发) |
| on_terminal_liquidation | 2 | 2 | 56 | 50.0% | 37.7-62.3 | 惰性(不触发) |
| on_dead_stock | 17 | 41 | 2 | 30.0% | 19.9-42.5 | ❌ 有害 |
| on_room_guard | 9 | 51 | 0 | 15.0% | 8.1-26.1 | ❌ 有害 |
| on_all(6 个全开) | 2 | 58 | 0 | 3.3% | 0.9-11.4 | ❌ 灾难 |
| on_budget_guard | 0 | 56 | 4 | 3.3% | 0.9-11.4 | ❌ 灾难 |

**作者关掉 budget_guard / room_guard / dead_stock 是对的**(实测 3%–15% 胜率)。
**但关掉 clamp_sells 是错的** —— 打开后对孪生基线 48:10。

`clamp_sells` 的实现(`_clamp_sells`)是 tetsutani 的机制:逐个 SELL 订单把数量夹到
"投影库存"的滚动余额(被前面的 BUY_PRODUCT/BUY_ANIMAL 补充),并把夹到 0 的订单
**保留占位**以维持 market slot 的 lockstep 顺序。

⚠️ 但要看清它的量级:**中位边际 +6 金币**,均值 +77。它是市场 lockstep 的微调,
专在近乎平局的镜像对局里翻盘 —— 而天梯上大量对手是同族近亲,这类对局恰好决定评分。

## 3. 第二轮:数值超参 + 组合(vs 新冠军 v37+clamp,25 种子 × 正反 = 50 局)

| 变体 | W | L | T | 胜率 | 中位边际 |
| --- | --- | --- | --- | --- | --- |
| min_sell_price = 1 / 3 / 5 | 3/3/2 | 3/3/2 | 44/46/46 | 50.0% | +0 |
| block_turns = 48 / 120 | 0 | 0 | 50 | 50.0% | +0 |
| clamp + front_run | 7 | 7 | 36 | 50.0% | +0 |
| clamp + terminal_liquidation | 2 | 2 | 46 | 50.0% | +0 |

**全部完全惰性**(50 局里 44-50 局不分胜负,中位边际恒为 0)。
说明这些旋钮在当前对局里根本不触发,或对结果无影响。

⇒ **v37 在我们能翻的旋钮上已经是局部最优。** 继续调参没有收益。

## 4. 测量系统撞到天花板(关键限制)

我搭了 8 对手的多样化面板(0911-simple / v36 / v109 / 0909-base / tetsutani /
aurax7 / nusrati / prvsiyan,每个 16 局 × 2 座位 = 128 局):

| 候选 | 面板胜率 | 平均边际 |
| --- | --- | --- |
| v37 基线 | **100.0%**(128/128) | — |
| v37 + clamp_sells | **100.0%**(128/128) | — |

两个版本都全胜 ⇒ **面板已饱和,无法区分 v37 级别的强弱**。
本地唯一还能分辨的是"孪生 A/B"(同代码微改),而孪生 A/B 衡量的是镜像竞速,
不能保证迁移到天梯。

### 尝试过的补救:从第一名 replay 造"记录型对手"(失败)

思路:replay 里有双方 720 步完整动作,可以把 rank1/rank2 的动作序列原样重放成对手,
从而得到 3000 分级别的本地对手。实测:

| 实验 | 结果 |
| --- | --- |
| v37 vs 重放版 Majkel1337(rank1) | 174,155 : **9,358** |
| 对 Majkel1337 计划做 hand_align + 库存夹取修补 | 仍然 **9,358** |
| **两个记录型对手互相对打**(应复现原局 103,912 / 108,580) | **37,064 / 12,487 —— 复现失败** |

结论:replay 里 `configuration.seed` 为 null、`info.seed` 无法复现原世界;而且记录的动作
依赖原局的现金/工人数,一旦分歧就级联失效。**这条"精英对手"路线在本数据上不可用。**

## 5. 结论:增强该怎么做

- **廉价杠杆已挖尽**:13 个变体只有 1 个(clamp_sells)是真增强,幅度是"镜像竞速的毫厘之争"
- **加深还需结构性改动**,候选方向:
  1. **磁带移植**:0911 的新 14 条磁带 × v37 的规则栈(两者本质互补:v37 = 老磁带+厚规则,0911 = 新磁带+零规则)
  2. **填 `front_run` 的坑**:该钩子存在但惰性,因为 `self.opponent_plan` 从未被赋值。用公开信息预测对手卖出时点 = 已铺好管线但没人用
  3. **换方案选择器**:现在是"前两个 shop → 计划",可用公开状态(价格/库存/对手可见状态)学习式选择(nusrati 的 `model.json` 是决策树样例)
  4. **磁带局部搜索**:2.3 秒/局,可对卖出时点做爬山
- **测量必须换仪器**:本地面板饱和 + 记录对手不可用 ⇒ **唯一还能分辨的是天梯本身**。
  而这正好可以用规则的"追踪最新 2 个提交"来做一次干净 A/B:
  同时提交 2 个全新提交(同一天、同环境、同收敛曲线),直接比较两者的评分轨迹。

## 复现

```bash
.venv/bin/python scripts/make_variants.py data/league/more-yield/main.py data/variants --all-off-flags
.venv/bin/python scripts/versus.py <变体>/main.py <基线>/main.py --seeds 30   # 交替座位 A/B
.venv/bin/python scripts/panel.py <候选>/main.py --seeds 8                    # 8 对手面板
.venv/bin/python scripts/league.py --seeds 6                                  # round-robin
```
