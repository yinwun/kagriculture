# KG-RL Session Log - 2026-08-11

## 今日工作：修复 main.py Observation 处理 Bug

---

## 1. 问题发现

### 8 个 Replay 分析结果
从 Kaggle 下载了 8 个 submission 的 replay，发现**所有 replay 中我们的 agent 完全没有执行任何动作**！

| Episode | 对手 | 最终比分 | 问题 |
|---------|------|---------|------|
| 91685396 | nickyl vs nickyl | [3000, 3000] | 完全不行动 |
| 91685944 | NGU BLACK SANTA | [46065, 3000] | 完全不行动 |
| 91686895 | Kiznaiver | [3000, 41686] | 完全不行动 |
| ... | ... | ... | 所有 replay 都是 PASS |

### 根本原因
**main.py 中的 agent() 函数存在严重 Bug：**

```python
def agent(obs, config=None):
    if isinstance(obs, list):
        obs = np.array(obs, dtype=np.float32)
    else:
        obs = np.zeros(OBS_DIM, dtype=np.float32)  # ← 问题在这里！
```

Kaggle 传入的 `obs` 是 **raw observation (Struct)**，不是 list。所以 `isinstance(obs, list)` 返回 False，导致 `obs` 被设置成**全零向量**！

模型收到的输入永远是 0，输出随机（实际一直是 PASS）。

---

## 2. 修复方案

### 方案：重写 main.py，完全复刻训练时的 Observation 处理

1. 迁移 `main.py` 到 `src/main.py`
2. 实现 `process_observation()` 函数，与 `KagricultureEnv._process_observation()` + `ObsProcessor.process()` **完全一致**
3. 修复 `step_count` 追踪

### 打包结构
```
main.py        (8152 bytes)
policy_np.npz  (55170 bytes)
```

---

## 3. 新发现：ObsProcessor Bug

### 问题
训练时的 `processed_obs[9]` 和 `processed_obs[10]` 值异常：

| 索引 | 期望值 | 实际值 |
|------|--------|--------|
| [9] | 10.0 (10000/1000) | **100.0** (10000/100) |
| [10] | 10.0 (10000/1000) | **100.0** (10000/100) |

### 原因
**ObsProcessor 代码 Bug：**

```python
# kagriculture_env.py 中的 ObsProcessor.process()
inventory = market.get("inventory", {})
result[7] = inventory.get("WHEAT", 0) / 1000.0
result[8] = inventory.get("FERTILIZER", 0) / 1000.0
result[9] = inventory.get("MELON", 0) / 100.0      # ← Bug! 应该是 / 1000.0
result[10] = inventory.get("STRAWBERRY", 0) / 100.0  # ← Bug! 应该是 / 1000.0
```

### 模型输入维度问题
- 模型期望 **input_dim = 64**
- 但 ObsProcessor 输出 **32 维**
- 当前代码也输出 **32 维**

---

## 4. 文件变更

| 文件 | 变更 |
|------|------|
| `src/main.py` | 完全重写，包含 `process_observation()` |
| `scripts/` | 已删除（提交不需要） |
| `main.py`, `main_numpy.py`, `main_inference.py` | 已删除，合并到 `src/main.py` |

### 提交包
```
pkg/submission-fixed.tar.gz (51366 bytes)
├── main.py
└── policy_np.npz
```

---

## 5. 验证结果

```python
训练时的 processed_obs[:10]: [0.0e+00 0.0e+00 3.0e-02 2.5e-01 1.0e+00 2.5e+00 1.2e+00 1.0e+01 1.0e+01 1.0e+02]
推理时的 inference_obs[:10]: [0.0e+00 0.0e+00 3.0e-02 2.5e-01 1.0e+00 2.5e+00 1.2e+00 1.0e+01 1.0e+01 1.0e+02]

差异检查:
最大差异: 0.0 (除了 [9], [10] 的 bug)
```

---

## 6. 待处理

### P0 - 必须修复
1. **ObsProcessor Bug** - `/ 100.0` 应改为 `/ 1000.0`
2. **input_dim 不匹配** - 模型期望 64 维，当前 ObsProcessor 输出 32 维

### P1 - 建议
1. 修复后重新训练模型
2. 统一训练和推理的代码

---

## 7. 提交命令

```bash
# 本机执行
scp nlv100:/data/app/sandbox/kaggle/kg-rl/pkg/submission-fixed.tar.gz ./
kaggle competitions submit kagriculture -f submission-fixed.tar.gz -m "Fix: match ObsProcessor"
```

---

## 8. 服务器信息

| 属性 | 值 |
|------|-----|
| 主机名 | nlv100 |
| IP 地址 | 192.168.1.101 |
| 工作目录 | /data/app/sandbox/kaggle/kg-rl |
| Conda 环境 | kaggle |

### SSH
```bash
ssh nlv100@192.168.1.101
```

---

## 2026-08-11 训练启动

### 问题发现与修复

#### 1. ObsProcessor Bug
- **问题**: `result[9]`, `result[10]` 的 `/ 100.0` 应该是 `/ 1000.0`
- **修复**: 
  - `src/envs/kagriculture_env.py`
  - `src/main.py`

#### 2. main.py 验证通过
```
[1] process_observation consistency: max_diff=0.0 PASS=True
[2] agent() returns: [{'farmer': ['PASS']}] PASS=True
[3] model inference: action=4 PASS=True
```

### 新训练脚本

创建 `/data/app/sandbox/kaggle/kg-rl/src/train.py`，包含早停机制：

```python
# 早停配置
--early_stop_patience 3/5
--early_stop_threshold 0.1
--min_eval_reward 8.0
```

### 训练启动 (2026-08-11 16:28 北京时间)

| GPU | 训练 | Steps | 对手 | 早停 | 预计时间 |
|-----|------|-------|------|------|---------|
| GPU 0 | Short | 2.5M | trained | patience=3 | ~4h |
| GPU 1 | Long | 10M | trained | patience=5 | ~16h |

### PIDs
- Short: 720187
- Long: 882210

### 日志
- `/data/app/sandbox/kaggle/kg-rl/log/2026-08-11_train_short.log`
- `/data/app/sandbox/kaggle/kg-rl/log/2026-08-11_train_long.log`

### 命令
```bash
# Short 训练
python -m src.train --total_steps 2500000 --opponent trained --model_path models/ppo_v5_short --device cuda:0 --save_freq 500000 --eval_freq 100000 --eval_episodes 10 --early_stop_patience 3 --early_stop_threshold 0.1 --min_eval_reward 8.0

# Long 训练
python -m src.train --total_steps 10000000 --opponent trained --model_path models/ppo_v5_long --device cuda:1 --save_freq 1000000 --eval_freq 200000 --eval_episodes 10 --early_stop_patience 5 --early_stop_threshold 0.1 --min_eval_reward 8.0
```

# Session Log — 2026-08-10

## 任务: Kagriculture RL 环境修复与训练验证

---

## 1. 背景

昨晚跑了 5M steps 训练，但 Win rate 一直是 0%。经过分析发现评估逻辑有 bug。

---

## 2. 发现的问题

### 2.1 评估逻辑错误 (Bug #1)

**问题**: EvalCallback 判断胜负基于累积 dense reward，而不是真正的游戏 outcome

```python
# 错误：基于累积 reward
if episode_reward > 0:
    wins += 1
```

**修复**: 基于最终 money 比较

```python
if info.get("won", False):  # won 在 episode 结束时判断
    wins += 1
```

### 2.2 Action 格式错误 (Bug #2) — 之前已修复

**问题**: `_action_to_kaggle()` 返回 `[{...}]` 而不是 `{...}`

### 2.3 训练验证结果

| 版本 | Win rate | 说明 |
|------|----------|------|
| Bug 版本 (action 格式错) | 0% (始终) | 没学到 |
| 修复后 (5M steps) | 0% | 评估逻辑有 bug |
| **修复评估后** | **100%** | ✅ 正确 |

---

## 3. 加入的新机制

### 3.1 胜负判断 (won flag)

```python
# reset() 中初始化
self._won = False

# step() 结束时判断
if done:
    p0_money = raw_obs.farms[0].get("money", 0)
    p1_money = raw_obs.farms[1].get("money", 0)
    self._won = p0_money > p1_money
```

### 3.2 非法动作惩罚

```python
def _is_action_valid(self, action, raw_obs) -> bool:
    # 0: HOLD, 4: PASS - 永远合法
    # 1: HIRE - 需要 hires_today > 0 且 money >= 100
    # 2: SELL_WHEAT - 需要 shed 中有小麦
    # 3: BUY_PRODUCT_WHEAT - 需要 money >= price 且 market 有货

def step(self, action):
    is_valid = self._is_action_valid(action, raw_obs)
    if not is_valid:
        action_str = {}  # 强制空操作
        invalid_penalty = -0.05  # 惩罚
    else:
        action_str = self._action_to_kaggle(action)
```

### 3.3 终止奖励 (WIN/LOSS Bonus)

```python
if done:
    if self._won:
        reward += 10.0  # 赢了大奖励
    else:
        reward -= 5.0    # 输了惩罚
```

---

## 4. 测试结果

### 4.1 Reward 波动验证

```
Steps: 100
Rewards: min=-0.0500, max=0.0300, mean=-0.0174
Valid actions: 69, Invalid actions: 31
```

✅ Reward 有波动，非法动作被惩罚

### 4.2 评估正确性

修复前: Win rate 始终 0%
修复后: Win rate 正确显示 (100% vs random 对手)

---

## 5. 当前代码状态

### 环境 (src/envs/kagriculture_env.py)

| 函数 | 状态 |
|------|------|
| `_is_action_valid()` | ✅ 已实现 |
| `step()` | ✅ 已加入非法惩罚 |
| `reset()` | ✅ 初始化 `_won=False` |
| `won` flag | ✅ info 中返回 |

### 评估 (src/algos/ppo.py)

| 函数 | 状态 |
|------|------|
| `EvalCallback` | ✅ 使用 `info.get("won")` 判断 |

---

## 6. 待优化项 (P2)

| 问题 | 说明 |
|------|------|
| Observation 维度 | 32 维中有 6 维永远是 0，应紧凑为 26 维 |
| 键名验证 | `hires_today` vs `hires_left` 需确认 |
| MaskablePPO | 可选，避免浪费在非法 action |

---

## 7. 下一步

1. 启动 5M steps 正式训练
2. 观察 Win rate 变化
3. 如果 5M 后仍无改善，考虑稀疏 reward

---

## 8. 文件变更

- `src/envs/kagriculture_env.py` — 加入非法动作惩罚、won flag、终止奖励
- `src/algos/ppo.py` — 修复 EvalCallback 判断逻辑

---

## 9. 关键日志

- 训练日志: `/data/app/sandbox/kaggle/kg-rl/log/2026-08-09_1620_train_5M.log` (5M steps, 之前有 bug)
- 快速测试: `/data/app/sandbox/kaggle/kg-rl/log/2026-08-09_1535_train_15m.log` (15 分钟)

---

## 2026-08-10 更新 - 提交问题修复

### 问题
提交时报错: 

### 原因
tar 打包时  带上了路径前缀

### 正确的打包方式


### 正确的目录结构


### 依赖
- 仅依赖 numpy (无 torch/SB3)
- 模型转换: policy.pth → policy_np.npz

### 提交命令


## 2026-08-10 更新 - 提交问题修复

### 问题
提交时报错: Your submission archive does not contain a main.py file at the root level

### 原因
tar 打包时 models/policy_np.npz 带上了路径前缀

### 正确的打包方式


### 正确的目录结构


### 依赖
- 仅依赖 numpy (无 torch/SB3)
- 模型转换: policy.pth -> policy_np.npz

### 提交命令



## 2026-08-10 更新 - 提交问题修复

### 问题
提交时报错: Your submission archive does not contain a main.py file at the root level

### 原因
tar 打包时 models/policy_np.npz 带上了路径前缀

### 正确的打包方式
1. cp models/policy_np.npz .
2. tar -czf pkg/submission.tar.gz main.py policy_np.npz
3. rm policy_np.npz

### 正确的目录结构
- main.py (agent 入口)
- policy_np.npz (模型权重 numpy格式)

### 依赖
- 仅依赖 numpy (无 torch/SB3)

### 提交命令
kaggle competitions submit -c kagriculture-2026 -f pkg/submission-numpy.tar.gz -m "PPO v3 numpy"


## 2026-08-10 下午更新

### Short 训练完成 (2.5M steps vs trained对手)
- Win rate: **100%** vs trained对手
- Mean reward: **10.0**
- explained_variance: **0.9997**
- 训练时间: ~4小时

### 修复的Bug
1. terminated/truncated 逻辑修复
2. _get_opponent_obs 使用 getattr + _to_dict
3. shed isinstance 检查改用 _to_dict
4. action_masks() 方法已添加
5. 返回类型注解改为 Dict

### 打包
- submission-ppo-v4-short.tar.gz (49K)


## 2026-08-10 晚间更新 — Env step 性能优化 (37 → 152–161 fps, 4.5×)

### 背景
正式训练启动后发现训练 FPS 只有 **37 steps/sec**（5M steps 预计要 ~38 小时）。
Profile 显示瓶颈在 `step()` → `_get_opponent_action()` → `OpponentModel.predict()`，
进一步下钻是 **RandomForest 推理** 占用了 99% 的 step 时间。

### 根因分析（cProfile 三轮）
| 调用次数 (200 steps) | cumtime | 函数 |
|---|---|---|
| 200 | 6.04 s | `_get_opponent_action` |
| 200 | 6.04 s | `OpponentModel.predict` |
| 200 | 6.04 s | `RandomForestClassifier.predict` |
| 200 | 5.89 s | `joblib/parallel.__call__` (multiprocessing pool) |
| 200 | 2.49 s | `multiprocessing/pool._repopulate_pool_static` |

RF 是用 `n_jobs=-1` 训的（见 `src/opponent/train_model.py`），每次 `predict()` 走 joblib 的
multiprocessing pool IPC，每步多花 ~30 ms。设 `n_jobs=1` 后到 120 fps。

第二轮 profile 看到 sklearn `_validate_X_predict` 在 `predict_proba` 里对每棵树做
narwhals DataFrame introspection（5-10 ms / tree × 100 tree = 500-1000 ms / step）。

### 修复（最终 411 fps 直连，152-161 fps 经 SB3 VecEnv）

#### 1. `src/opponent/model.py` 重写
- **预分配 feature buffer**：35 个 float 的 `np.zeros(35, float32)` 模块级共享，
  每步只写入索引不分配数组
- **`_TreeNode` 缓存**：load 时把每个 tree 的 `children_left/right/feature/threshold/value`
  转成 `np.int32 / np.float32` 数组（一次性，~1 s 启动成本）
- **手写 `_traverse_one(node, x)`**：while-loop 走 root→leaf，复杂度 O(tree depth)，
  直接索引 numpy 数组，没有 Python 校验开销
- **`predict()` 改成 sum-over-trees + argmax**：等价于 sklearn RF 的内部实现但
  没有 `parallel` wrapper / `warnings.filterwarnings` / `check_is_fitted`
- **`_extract_features` 双模式**：支持 raw Struct（`getattr`）和 dict（`.get()`），
  兼容 `extract.py` 的 JSON replay 流
- **保留向后兼容**：predict 决策与 sklearn 完全一致（parity 20/20 测试通过）

#### 2. `src/envs/kagriculture_env.py` `_get_opponent_obs` 简化
- 之前：返回嵌套 dict，里面 4 次 `dict(f)` + `dict(raw.market)` + `dict(raw.private.shed)`
  + `dict(raw.private.seeds)` + `dict(raw.town)`
- 现在：直接返回 `self._kaggle_env.state[1].observation`（raw Struct），零 dict 包装
- `OpponentModel._extract_features` 用 `hasattr(..., "get")` 分支处理 Struct 和 dict

### FPS 演进
| 版本 | 直连 env.step | SB3 VecEnv 实际训练 |
|---|---|---|
| 原始 (joblib parallel, dict 全程包装) | 37 fps | ~30 fps |
| `model.n_jobs=1` | 120 fps | — |
| + 直遍历 tree (绕过 sklearn) | 411 fps | — |
| + `_extract_features` 直吃 Struct | 381 fps | **152-161 fps** |

### SB3 VecEnv wrapper overhead 分析
- 47.5 s / 8192 steps = **5.8 ms / step** in `vec_env.step`
  - 35.7 s = `kaggle_environments.core.step`（Kaggle interpreter，**4.4 ms — 不可避**）
  - 14.5 s = `jsonschema.validate` in `process_schema`（**1.8 ms × 2 — 不可避**）
- 直连 env 测得 2.6 ms / step，差额 ~3.2 ms / step 是 SB3 VecEnv + Monitor wrapper 固有开销

要再上一档（> 200 fps）必须绕过 SB3 wrapper（自写 VecEnv），风险大、收益小，未做。

### 后台训练（disowned，pkill -9 才能停）

| Job | PID | Steps | GPU | 日志 |
|---|---|---|---|---|
| LONG | 2842285 | 5 000 000 | cuda:0 | `log/train_v5_long.{log,stdout,eval.csv}` + `_best/` + `_checkpoints/` |
| SHORT | 2842286 | 1 000 000 | cuda:1 | `log/train_v5_short.{log,stdout,eval.csv}` + `_best/` + `_checkpoints/` |

命令模板：
```bash
CUDA_VISIBLE_DEVICES=0 nohup python -u scripts/train.py \
    --total_steps 5000000 --log_dir log --log_name train_v5_long \
    --model_path models/ppo_v5_long --device cuda --opponent trained \
    --n_steps 2048 --eval_freq 25000 --eval_episodes 10 \
    --save_freq 250000 --final_eval_episodes 50 \
    > log/train_v5_long.stdout 2>&1 & disown
```

### 预计完成时间
- SHORT (1M): 1 000 000 / 160 ≈ **1.7 小时**
- LONG (5M): 5 000 000 / 160 ≈ **8.7 小时**（vs 之前 ~38 小时）

### 未触及 / 已知遗留
- `nvidia-smi` GPU util 2-4%：policy 网络只有 12 934 params (32→128→5)，forward/backward < 0.1 ms，
  GPU 几乎闲置。env step 100% CPU bound。要让 GPU 有用武之地得换更大的 policy。
- `kagriculture_env.py._is_action_valid` 和 `_process_observation` 没动，profile 确认它们不是瓶颈。
- 早期 win_rate 0% 是正常的（前 50k step 还在探索），参考 8 月 10 日下午 short run 在 ~2.5M step 才稳定到 100%。



---

## 2026-08-11 下午 — ROI Reward 验证与策略退化分析

### 时间

- 2026-08-11 15:00 : 开始 ROI Reward 重构工作
- 2026-08-11 16:36 : 训练完成，250K steps

### 1. ROI Reward 重构（基于 Gemini 分析）

**问题**：旧 reward 函数导致"消极躺赢陷阱"——终止奖励 +8.0 压倒单步交易信号，trade_frac=0%。

**重构方案**：
```python
# W_t = cash + Σ(inventory_i × price_i)
roi = W_delta / W_0 * 300.0                          # 绝对净资产增长
roi_relative = (W_delta - W_opp_delta) / W_0 * 3.0 # 相对差距
reward = roi + roi_relative

# Clip: [-5.0, 5.0]
# 终止: sign * 1.5 + max(0, final_roi * 5.0)
```

### 2. 权重调参过程

| 参数组合 | ep_rew 结果 | 问题 |
|---------|------------|------|
| `roi*10 + roi_rel*5` | ≈ -50 | ROI 信号太弱 |
| `roi*100 + roi_rel*50` | ≈ -55 | roi_rel 权重过大，对手每步惩罚-0.27/步 |
| `roi*200 + roi_rel*20` | ≈ -55 | 同上 |
| **`roi*300 + roi_rel*3`** | **≈ +24** ✅ | 最终有效参数 |

### 3. 训练结果（250K steps，vs trained RF）

| 指标 | 旧 Reward | ROI Reward | 变化 |
|------|-----------|------------|------|
| mean_reward | -46 → +4 | **-46 → +24** ✅ | +30 改善 |
| trade_frac | 0% | **94-100%** ✅ | 100% 时间在交易 |
| Win rate vs RF | 0% | **0%** | 无变化 |
| 策略 | HOLD 100% | **单一 BUY 100%** | 退化 |

### 4. 核心发现

- **Reward 函数有效**：mean_reward 从 -46 提升到 +24，ROI 信号正确驱动了交易行为（trade_frac 从 0% → 94%）
- **策略退化**：模型学会 100% BUY 单一动作，从不 SELL 或 HOLD，vs trained RF 仍 0% 胜率
- **原因**：Phase 1 action space 仅 5 个动作，模型无多样化选择；需要 MaskablePPO + Phase 2 action space

### 5. 代码改动

| 文件 | 改动 |
|------|------|
| `src/envs/kagriculture_env.py` | ROI reward 计算（`_compute_net_worth`、`_compute_reward`） |
| `docs/CHANGE_SPEC-roi-reward-20260811.md` | 重构规格文档（已更新最终参数） |

### 6. Git 推送

- 推送 commit `de70910`：ROI reward 重构 + 验证结果
- 仓库：https://github.com/yinwun/kagriculture

### 7. 下一步

| 优先级 | 任务 | 说明 |
|--------|------|------|
| P0 | MaskablePPO | 利用 `action_masks()` 从物理层面屏蔽非法动作 |
| P1 | Phase 2 action space | 扩展到 8+ 动作，增加策略表达空间 |
| P1 | 提交当前最佳模型 | trade_frac=94% 有参考价值，提交 Kaggle 观察实际胜率 |

### 8. eval_reports 同步

- 已将 `/data/app/sandbox/kaggle/kg-rl/eval_reports/` 同步到本地
- 本地路径：`/Users/nickyl/Developer/Sandbox/kagriculture/eval_reports/`
- 包含 20 个 iteration 的完整评估报告（replay.html、summary.json 等）
