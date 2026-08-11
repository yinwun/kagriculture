## Code Review — env-dense-reward-scale

### 审查文件
- `docs/CHANGE_SPEC-env-dense-reward-scale-20260810.md` (新增)
- `src/envs/kagriculture_env.py:_compute_reward()` (改 divisor: 1000 → 10000)

### P0 问题 ❌
- (无新增)

### P1 问题 ⚠️
- (无新增)

#### P0/P1 checklist 逐项核对
| # | 检查项 | 结果 |
|---|---|---|
| P0-1 | Reward Hacking | ✓ **修复的就是 reward hacking 类问题**——dense magnitude 让 agent 用 money-making hack 取代 winning |
| P0-2 | 崩溃风险 | 无影响 — 改数字常量 |
| P0-3 | 非法 Action | 无影响 |
| P0-4 | 无限循环 | 无影响 |
| P0-5 | 内存泄漏 | 无影响 |
| P0-6 | 梯度爆炸 | ✓ **降低** 风险——target variance 减小, value_loss 应更平滑 |
| P1-1 | 逻辑错误 | ✓ 修复的就是 P1-6 (reward scale 不合理) |
| P1-2 | Observation Bug | 无影响 |
| P1-3 | 硬编码魔数 | 注意: `10000.0` 仍是魔数, 但比 `1000.0` 合理. 后续可加常量 `DENSE_REWARD_DIVISOR = 10000` |
| P1-4 | 副作用 | 无影响 |
| P1-5 | Action Mask 遗漏 | 无影响 |
| P1-6 | Reward Scale 不合理 | ✓ **正在修复**——本次的核心改动 |

### P2/P3 提示 (reviewer 主动指出)
- **P3-1 风格**: `_compute_reward` 没有 docstring 说明 reward 公式, 这次顺手补一行
- **P2-1 代码重复**: `if self.reward_type == "dense": ... elif self.reward_type == "sparse": ... else: ...` 三分支其实 dense 和 else 一样, 可以简化为 `if self.reward_type == "sparse": reward = 0 else: reward = money_delta / 10000`. 但不属于本次必改范围

### 结论
✅ **通过** — 可以进入本地评估 (Step 4 Gate 1)

### 修复后操作
- [ ] grep `money_delta / 10000.0` 确认改对
- [ ] python scripts/test_env.py 等价 (Gate 1: env 仍能跑 720 步)
- [ ] 短期 smoke: 验证 dense reward magnitude 下降
- [ ] 配套建议: 启动1M steps重训 (此改动要等数据验证, 但代码 review pass)