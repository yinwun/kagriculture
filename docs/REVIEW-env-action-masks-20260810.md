## Code Review — env-action-masks

### 审查文件
- `docs/CHANGE_SPEC-env-action-masks-20260810.md` (新增)
- `src/envs/kagriculture_env.py` (新增 `action_masks()` 方法 + `info["action_mask"]` 字段)

### P0 问题 ❌
- (无)

### P1 问题 ⚠️
- (无新增)

#### P0/P1 checklist 逐项核对
| # | 检查项 | 结果 |
|---|---|---|
| P0-1 | Reward Hacking | 无影响 — 不改 reward 计算 |
| P0-2 | 崩溃风险 | ⚠️ **微风险**: `action_masks()` 在 reset() 之前调用时 `self._kaggle_env.state[0]` 会失败。需要在调用前 lazy-init. 建议加 guard |
| P0-3 | 非法 Action | ✓ **修复的就是这个方向** — 让 action mask 标准暴露, 让 MaskablePPO 可用 |
| P0-4 | 无限循环 | 无影响 |
| P0-5 | 内存泄漏 | 无影响 — 每次调用新建 mask 数组, 但 ~50 bytes, 720 steps × 4 ep/s = ~1.5 KB/s, 可忽略 |
| P0-6 | 梯度爆炸 | 无影响 |
| P1-1 | 逻辑错误 | ⚠️ 需要 verify: `_is_action_valid(0, ...)` 永远 True (HOLD), `_is_action_valid(4, ...)` 永远 True (PASS). 检查 mask 不能把这两个 mask 成 0 |
| P1-2 | Observation Bug | 无影响 |
| P1-3 | 硬编码魔数 | 无影响 |
| P1-4 | 副作用 | ⚠️ 调用 `action_masks()` 多次会重复 lazy-init `_kaggle_env`，但幂等（`if None`），无影响 |
| P1-5 | Action Mask 遗漏 | ✓ **正在修复** |
| P1-6 | Reward Scale 不合理 | 无影响 |

### P2/P3 提示
- **P2-5 GPU 利用率低**: 与本改动无关, 单独 spec
- **P3-1 风格**: `action_masks()` 应该在 `_is_action_valid` 后面紧跟，签名符合 Gymnasium 约定 ✓
- **P2-3 文档缺失**: 已加 docstring

### 结论
⚠️ **有条件通过** — 必须加 `self._init_kaggle_env()` guard 在 `action_masks()` 顶部 (P0-2 提到的 crash 风险)

### 修复后操作
- [ ] grep `def action_masks` 确认定义
- [ ] grep `action_mask` 在 info dict 里
- [ ] python smoke:
  - reset 之后立即调用 `env.action_masks()` 不 crash
  - HIRE / SELL / BUY 在没钱 / 没小麦 / 没货时 mask=0
  - HOLD / PASS 永远 mask=1
  - `info["action_mask"]` 在 step() 返回值中可用
- [ ] 1 完整 720 步 episode 跑通