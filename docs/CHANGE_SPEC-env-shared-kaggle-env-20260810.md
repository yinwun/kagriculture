# CHANGE_SPEC-env-shared-kaggle-env — share kaggle_env between train and eval

> **Date**: 2026-08-10
> **Author**: code-walkthrough session
> **Based on**: code review of `src/envs/kagriculture_env.py` (post SHORT training analysis)

## 1. 问题描述

Each `KagricultureEnv` instance lazily creates its own `_kaggle_env` via `make("kagriculture", debug=False)` (`_init_kaggle_env`). `scripts/train.py` creates **two independent** `KagricultureEnv` instances (one for train, one for eval). Each runs:

- Independent `reset(num_agents=2)` with a different random initial state
- Independent interpreter state for the kaggle game
- Independent opponent (RF is deterministic given obs, but obs depends on env state → opponent plays **differently** in train vs eval)

Result: the agent learns to play against the rollout's specific opponent action sequence, which does not match the eval env's opponent action sequence. The eval win-rate is therefore measuring the agent's performance against a *different* opponent than the one it trained against.

This is a primary suspect for the SHORT `ep_rew_mean = +5.8` vs `eval win_rate = 0%` gap, even after P0-1/P0-3/P0-4 are fixed.

## 2. 实验依据

- SHORT training: rollout reward suggests "winning" but eval deterministic never wins
- `src/envs/kagriculture_env.py:194-199` `_init_kaggle_env` creates fresh kaggle_env per instance
- `scripts/train.py:298-303` creates two `KagricultureEnv` instances, each making its own kaggle_env
- The Kaggle env's `reset(num_agents=2)` uses Python's random without seeding → different initial farms

## 3. 改动范围

- 文件: `src/envs/kagriculture_env.py` (add optional `kaggle_env` param to `__init__`)
- 文件: `scripts/train.py` (create one kaggle_env, share with both envs)
- 行数: ~10 lines added across 2 files

## 4. 代码改动

```python
# Before (src/envs/kagriculture_env.py:160-199):
def __init__(self, opponent: str = "random", reward_type: str = "dense",
             opponent_model_path: str = None):
    super().__init__()
    ...
    self._kaggle_env = None
    ...

def _init_kaggle_env(self):
    """初始化 Kaggle 环境"""
    if self._kaggle_env is None:
        from kaggle_environments import make
        self._kaggle_env = make("kagriculture", debug=False)


# After:
def __init__(self, opponent: str = "random", reward_type: str = "dense",
             opponent_model_path: str = None, kaggle_env=None):
    super().__init__()
    ...
    # Allow sharing one kaggle_env instance across train and eval (so the
    # opponent sees consistent initial state between train and eval).
    self._kaggle_env = kaggle_env  # may be None → lazy create
    ...

def _init_kaggle_env(self):
    """Initialize Kaggle env (lazy, unless one was injected)."""
    if self._kaggle_env is None:
        from kaggle_environments import make
        self._kaggle_env = make("kagriculture", debug=False)
```

```python
# Before (scripts/train.py:298-303):
logger.log(f"[setup] creating train env (opponent={args.opponent})")
train_env = KagricultureEnv(...)
logger.log(f"[setup] creating eval env")
eval_env = KagricultureEnv(...)


# After:
logger.log(f"[setup] creating shared kaggle_env")
from kaggle_environments import make as _kaggle_make
shared_kaggle_env = _kaggle_make("kagriculture", debug=False)

logger.log(f"[setup] creating train env (opponent={args.opponent})")
train_env = KagricultureEnv(opponent=args.opponent,
                             reward_type="dense",
                             opponent_model_path=args.opponent_model_path,
                             kaggle_env=shared_kaggle_env)
logger.log(f"[setup] creating eval env (sharing kaggle_env)")
eval_env = KagricultureEnv(opponent=args.opponent,
                           reward_type="dense",
                           opponent_model_path=args.opponent_model_path,
                           kaggle_env=shared_kaggle_env)
```

## 5. 预期效果

- **eval opponent matches train opponent**: 同一个 kaggle env instance，意味着：
  - 同一 episode 序列下 opponent 看到的 obs 完全一致
  - agent 训练用的"opponent 行为"和 eval 测的"opponent 行为"对齐
- **eval win_rate 成为更有意义的指标**: 不再受 opponent 行为分歧影响
- **Training loss / reward**: 不直接变化（gradient 计算路径不变）
- **训练稳定性**: 持平（没有 reward / policy 改动）

## 6. 风险

- **中** — 共享 mutable state，理论上有并发风险。但 SB3 的 rollout（train）和 eval callback 串行执行（eval 在 rollout 之间跑），不会并发。
- **可能引入的副作用**:
  - 共享 kaggle_env 的 `reset()` 会被 train / eval 各自调用，互不干扰（kaggle env 内部状态机允许反复 reset）
  - 如果用户在 train.py 里写 `eval_env.close()` 会丢掉 train_env 的引用——已经在 `close()` 里改成 `_kaggle_env = None`，会断引用，需要相应更新（见 P0 修复历史）
- 回滚方案: 删 `kaggle_env=shared_kaggle_env` 参数即可

## 7. 关联

- 关联 P0-1 (`_won` reset): 已修，正交
- 关联 P0-3 (dense reward scale): 已修，正交
- 关联 P0-4 (terminal bonus on truncated): 已修，正交
- 关联 `src/envs/kagriculture_env.py:close()`: 当前 `close()` 设 `_kaggle_env = None`，如果 kaggle_env 是共享的，调用 `train_env.close()` 会清空 eval_env 的引用 → 需要让 `close()` 不破坏共享引用（见 P2 提示）