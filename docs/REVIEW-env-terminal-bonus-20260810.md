## Code Review — env-terminal-bonus

### 审查文件
- `docs/CHANGE_SPEC-env-terminal-bonus-20260810.md` (新增)
- `src/envs/kagriculture_env.py` (修改 step() 中 if done 分裂)

### P0 问题 ❌
- (无新增)

### P1 问题 ⚠️
- (无新增)

#### P0/P1 checklist 逐项核对
| # | 检查项 | 结果 |
|---|---|---|
| P0-1 | Reward Hacking | ✓ **修复的就是 reward hacking 类问题**——把 truncated 当成 terminated 是经典的"利用终止条件骗奖励" |
| P0-2 | 崩溃风险 | 无影响 — 改 if 分支结构, 无新代码路径 |
| P0-3 | 非法 Action | 无影响 |
| P0-4 | 无限循环 | 无影响 |
| P0-5 | 内存泄漏 | 无影响 |
| P0-6 | 梯度爆炸 | 实际上可能 **降低** 风险——±10/-5 大幅度奖励消失, value_loss 应该更稳 |
| P1-1 | 逻辑错误 | ✓ 修复的就是 P1-1 类型 bug (conflated semantics: terminated == truncated) |
| P1-2 | Observation Bug | 无影响 |
| P1-3 | 硬编码魔数 | `10.0`/`-5.0` 仍是魔数, 但本次修复不引入新的. 保留 |
| P1-4 | 副作用 | ✓ 在 truncated 分支显式 `self._won = False`, 文档化了行为 |
| P1-5 | Action Mask 遗漏 | 无影响 |
| P1-6 | Reward Scale 不合理 | ✓ 修复方向正确——但 P0-3 (dense scale) 仍未解决 |

### P2/P3 提示 (reviewer 主动指出)
- **P2-2 命名不清**: `done` 变量名本身就有歧义 (terminated? truncated? both?), Python Gymnasium 5-tuple API 期望 `terminated` 和 `truncated` 分开返回, 当前实现是合规的, 但变量命名 `done = terminated or truncated` 容易让后续 reader 误用. 建议加注释.
- **P2-3 文档缺失**: 现有 step() 无 docstring 解释 5-tuple 各字段含义. 这次补 docstring.

### 结论
✅ **通过** — 可以进入本地评估 (Step 4 Gate 1)

### 修复后操作
- [ ] grep `if terminated:` 确认已分裂
- [ ] python scripts/test_env.py 等价 (Gate 1: 环境运行 720 步)
- [ ] smoke: 验证 truncated 路径不发放 ±10/-5
- [ ] smoke: 验证 terminated 路径仍发放 ±10/-5