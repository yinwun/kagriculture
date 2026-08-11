## Code Review — phase1-random-curriculum

### 审查文件
- `docs/CHANGE_SPEC-phase1-random-curriculum-20260811.md` (新增)
- `scripts/train.py` (2 lines changed)
- `scripts/eval_loop.py` (1 line added in subprocess call + argparse)

### P0 问题 ❌
- (无新增)

### P1 问题 ⚠️
- (无新增)

#### P0/P1 checklist 逐项核对
| # | 检查项 | 结果 |
|---|---|---|
| P0-1 | Reward Hacking | 无影响 — 不改 reward 计算 |
| P0-2 | 崩溃风险 | 无影响 — 改两个默认值 |
| P0-3 | 非法 Action | 无影响 — ent_coef 0.04 不会让 invalid 动作变多 |
| P0-4 | 无限循环 | 无影响 |
| P0-5 | 内存泄漏 | 无影响 |
| P0-6 | 梯度爆炸 | ⚠️ ent_coef 0.04 比 0.01 高 4×，可能略增梯度噪声。但 SB3 PPO 默认上限 0.05+，0.04 在安全区 |
| P1-1 | 逻辑错误 | 无影响 |
| P1-2 | Observation Bug | 无影响 |
| P1-3 | 硬编码魔数 | ✓ 把 0.01 改成 0.04 反而减少魔数感（更接近 SB3 默认） |
| P1-4 | 副作用 | 无影响 — argparse default 只在用户没传时生效 |
| P1-5 | Action Mask 遗漏 | 已知未改进 (Phase 3 才会做 MaskablePPO 切换) |
| P1-6 | Reward Scale 不合理 | 不涉及 (Phase 2 才会动 reward) |

### P2/P3 提示 (reviewer 主动指出)
- **P2-3 文档缺失**: 改默认值后，`TRAINING_SPEC.md` 的 PPO 超参表需要同步更新（merge 后做）
- **P3-1 风格**: 两个 default 在相邻行，无大碍

### 结论
✅ **通过** — 可以进入本地评估 (Step 4 Gate 1)

### 修复后操作
- [ ] grep `default="random"` 在 train.py 确认改动
- [ ] grep `default=0.04` 在 train.py 确认 ent_coef
- [ ] eval_loop 把 `--ent_coef` 加到 subprocess cmd
- [ ] eval_loop argparse 加 `--ent_coef`
- [ ] 在 GPU 1 上启动训练（不干扰 GPU 0 的 running loop）
- [ ] 监控 `log/eval_loop_phase1.log` 和 `eval_reports/iter_NN_*/train_log/train.stdout`
- [ ] iter 1 完成看 `summary.json` 的 trade_frac