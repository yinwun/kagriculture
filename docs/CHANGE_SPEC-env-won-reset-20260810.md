# CHANGE_SPEC-env-won-reset — `_won` state leak across episodes

> **Date**: 2026-08-10
> **Author**: code-walkthrough session
> **Based on**: code review of `src/envs/kagriculture_env.py` (post SHORT training analysis)

## 1. 问题描述

`KagricultureEnv.reset()` does NOT reset `self._won = False`. Once set to `True` in step N, it stays `True` until step N+1 hits `done=True` again. Any reader of `info["won"]` mid-episode (or during the first done=True of the new episode, before the new outcome is set) sees stale data.

Combined with the P0-4 finding (terminal bonus applied on truncated episodes), this can produce cascading wrong signals.

## 2. 实验依据

- SHORT 训练日志 `log/train_v5_short.stdout` (1M steps, 1.81h, fps 153, eval win_rate=0%)
- Rollout `ep_rew_mean ≈ +5.8` 反推 win_rate ≈ 72%, but eval deterministic win_rate = 0% (差距 72 个百分点)
- `src/envs/kagriculture_env.py:201-222` `reset()` 只重置 `_step_count` 和 `_episode_reward`, 没有重置 `_won`
- `_won` 只在 `__init__` (False) 和 `step()` `done=True` 分支被赋值

## 3. 改动范围

- 文件: `src/envs/kagriculture_env.py`
- 函数: `reset()`
- 行数: +1 行

## 4. 代码改动

```python
# Before (src/envs/kagriculture_env.py:201-222):
def reset(self, seed: Optional[int] = None, options: Optional[Dict] = None) -> Tuple[np.ndarray, Dict]:
    """Reset environment"""
    super().reset(seed=seed)
    self._init_kaggle_env()

    # 初始化
    self._kaggle_env.reset(num_agents=2)

    # 获取初始 observation
    raw_obs = self._kaggle_env.state[0].observation

    self._step_count = 0
    self._episode_reward = 0.0
    # ← _won 没被重置!

    # 获取玩家信息
    farm = raw_obs.farms[self._player_id]
    self._prev_money = farm.get("money", 0)

    # 处理 observation
    processed_obs = self._process_observation(raw_obs)

    return processed_obs, {}


# After:
def reset(self, seed: Optional[int] = None, options: Optional[Dict] = None) -> Tuple[np.ndarray, Dict]:
    """Reset environment"""
    super().reset(seed=seed)
    self._init_kaggle_env()

    # 初始化
    self._kaggle_env.reset(num_agents=2)

    # 获取初始 observation
    raw_obs = self._kaggle_env.state[0].observation

    self._step_count = 0
    self._episode_reward = 0.0
    self._won = False          # ← fix: 重置 episode 内 win flag

    # 获取玩家信息
    farm = raw_obs.farms[self._player_id]
    self._prev_money = farm.get("money", 0)

    # 处理 observation
    processed_obs = self._process_observation(raw_obs)

    return processed_obs, {}
```

## 5. 预期效果

- `info["won"]` 在 reset 之后立即反映 `False`，而不是上一局的 stale 值
- Eval callback `if last_info.get("won", False): wins += 1` 行为更可靠
- Training loss / win_rate: 不直接预测数值变化, 但 rollout/eval 数字开始有意义对比
- 训练稳定性: 持平

## 6. 风险

- **低** — 单行加法, 不动其他逻辑
- 回滚方案: 删除该行即可
- 可能引入的副作用: 无（reset 本来就应该重置所有 episode-level 状态）

## 7. 关联

- 关联 P0-4 (terminal bonus on truncated episodes): 这两个修复合起来, win_rate 评估信号才有意义
- 关联 log-session.md "2026-08-10 晚间更新" 的 train/eval 矛盾分析