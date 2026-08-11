# CHANGE_SPEC-env-dense-reward-scale — reduce dense reward magnitude

> **Date**: 2026-08-10
> **Author**: code-walkthrough session
> **Based on**: code review of `src/envs/kagriculture_env.py` (post SHORT training analysis)

## 1. 问题描述

The dense reward signal `money_delta / 1000` per step dominates the terminal `+10/-5` signal. Concretely:

- A 720-step episode where money grows by ~$5 000 yields dense reward `+5.0`, comparable to a single win bonus of `+10`
- An agent that **never wins** but accumulates money (e.g., trading wheat at small margins) gets high rollout `ep_rew_mean` without ever beating the opponent
- Combined with the now-fixed P0-4 (terminal bonus only on real termination), the agent's signal is still muddied by dense money_delta

This is the **root cause** of the SHORT training's `ep_rew_mean = +5.8` with `eval win_rate = 0%` paradox: the agent optimized money-making, not winning.

## 2. 实验依据

- SHORT training log: rollout `ep_rew_mean ≈ +5.8` but eval `win_rate = 0%` (log-session.md "2026-08-10 晚间更新")
- Magnitude analysis:
  - `money_delta / 1000`: typical per-step delta ~ ±$10–$100 → per-step reward ±0.01–0.1 → per-episode total up to ±72
  - Terminal bonus: ±10 (one-shot at end)
  - **Dense swamps terminal by ~7×**
- WORKFLOW.md P1-6: "Reward Scale 不合理: Reward magnitude 过大或过小, 影响训练稳定性"
- Adjacent fixes: P0-1 done (`_won` reset), P0-4 done (terminal only on real `terminated`)

## 3. 改动范围

- 文件: `src/envs/kagriculture_env.py`
- 函数: `_compute_reward()`
- 行数: 1 line (divisor change)

## 4. 代码改动

```python
# Before (src/envs/kagriculture_env.py:_compute_reward):
def _compute_reward(self, raw_obs) -> Tuple[float, Dict]:
    farm = raw_obs.farms[self._player_id]
    current_money = farm.get("money", 0)
    money_delta = current_money - self._prev_money
    self._prev_money = current_money
    reward_info = {"money_delta": money_delta}
    if self.reward_type == "dense":
        reward = money_delta / 1000.0   # ← too large
    elif self.reward_type == "sparse":
        reward = 0.0
    else:
        reward = money_delta / 1000.0
    return reward, reward_info


# After:
def _compute_reward(self, raw_obs) -> Tuple[float, Dict]:
    farm = raw_obs.farms[self._player_id]
    current_money = farm.get("money", 0)
    money_delta = current_money - self._prev_money
    self._prev_money = current_money
    reward_info = {"money_delta": money_delta}
    if self.reward_type == "dense":
        reward = money_delta / 10000.0  # ← 10× smaller; terminal ±10 dominates
    elif self.reward_type == "sparse":
        reward = 0.0
    else:
        reward = money_delta / 10000.0
    return reward, reward_info
```

## 5. 预期效果

**Magnitude after fix**:
- Per-step dense: ±0.001–0.01 (was ±0.01–0.1)
- Per-episode dense total: ±7.2 max (was ±72)
- Terminal bonus: ±10 (unchanged)
- **Net**: terminal now dominates, dense is a small shaping signal

**Training outcomes**:
- rollout `ep_rew_mean`: 会**下降**（不再被 money_delta 撑高）——从 +5.8 落到 ~+0.5 到 +2 是预期
- eval `win_rate`: 应该**上升**（如果 agent 真的学到了 win）
- training loss: 略升但更稳定（less noisy target）
- value_loss: 应该收敛更快（target less spiky）

## 6. 风险

- **中** — 改了 reward magnitude，PPO 调好的 lr / ent_coef / clip_range 可能需要重新调
- **训练时间影响**: 必须重新跑1M+ steps 才能看到效果
- 回滚方案: 把 `/ 10000.0` 改回 `/ 1000.0`
- 兼容性: 与 P0-1（已修）、P0-4（已修）正交，无冲突

## 7. 关联

- 关联 P0-1 (`_won` reset): 已修
- 关联 P0-4 (terminal bonus on truncated): 已修
- 关联 P0-2 (train/eval env state split): 未修，但本改动独立
- 关联 log-session.md "2026-08-10 晚间更新" 的 train/eval 矛盾分析