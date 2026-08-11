# CHANGE_SPEC-env-action-masks — expose `action_masks()` for MaskablePPO

> **Date**: 2026-08-10
> **Author**: code-walkthrough session
> **Based on**: code review of `src/envs/kagriculture_env.py` (P1-5 from earlier review)

## 1. 问题描述

`KagricultureEnv` has `_is_action_valid()` (`src/envs/kagriculture_env.py:235-263`) which checks legality of actions based on current state (e.g., HIRE needs `money >= 100` and `hires_today > 0`; SELL needs wheat in shed; BUY needs market inventory). But:

- This method is **private** (`_` prefix)
- It is **not exposed** as the Gym-standard `action_masks()` method that MaskablePPO expects
- Therefore the agent cannot learn to avoid illegal actions — it samples them, gets `−0.05` penalty, then the env coerces them to `{}` (HOLD)

This is the **classic "PPO wastes steps on invalid actions" failure mode** flagged in `log-session.md` ("MaskablePPO: 可选, 避免浪费在非法 action") and `docs/03-ACTION-SPACE.md` §7. Even without switching to MaskablePPO, exposing the mask lets any downstream consumer (eval, debugging) skip invalid actions cheaply.

## 2. 实验依据

- `log-session.md` §4.1 reward波动验证: "Valid actions: 69, Invalid actions: 31" over 100 steps → 31% wasted
- `docs/03-ACTION-SPACE.md` §7: action masking designed but not implemented
- WORKFLOW.md P1-5: "Action Mask 遗漏: Invalid actions 没有被正确 mask"
- `_is_action_valid` already encodes the right rules — just needs to be exposed in Gym's expected format

## 3. 改动范围

- 文件: `src/envs/kagriculture_env.py`
- 函数: 新增 `action_masks()` 方法 (Gymnasium ActionMask API)
- 行数: ~8 行

不改 `scripts/train.py`（regular PPO 忽略 `action_masks()`；切换到 MaskablePPO 是另一个 spec）

## 4. 代码改动

```python
# Add to src/envs/kagriculture_env.py after _is_action_valid (around line 263):

def action_masks(self) -> np.ndarray:
    """Gymnasium ActionMask API: which actions are legal in the current state.

    Returns a (action_space.n,) bool array. 1 = legal, 0 = illegal.
    Used by MaskablePPO (sb3-contrib) and any downstream consumer that wants
    to skip invalid actions.

    Note: regular SB3 PPO ignores this method — no behavioral change unless
    the consumer explicitly checks `info["action_mask"]` or the policy is
    swapped for `MaskablePPO`.
    """
    raw_obs = self._kaggle_env.state[0].observation
    mask = np.ones(self.action_space.n, dtype=np.int8)
    for a in range(self.action_space.n):
        if not self._is_action_valid(a, raw_obs):
            mask[a] = 0
    return mask
```

```python
# Optional: also expose the mask in info dict for visibility in eval.
# In step(), add to the info dict:
info = {
    "episode_reward": self._episode_reward,
    "step": self._step_count,
    "money": new_raw_obs.farms[self._player_id].get("money", 0),
    "won": self._won,
    "is_valid_action": is_valid,
    "action_mask": self.action_masks(),   # ← NEW:，方便 eval / debug
    **reward_info
}
```

## 5. 预期效果

- **数据流**: env 现在暴露 `action_masks()` 方法（标准 Gym API）+ `info["action_mask"]` 字段
- **当前 SB3 PPO 行为**: 不变 (regular PPO 不读 `action_masks`)
- **未来切换 MaskablePPO 时**: 零额外改动，policy 自动读 mask
- **Eval / debug**: 现在可以直接用 `env.action_masks()` 检查状态-合法性映射，调试 action 选择的合理性

## 6. 风险

- **低** — 纯加法, 不改任何已有路径
- 调用 `action_masks()` 自身的开销: O(action_space.n) 次 `_is_action_valid` 调用，每次~5 个 attribute access ~1μs，总 ~5μs/call。可忽略。
- 回滚方案: 删掉 `action_masks()` 方法和 `info["action_mask"]` 字段即可

## 7. 关联

- 关联 P0 修复：纯净的 reward 信号 + 共享 kaggle_env 已经让 PPO 信号有效，再加 mask 让 PPO 学习更高效
- 关联未来工作: 切换到 MaskablePPO（sb3-contrib）以真正利用 mask（单独的 spec/CHANGE_SPEC）
- 关联 `docs/03-ACTION-SPACE.md` §7: 这个 spec 让 §7 的设计真正落地