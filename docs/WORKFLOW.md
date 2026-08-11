# Development Workflow — RL Agent Development

> 这是 kg-rl 项目的标准开发流程。每个 session 都应 follow 这个流程。
> **任何代码改动都必须经过这个流程才能进行正式训练。**

---

## 流程概览

```
┌─────────────────────────────────────────────────────────────────┐
│  Step 1: 代码修改                                                 │
│  (Code Change)                                                   │
└────────────────────────┬────────────────────────────────────────┘
                         ▼
┌─────────────────────────────────────────────────────────────────┐
│  Step 2: Code Review                                             │
│  (Reviewer 检查 P0/P1 问题)                                       │
└────────────────────────┬────────────────────────────────────────┘
                         ▼
              ┌──────────────────────┐
              │ 有 P0/P1 问题？       │
              └──────────┬───────────┘
                    YES  │  NO
         ┌───────────────┘  │
         ▼                  ▼
┌─────────────────┐  ┌─────────────────────────────────────────┐
│  Step 3: 修复    │  │  Step 4: 本地评估                        │
│  (Fix Issues)   │  │  (Local Evaluation)                     │
└────────┬────────┘  └───────────────┬─────────────────────────┘
         │                           │
         │  Loop until              ▼
         │  no P0/P1          ┌──────────────────────┐
         └──────────┐         │ 通过评估标准？        │
                     │         └──────────┬───────────┘
                     │              YES  │  NO
                     │   ┌───────────────┘  │
                     │   ▼                  ▼
                     │  DONE          修复问题 → Step 3
                     └─► (goto Step 2)
```

---

## Step 1: 代码修改 (Code Change)

### 规则

1. **每次只改一个模块** — 不要批量修改多个模块
2. **先写 CHANGE_SPEC 再写代码** — spec 是代码的蓝图
3. **改动必须来源于实验数据或明确的 bug** — 不允许理论推导

### 输出产物

```
docs/CHANGE_SPEC-{module}-{DATE}.md
```

### CHANGE_SPEC 模板

```markdown
# CHANGE_SPEC-{module} — {简短描述}

> **Date**: YYYY-MM-DD
> **Author**: {name}
> **Based on**: {previous version}

## 1. 问题描述

{具体的问题或改进点}

## 2. 实验依据

{实验数据、训练日志、或 bug 记录}

## 3. 改动范围

- 文件: `src/{module}.py`
- 函数: `{function_name}`
- 行数: ~{N} 行

## 4. 代码改动

```python
# Before:
{old_code}

# After:
{new_code}
```

## 5. 预期效果

- Training loss: {下降/持平/上升}
- Win rate vs baseline: {+%X 或 -%X}
- 训练稳定性: {改善/持平/下降}

## 6. 风险

- {低/中/高}
- 回滚方案: {如果有问题的处理方式}
```

---

## Step 2: Code Review

### 审查者角色

- **MiniMax (Codex)** 做静态分析 — 不实现代码，只审查
- **DeepSeek/Agent** 做代码实现

### 审查标准

#### P0 问题（Blocker — 必须修复）

| # | 检查项 | 说明 |
|---|--------|------|
| P0-1 | **Reward Hacking** | Reward function 被钻空子（如故意输掉换取某些状态） |
| P0-2 | **崩溃风险** | `None` / `KeyError` / `IndexError` 未捕获导致训练崩溃 |
| P0-3 | **非法 Action** | 生成环境不接受的 action（如负数数量、非法 product） |
| P0-4 | **无限循环** | `while True` 无 exit、或递归无 base case |
| P0-5 | **内存泄漏** | 训练过程中内存持续增长（如 replay buffer 未清理） |
| P0-6 | **梯度爆炸** | 梯度 norm 持续增长导致 NaN |

#### P1 问题（Critical — 应该修复）

| # | 检查项 | 说明 |
|---|--------|------|
| P1-1 | **逻辑错误** | 条件判断反向、`min`/`max` 用错、边界值 off-by-one |
| P1-2 | **Observation Bug** | 使用了不应该能看到的 private 信息 |
| P1-3 | **硬编码魔数** | 无解释的 magic number（如 `if x > 999` 而非 `SHED_CAPACITY`） |
| P1-4 | **副作用** | 函数修改了输入参数或全局状态但无文档 |
| P1-5 | **Action Mask 遗漏** | Invalid actions 没有被正确 mask |
| P1-6 | **Reward Scale 不合理** | Reward magnitude 过大或过小，影响训练稳定性 |

#### P2 问题（Major — 建议修复）

| # | 检查项 | 说明 |
|---|--------|------|
| P2-1 | **代码重复** | 超过 3 处相同的代码片段未抽象 |
| P2-2 | **命名不清** | 变量/函数名无法表达意图 |
| P2-3 | **文档缺失** | 公开接口无 docstring |
| P2-4 | **过度复杂** | 函数超过 50 行或嵌套超过 3 层 |
| P2-5 | **GPU 利用率低** | 训练时 GPU 利用率 < 50% |

#### P3 问题（Minor — 可选修复）

| # | 检查项 | 说明 |
|---|--------|------|
| P3-1 | **代码风格** | PEP8 问题（可用 `black` 自动修复） |
| P3-2 | **注释冗余** | 显而易见的注释可以删除 |
| P3-3 | **TensorBoard 日志缺失** | 关键 metrics 没有记录 |

---

### Code Review 流程

1. **MiniMax 审查代码改动**
   - 读取 CHANGE_SPEC 理解预期行为
   - 读取改动的源文件
   - 对照 P0/P1 检查表逐项检查
   - 输出审查报告

2. **输出格式**

```markdown
## Code Review — {module}

### 审查文件
- `src/xxx.py` (新增/修改)

### P0 问题 ❌
- (列出所有 P0 问题)

### P1 问题 ⚠️
- (列出所有 P1 问题)

### P2 问题 💡
- (列出所有 P2 问题)

### 结论
✅ **通过** — 可以进入本地评估
⚠️ **有条件通过** — 有 P1 问题需要修复后再评估
❌ **阻塞** — 有 P0 问题必须先修复
```

---

## Step 3: 修复问题 (Fix Issues)

### 规则

1. **先修 P0，再修 P1**
2. **每次只修一个问题** — 方便 bisect
3. **修复后标记** — 在 review 报告里打勾

### 修复后操作

```bash
# 验证修复
grep -n "fixed issue" src/xxx.py

# 运行快速测试
python scripts/test_env.py
```

---

## Step 4: 本地评估 (Local Evaluation)

### 评估标准

#### Gate 1: 环境验证 (快速失败)

```bash
python scripts/test_env.py
```

| 条件 | 结果 |
|------|------|
| 环境正常运行 720 步 | ✅ 进入下一阶段 |
| 崩溃或报错 | ❌ 回滚或修复 |

#### Gate 2: 短训练验证 (1M steps)

```bash
python scripts/train.py --config configs/test.yaml --total_steps 1000000
```

| 条件 | 结果 |
|------|------|
| Training loss 下降 | ✅ 进入下一阶段 |
| 梯度 NaN/爆炸 | ❌ 回滚 |
| Win rate > random (20%) | ✅ 通过 |
| Win rate ≤ random | ⚠️ 需要分析 |

#### Gate 3: 中等训练 (10M steps)

```bash
python scripts/train.py --config configs/production.yaml --total_steps 10000000
```

| 条件 | 结果 |
|------|------|
| Win rate vs random > 50% | ✅ 进入下一阶段 |
| Win rate vs heuristic > 40% | ✅ 进入下一阶段 |
| Win rate vs rule-based v22 > 30% | ✅ 可选 baseline |

#### Gate 4: 完整训练 (100M steps)

```bash
python scripts/train.py --config configs/production.yaml --total_steps 100000000
```

| 条件 | 结果 |
|------|------|
| Win rate vs v22 > 50% | ✅ 可以提交 Kaggle |
| Win rate vs top players > 30% | ✅ 有竞争力 |

---

## 完整示例流程

### 场景: 添加 WHEAT-only trading RL

#### Step 1: 代码修改

**CHANGE_SPEC-wheat-trading-20260809.md**:
```markdown
# CHANGE_SPEC-wheat-trading — WHEAT-only trading RL

## 1. 问题描述
需要验证 RL 能在 Kagriculture 环境中学到基本交易策略。

## 2. 实验依据
- Orbit Wars 2nd place 用简化 action space 成功
- WHEAT 是 Kagriculture 最核心的交易品

## 3. 改动范围
- 文件: `src/envs/kagriculture_env.py`
- 函数: `action_space`, `reward`
- 行数: ~50 行

## 4. 代码改动
```python
# Before:
action_space = MultiDiscrete([...])  # 全部 action

# After:
action_space = Discrete(3)  # HOLD, BUY_WHEAT, SELL_WHEAT
```

## 5. 预期效果
- 10M steps 后 win rate > 30% vs random
- 训练 loss 稳定下降
```

#### Step 2: Code Review

```markdown
## Code Review — wheat-trading

### P0 问题 ❌
- (无)

### P1 问题 ⚠️
- P1-6: Reward scale 可能过大 → 已调小到 0.001

### 结论
✅ **通过** — 可以进入本地评估
```

#### Step 3: 修复

(无 P0 问题，跳过)

#### Step 4: 本地评估

```bash
$ python scripts/train.py --config configs/wheat_only.yaml --total_steps 10000000
Training complete: 10M steps
Win rate vs random: 45% ✅
Win rate vs heuristic: 35% ✅
```

**评估通过 → 可以扩展到 full action space**

---

## RL 特定检查清单

### Reward Hacking 检测

训练时观察：
- [ ] Agent 是否学会了"自杀"行为
- [ ] Agent 是否故意不收获作物
- [ ] Agent 是否进入了死锁状态

### 训练稳定性检查

```bash
# 查看 TensorBoard
tensorboard --logdir logs/

# 检查关键指标
- policy_loss: 不应该是 NaN
- value_loss: 不应该持续增长
- entropy: 应该缓慢下降后稳定
- reward: 不应该出现尖峰
```

### 环境正确性检查

```bash
# 验证 observation 包含正确信息
python scripts/inspect_obs.py

# 验证 action mask 正确
python scripts/test_mask.py
```

---

## 常见问题

### Q: 训练 loss 下降但 win rate 不涨？
A: **Reward 可能不够dense**，或者 baseline 太强。尝试：
- 增加 dense reward
- 对比不同 baseline

### Q: 训练出现 NaN？
A: **梯度爆炸**。尝试：
- 减小 learning rate
- 增加 gradient clipping
- 检查 reward scale

### Q: 多个 session 协作时谁来 review？
A: 当前 session 审查上一个 session 的改动。例如：
- Session A 实现了 wheat trading
- Session B 扩展到 full action space 时做 review

### Q: P0/P1 问题修复后需要重新完整 review 吗？
A: 只需要重新 review 修复的部分（P0/P1 checklist），P2/P3 不需要。

---

## 相关文档

- `docs/01-DESIGN-SPEC.md` — 总体设计规范
- `docs/02-OBSERVATION-SPACE.md` — Observation 空间
- `docs/03-ACTION-SPACE.md` — Action 空间
- `docs/04-REWARD-DESIGN.md` — Reward 函数
- `docs/05-DATA-MANAGEMENT.md` — 数据管理
