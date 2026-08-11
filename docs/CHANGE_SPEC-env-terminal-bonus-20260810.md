# CHANGE_SPEC-env-terminal-bonus — terminal `+10/-5` on truncated episodes

> **Date**: 2026-08-10
> **Author**: code-walkthrough session
> **Based on**: code review of `src/envs/kagriculture_env.py` (post SHORT training analysis)

## 1. 问题描述

`KagricultureEnv.step()` applies the terminal `+10 (win) / -5 (loss)` bonus whenever `done=True`, which is `terminated or truncated`. But:

- `terminated=True` means the Kaggle game itself ended (e.g., one player ran out of money, or some game-end condition)
- `truncated=True` means we hit `MAX_STEPS = 720` (30 days × 24 steps) — the **game didn't end**, we just stopped observing

The current code conflates these and gives a win/loss bonus at step 720 based on `p0_money > p1_money`. This is wrong in two ways:

1. **Pollutes win_rate metric**: an agent that simply had a tiny money lead at step 720 (e.g., $50,001 vs $49,999) gets `won=True` even though it didn't "beat" the opponent in any real sense. Eval callback counts this as a win.

2. **Confuses reward signal**: PPO sees ±15 reward swings on truncated episodes (the diff between +10 win and -5 loss), creating a strong but spurious gradient at the time horizon. Combined with P0-3 (dense reward), the agent can maximize "money at step 720" without ever truly winning.

## 2. 实验依据

- SHORT training log: rollout `ep_rew_mean ≈ +5.8` but eval `win_rate = 0%`. The positive rollout reward is partially explained by truncated episodes awarding ±10/-5 based on whoever has more money at step 720 — not on actual game outcome.
- Code location: `src/envs/kagriculture_env.py:280-291`
  ```python
  terminated = self._kaggle_env.done
  truncated = self._step_count >= MAX_STEPS
  done = terminated or truncated
  if done:
      ...reward += 10.0/-5.0
  ```
- Adjacent P0 fixes: P0-1 (`_won` reset, already applied) — these are paired concerns.

## 3. 改动范围

- 文件: `src/envs/kagriculture_env.py`
- 函数: `step()` (one `if done:` block split into `if terminated:` and `if truncated:`)
- 行数: ~3 lines changed (no net line growth)

## 4. 代码改动

```python
# Before (src/envs/kagriculture_env.py:280-291):
        terminated = self._kaggle_env.done
        truncated = self._step_count >= MAX_STEPS
        done = terminated or truncated

        if done:
            p0_money = new_raw_obs.farms[0].get("money", 0)
            p1_money = new_raw_obs.farms[1].get("money", 0)
            self._won = p0_money > p1_money
            if self._won:
                reward += 10.0
            else:
                reward -= 5.0

# After:
        terminated = self._kaggle_env.done
        truncated = self._step_count >= MAX_STEPS
        done = terminated or truncated

        if terminated:
            # Game ended naturally — apply win/loss bonus.
            p0_money = new_raw_obs.farms[0].get("money", 0)
            p1_money = new_raw_obs.farms[1].get("money", 0)
            self._won = p0_money > p1_money
            if self._won:
                reward += 10.0
            else:
                reward -= 5.0
        elif truncated:
            # Hit MAX_STEPS but the game is still going. Mark _won=False
            # (don't carry over from prior episode; P0-1 fix already resets
            # in reset()). No terminal bonus — it's just a rollout cut-off.
            self._won = False
        # else: episode continues, no terminal logic
```

## 5. 预期效果

- **win_rate metric更可信**: 不再把"step 720 时多 $1 钱"算作赢
- **reward signal更纯**: ±10/-5 只在真正的 game end 时发放
- **训练稳定性**: 持平（reward magnitude 大致不变，移除的是误信号）
- **Training loss**: 略升（PPO 不再被 truncated bonus 误导）
- **rollout ep_rew_mean**: 应该会**下降**——之前 `+5.8` 部分来自 truncated ±10/-5 奖励，现在这些没了。eval win_rate 应该会**上升**（如果 P0-3 也修了，奖励信号才一致）

## 6. 风险

- **中** — 改了 reward 的语义（game end vs rollout cutoff）
- **训练进度影响**: LONG 已停了，影响只是下次重启时。SHORT 训练结果作废（早知如此，但走查流程的代价）
- 回滚方案: 把 `if done:` 改回原样
- 与 P0-1 的协同: `reset()` 已重置 `_won`，但 `step()` 在 truncated 时仍要显式置 False（防止 reset 后立刻 truncated 这种 corner case）

## 7. 关联

- 关联 P0-1 (`_won` reset): 已修复
- 关联 P0-3 (dense reward masking): 是 P0-3 修复后的预期效果放大器——一旦 dense 不再混淆 win/loss，pure sparse win/loss signal 才能生效
- 关联 log-session.md "2026-08-10 晚间更新" 的 train/eval 矛盾分析