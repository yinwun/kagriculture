## Code Review — env-won-reset

### 审查文件
- `docs/CHANGE_SPEC-env-won-reset-20260810.md` (新增)
- `src/envs/kagriculture_env.py` (修改, +1 行)

### P0 问题 ❌
- (无)

### P1 问题 ⚠️
- (无)

#### P0/P1 checklist 逐项核对
| # | 检查项 | 结果 |
|---|---|---|
| P0-1 | Reward Hacking | 无影响 — `_won` 不参与 reward 计算路径 |
| P0-2 | 崩溃风险 | 无影响 — 纯状态初始化 |
| P0-3 | 非法 Action | 无影响 — 与 action 生成无关 |
| P0-4 | 无限循环 | 无影响 |
| P0-5 | 内存泄漏 | 无影响 |
| P0-6 | 梯度爆炸 | 无影响 |
| P1-1 | 逻辑错误 | ✓ 修复的就是 P1-1 类型的 bug (stale state across episodes) |
| P1-2 | Observation Bug | 无影响 |
| P1-3 | 硬编码魔数 | 无影响 |
| P1-4 | 副作用 | ✓ `reset()` 本就该重置所有 episode-level 状态, `_won` 属于此范畴 |
| P1-5 | Action Mask 遗漏 | 无影响 (与 action masking 无关) |
| P1-6 | Reward Scale 不合理 | 无影响 |

### P2/P3 提示 (reviewer 主动指出)
- **P2-4 过度复杂**: `reset()` 现在 22 行, 包括 super().reset, _init_kaggle_env, kaggle_env.reset, raw_obs获取, 4 个状态重置, prev_money, _process_observation, return. 接近 50 行阈值但未超. 不属于本次修复范围.
- **P3-3 文档缺失**: `reset()` 没有 docstring 说明它重置哪些状态. 这次顺手补一下 docstring (作为 reviewer 建议).

### 结论
✅ **通过** — 可以进入本地评估 (Step 4 Gate 1)

### 修复后操作
- [ ] grep `self._won = False` src/envs/kagriculture_env.py 确认有2处 (init + reset)
- [ ] python scripts/test_env.py (Gate 1: 环境运行 720 步)
- [ ] 短期 smoke: python -c "short rollout, assert info['won'] is False after first reset()"