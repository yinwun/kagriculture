# CHANGE_SPEC-maskableppo — MaskablePPO 改造

> **Date**: 2026-08-11
> **Author**: Codex
> **Based on**: Gemini 分析 + Episode 0 replay 诊断

---

## 1. 问题描述

### Episode 0 Replay 暴露的"动作空间死锁"

Step 0~93：初始资金 $2,974，模型连续 93 步 100% 触发 BUY_WHEAT，价格 $80~$105/步，资金瞬间耗尽至 $10。

Step 94~719：money=$10 < 小麦价格，BUY 实际无效。但标准 PPO **看不到这个约束**，继续盲目输出 BUY_WHEAT，每步得 -0.05 penalty，625 步全在空转，最终 LOST。

**根因**：标准 PPO 不调用 `action_masks()`，无法感知"BUY 在资金不足时不可执行"这一硬约束。非法动作被选后只给惩罚，不被物理屏蔽，导致：
1. 模型学到"HOLD 最安全"
2. 或者学到了也继续选 BUY 但被持续惩罚

---

## 2. 实验依据

### Episode 0 数据（eval_reports/iter_01_20260811_095726）

| 阶段 | Steps | 动作 | 资金变化 | Reward |
|------|-------|------|---------|--------|
| BUY 期 | 0~93 | 100% BUY | $2,974 → $10 | -0.05/步 |
| 空转期 | 94~719 | 100% BUY | $10 → $10 | -0.05/步 |
| 合计 | 719 | BUY=719 | 净亏 | 总 reward ≈ -35 |

### `_is_action_valid` 硬性规则

```python
# SELL_WHEAT：库存 > 0
if action == 2:
    return shed.get("WHEAT", 0) > 0

# BUY_WHEAT：money >= price 且 market 有库存
if action == 3:
    return money >= wheat_price and market_inv.get("WHEAT", 0) > 0
```

这些规则不是猜测，是游戏引擎本身对动作的约束。

---

## 3. 改动范围

| 文件 | 改动内容 |
|------|---------|
| `scripts/train.py` | 标准 PPO → MaskablePPO |
| `src/envs/kagriculture_env.py` | `action_masks()` 已存在，确认返回类型正确（bool 或 int8）|

### 3.1 train.py 改动

**Before**：
```python
from stable_baselines3 import PPO

env = gym.make("Kagriculture-v0", opponent=args.opponent, ...)
env = Monitor(env)

model = PPO(
    "MlpPolicy",
    env,
    learning_rate=args.learning_rate,
    ...
)
```

**After**：
```python
from sb3_contrib import MaskablePPO
from sb3_contrib.common.maskable.policies import MaskableActorCriticPolicy
from sb3_contrib.common.wrappers import ActionMasker
from stable_baselines3.common.callbacks import CallbackList

def make_env():
    env = gym.make("Kagriculture-v0", opponent=args.opponent, ...)
    env = ActionMasker(env, lambda e: e.action_masks())
    env = Monitor(env)
    return env

model = MaskablePPO(
    MaskableActorCriticPolicy,
    env=vec_env,   # VecEnv 支持 MaskablePPO
    learning_rate=args.learning_rate,
    n_steps=args.n_steps,
    batch_size=args.batch_size,
    n_epochs=args.n_epochs,
    gamma=args.gamma,
    ent_coef=args.ent_coef,
    ...
)
```

### 3.2 VecEnv 支持

SB3 MaskablePPO 要求环境是 `VecEnv`。需要用 `stable_baselines3.common.vec_env.DummyVecEnv` 或 `SubprocVecEnv` 包装。

**Before**：
```python
env = gym.make("Kagriculture-v0", ...)
```

**After**：
```python
def make_env():
    env = gym.make("Kagriculture-v0", opponent=args.opponent, ...)
    env = ActionMasker(env, lambda e: e.action_masks())
    return env

vec_env = DummyVecEnv([make_env for _ in range(1)])
model = MaskablePPO(MaskableActorCriticPolicy, vec_env, ...)
```

### 3.3 action_masks() 类型确认

`action_masks()` 已存在（line 308），返回 `np.ndarray` of `int8`。MaskablePPO 要求返回 `bool` 或 `np.bool_`，需要做类型兼容。

```python
# 确认返回类型
def action_masks(self) -> np.ndarray:
    mask = np.ones(self.action_space.n, dtype=bool)  # 改为 bool 类型
    ...
    return mask
```

---

## 4. 预期效果

| 指标 | 改动前（标准 PPO） | 改动后（MaskablePPO） |
|------|-------------------|---------------------|
| BUY 空转 | 持续选 BUY → 每步 -0.05 | 资金不足时 BUY 被屏蔽，只选 HOLD/SELL |
| 策略多样性 | BUY 100% | 预期 BUY+SELL+HOLD 混合 |
| trade_frac | ~90% 但单一动作 | 预期接近 50%，多动作协调 |
| win_rate vs RF | 0% | 预期提升 |

---

## 5. 风险

| 风险 | 级别 | 回滚方案 |
|------|------|---------|
| sb3-contrib 未安装 | 低 | `pip install sb3_contrib` |
| VecEnv + ActionMasker 兼容问题 | 中 | 单独测试 env.wrapper |
| MaskablePPO 超参需调 | 中 | 保持与当前 PPO 相同超参 |
| action_masks() bool 类型不兼容 | 低 | 改为 `dtype=bool` 即可 |

---

## 6. 验证方法

```bash
# 1. 检查 sb3_contrib 已安装
python -c "from sb3_contrib import MaskablePPO; print('OK')"

# 2. 验证 action_masks 返回 bool
python -c "
from src.envs.kagriculture_env import register
register()
import gymnasium as gym
env = gym.make('Kagriculture-v0')
obs, _ = env.reset()
mask = env.action_masks()
print(f'mask dtype={mask.dtype}, shape={mask.shape}, values={mask}')
assert mask.dtype == bool, f'Expected bool, got {mask.dtype}'
"

# 3. 快速训练 50K steps 验证无报错
python scripts/train.py --total_steps 50000 --opponent random --save_freq 999999

# 4. eval_loop 验证
python scripts/eval_loop.py --max_iters 1 --skip_train \
    --existing_model <model_path> --opponent trained --num_eval_episodes 5
```
