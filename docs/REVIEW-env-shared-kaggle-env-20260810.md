## Code Review — env-shared-kaggle-env

### 审查文件
- `docs/CHANGE_SPEC-env-shared-kaggle-env-20260810.md` (新增)
- `src/envs/kagriculture_env.py:__init__` (新增可选参数 `kaggle_env`)
- `scripts/train.py:_run` (新增 shared_kaggle_env 创建并注入)

### P0 问题 ❌
- (无新增)

### P1 问题 ⚠️
- **P1-4 副作用** ⚠️: `close()` 当前设 `self._kaggle_env = None`。如果两个 env 共享同一引用，调用 `train_env.close()` 会把 eval_env 的 kaggle_env 也清掉。需要让 `close()` 只清"自己创建的"实例, 不清注入的。

#### P0/P1 checklist 逐项核对
| # | 检查项 | 结果 |
|---|---|---|
| P0-1 | Reward Hacking | 无影响 — 共享 env 不改 reward 计算 |
| P0-2 | 崩溃风险 | ⚠️ 共享 mutable state, 必须保证 train / eval 串行调用 (SB3 保证) |
| P0-3 | 非法 Action | 无影响 |
| P0-4 | 无限循环 | 无影响 |
| P0-5 | 内存泄漏 | ✓ 改进 — 共享一个 kaggle_env 比创建两个更省内存 |
| P0-6 | 梯度爆炸 | 无影响 |
| P1-1 | 逻辑错误 | 无影响 — 只是注入可选参数 |
| P1-2 | Observation Bug | 无影响 |
| P1-3 | 硬编码魔数 | 无影响 |
| P1-4 | 副作用 | ⚠️ **必须修** — `close()` 需要区分"自己创建"和"外部注入", 已在 P1 列出 |
| P1-5 | Action Mask 遗漏 | 无影响 |
| P1-6 | Reward Scale 不合理 | 无影响 |

### P2/P3 提示
- **P2-3 文档缺失**: `__init__` 没 docstring 说明 `kaggle_env` 参数. 顺手补一行
- **P3-1 风格**: 公共 API 新增参数, 应该有 backward-compat default (`None`)

### 结论
⚠️ **有条件通过** — 必须同时修 P1-4 (close() 不能破坏共享引用) 才能进 Gate 1

### 修复后操作
- [ ] grep `kaggle_env` 确认注入路径生效
- [ ] `close()` 行为: 用 `_owns_kaggle_env` flag 区分
- [ ] python smoke: train/eval 两个 env 共用, 关一个不影响另一个
- [ ] python scripts/test_env.py 等价 Gate 1