# S1 实施计划：计划编译器 + 保真度闸门

立项依据：`REPORT-new-architecture-proposal.md`。本文是**可执行**的那一半：做什么、怎么验收、什么时候停。
基线仪器（已存在）：`scripts/lockstep.py`（市场复刻，0 误差）、`scripts/ab_duel.py`（配对对战，唯一有效仪器）、
`scripts/day_gap.py`（逐日流动性净值差，20 局配对实测）。

---

## 0. 为什么闸门改早（本次实施的核心修正）

用 `day_gap.py` 对 20 局配对实测：

| 对比 | 第一次转负 | 首个显著赤字日 | 分水岭 | 收官 |
|---|---|---|---|---|
| 前沿(2945-farm) vs 我们冠军 | 无（第 1–2 天 −4，其余持续小正） | **无** | 第 12 天起单边累积 | **+3,328** |
| 从零重做(plan_v0) vs 冠军 | **第 4 天 (−653)** | **第 5 天 (−719)** | **第 10 天 (−16,276，8 倍跳变)** | **−113,039（20/20 全负）** |

⇒ 从零重做的失败**在第 4–5 天注定、第 10 天兑现**；而前沿的优势不是爆发，是第 12 天起每笔多拿 ~2.8/单位。
⇒ 因此 S1 的验收不再是"60 局总量 ±5%"，而是**早期就判定**：前 9 天净值打平 + 第 10 天不跳变。

---

## 1. S1.1 参考轨迹（1 天）

**产物**：`scripts/trace_ref.py` → `data/trace/<agent>-<seed>/`。
对在榜叠加版（`data/forward/wool_drain1_outerprem/main.py`）与冠军，各在 **12 个种子**上记录逐步：
- 输入侧：observation 的 farms / private(shed, seeds, inventories) / market(inventory, prices) / town(unlocked_shops) / step；
- 输出侧：完整 action（farmer/hands/market），以及引擎应用后的实际状态（用引擎自己的 `_apply_unit_action` 语义重放校验）；
- 派生量：每步每个 unit 的位置与手持、每块 tile 的作物/动物/结构、每步市场成交单位与收入（用 lockstep 复算）。

**验收**：trace 自洽——用 lockstep 从 trace 复算的收入与引擎 money 差 ≤ 1 币/局（Task 3 已证明该复算在真实对局上 0 误差，这里只是换输入源）。

## 2. S1.2 显式表示 θ 与控制器（1 天）

`data/plan/theta.json`（人可读）+ `scripts/plan_runtime.py`（θ → action 的控制器）。
θ 的字段（每条都要能从 trace 反推）：

| 组 | 字段 | 说明 |
|---|---|---|
| 土地 | `land_days`（买地日与象限顺序） | 第 10 天跳变的关键 |
| 种植 | `plant[day][quadrant] = {crop: n}` | 逐日逐象限 |
| 浇水/施肥 | `water_rule`（作物→窗口、优先级）、`fert_rule` | 由 `max_yield_day` 窗口驱动 |
| 收获/拾取 | `harvest_rule`、`cargo_rule`（何时回仓、手货上限） | 溢出丢弃两家都是 0，必须保持 |
| 结构/放置 | `build[day] = {structure: n}`、`place_rule`（pen_min_dist、优先级） | |
| 动物 | `buy_animal[day] = {animal: n}`、`feed_rule`、`care_rule` | 今天已证不是差距来源，但必须 parity |
| 市场 | `sell[day][item] = [units...]`（分批）+ `price_gate` | 三层里的"卖出时点" |
| 价格操作 | `buy_feed[day][item]`、`hold_rule` | 三层里的"价格操作"，**最不确定** |

**控制器**：每步 = 优先级排序（收获/浇水/喂/照顾/放置/移动）+ 市场槽位分配（复用已验证的 layout 搜索）+ 现金门。

## 3. S1.3 编译与拟合（0.5–1 天）

`scripts/compile_plan.py`：把 trace 的每类动作归约成 θ 的对应字段（plant/water/harvest/build/place 由 tile 变化反推；buy/sell 由市场订单反推；movement 由位置序列反推并归纳成"取最近目标"规则）。
拟合后用 `scripts/fidelity.py` 重放 θ 并与参考 trace 逐步对比。

---

## 4. 闸门（每道都可判定，全部用配对对战/逐日曲线）

| 闸门 | 判据 | 成本 | 失败怎么办 |
|---|---|---|---|
| **1a 管线无损** | 直接回放 trace 的 agent 逐步 **100% 复现**冠军动作（含市场订单） | 分钟级 | 修记录/语义；不往下走 |
| **1b 早期打平** | θ agent 在 **20 镇配对**上，**前 9 天流动性净值 delta 的 |t| < 2**，且**第 10 天不出现 >3,000 的跳变落后** | ~10 分钟 | **停**，用 1c 定位缺的概念 |
| **1c 残差定位** | 输出 θ 复现不了的动作/时段清单（按动作类型×天聚合），并给出每个缺口对应的缺失概念假设 | 小时级 | 这是 S2 的输入 |
| **1d 总量** | θ agent 对冠军 60 镇配对 **delta ≥ −2%**（不要求打赢） | ~15 分钟 | 若 1b 过而 1d 不过，说明差距在中后期，回到 1c |

**S1 的产出无论成败都必须交付**：trace 仪器、θ 表示、编译器、保真度报告、残差清单（这些是可复用资产）。

## 5. S2（仅在 1b+1d 通过后开工）

按 1c 的残差清单**一次补一个概念**，每个概念一次 60 局配对（IS+OOS），直到总量 parity（delta ≥ 0 且 t ≥ 3）。
Kill：累计 ≥ 200 次配对或 3 周未过 parity ⇒ 停止，交回人类决定（兜底：收在当前在榜线）。

## 6. S3（仅在 S2 通过后）

统一参数空间上做联合搜索（组合 × 价格操作 × 卖出时点同处一个 θ），并接入 `lockstep.py` 做**滚动优化控制**（每步预算余量以数量级计：mean 0.5 ms / worst 56.5 ms）。

---

## 7. 纪律（不遵守即视为实验无效）

1. 唯一有效仪器是配对对战（对 starter 调参无效，已证）。
2. 每个变体必须报 `layer_fallbacks == 0` 且参数不同必须行为不同（**逐字节相同的结果 = bug 签名**）。
3. 计划改动可能翻转第 6 天商店抽取（RNG 与杂草共用）⇒ 只能整局配对，不能筛选。
4. 不 churn 提交；只有对**当前在榜线** 60 局 IS+OOS 过 t ≥ 3 才消耗配额。
5. 不改在榜文件；新架构全部在 `data/plan/` 与 `data/theta/` 下构建。
