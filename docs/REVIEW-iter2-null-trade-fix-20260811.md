## Code Review — iter2-null-trade-fix

### 审查文件
- `docs/CHANGE_SPEC-iter2-null-trade-fix-20260811.md` (新增)
- `src/envs/kagriculture_env.py` (~12 lines changed: _compute_reward + reset + __init__)

### P0 问题 ❌
- (无新增)

### P1 问题 ⚠️
- (无新增)

#### P0/P1 checklist 逐项核对
| # | 检查项 | 结果 |
|---|---|---|
| P0-1 | Reward Hacking | ✓ **修复的就是这个** — dummy trading hack |
| P0-2 | 崩溃风险 | 无影响 — 加 `farm.get("wheat", 0)` 容错 |
| P0-3 | 非法 Action | 无影响 — 非法动作的 `-0.05` 还在 |
| P0-4 | 无限循环 | 无影响 |
| P0-5 | 内存泄漏 | 无影响 — `self._prev_wheat` 是标量属性 |
| P0-6 | 梯度爆炸 | 无影响 — 仍是 clip ±3 |
| P1-1 | 逻辑错误 | ✓ 修复的就是这类 (counter reset 太宽)|
| P1-2 | Observation Bug | 无影响 — 不改 obs |
| P1-3 | 硬编码魔数 | 无影响 |
| P1-4 | 副作用 | ⚠️ `farm.get("wheat", 0)` 假设 wheat 字段存在。Kaggle 用 `private.shed` 而不是 `farm.wheat`。**待 verify** |
| P1-5 | Action Mask 遗漏 | 无影响 |
| P1-6 | Reward Scale 不合理 | 无影响 |

### ⚠️ P1-4 副作用警告

Spec 里 `current_wheat = farm.get("wheat", 0)` 是基于猜测 Kaggle 把 wheat 存在 `farm.wheat` 里。**实际可能** wheat 是在 `raw_obs.private.shed["WHEAT"]` 或者 `farm.shed["WHEAT"]`。

**Fix**: 在 apply 前先 verify，用 Kaggle debug 数据（30 步 BUY 测试已经跑过）+ 读 Kaggle agent sample。

### P2/P3 提示
- **P2-1 代码重复**: Phase 2 spec + Iter 2 spec 都在改 `_compute_reward`。考虑是否合并。
- **P3-1 风格**: 加 `_prev_wheat` 与 `_prev_opp_money` 命名一致 ✓

### 结论
⚠️ **有条件通过** — 必须先 verify `farm.get("wheat", 0)` 实际返回什么字段。 如果 Kaggle 用 `private.shed["WHEAT"]`，需要把 `current_wheat = farm.get("wheat", 0)` 改成 `current_wheat = raw_obs.private.shed.get("WHEAT", 0)`。

### 修复后操作
- [ ] debug 验证：`current_wheat` 应该从哪个字段读取
- [ ] grep `wheat` 在 Kaggle env source（或 step 输出）确认
- [ ] python smoke: 30 步 trade 测试，确认 wheat_d 检测到变化
- [ ] python -c "from src.envs.kagriculture_env import KagricultureEnv; e = KagricultureEnv(); obs, _ = e.reset(); print(obs.shape)"
- [ ] 启动 Iter 2 loop
- [ ] 检查 iter 1 money trajectory 是否变化（不是 $3,000 平线）