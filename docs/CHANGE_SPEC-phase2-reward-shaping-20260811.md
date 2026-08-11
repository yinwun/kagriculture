# CHANGE_SPEC-phase2-reward-shaping — trade bonus + inactivity penalty + relative reward

> **Date**: 2026-08-11
> **Author**: Claude (post Phase 1 failure)
> **Based on**: Phase 1 failed ([`docs/REWARD_AND_TRAINING_REDESIGN_20260811.md`](REWARD_AND_TRAINING_REDESIGN_20260811.md) §5 Phase 2) + Gemini advice analysis
> **Pre-flight check**: 5 Phase 1 iters all hit 0% trade_frac. **Root cause confirmed**: random opponent does nothing, so HOLD/PASS "wins" by default. ent_coef=0.04 not enough. Reward function must be changed.
> **Status**: Draft revised with Gemini corrections (2026-08-11 PM)

## Gemini review — 3 critical bugs found

Gemini reviewed the initial draft and identified **3 logic bugs + 1 hardcode bug** that would have made Phase 2 unstable:

### Bug 1: Sugar Rush Exploit (致命套利)
- Trade bonus `+0.05` > HIRE money penalty (`-100/10000 = -0.01`)
- Net per HIRE step: `+0.04` even when losing money
- Agent would learn "spend money to farm trade bonus" instead of "trade profitably"

### Bug 2: Counter Bypass (消极计数清零漏洞)
- Original: any non-HOLD/PASS action resets `_consecutive_safe = 0`
- Agent can issue illegal actions (e.g. BUY with no money, costing `-0.05`) to reset penalty and avoid further `-0.01 * (n-5)` increments
- Net: illegal action (-0.05) cheaper than continued HOLD (-0.10+)

### Bug 3: Value Loss Explosion
- Inactivity penalty `-0.01 * (n-5)` unbounded
- Step 300: single-step penalty `-2.95` (after clip -3, but value target still oscillates wildly)
- Value network prediction targets become unstable → PPO gradient explodes

### Bug 4: Hardcoded Opponent Index
- `self._kaggle_env.state[1].observation.farms[1]` is wrong if `self._player_id == 1`
- Should use dynamic `opp_id = 1 - self._player_id`

## Gemini's corrections (all applied in §6 below)

1. **Trade bonus** `0.05 → 0.008` (must be `< money_penalty = 0.01` so single HIRE is net-negative)
2. **Counter reset** only on `is_trade_action AND is_valid` (illegal actions keep counter growing)
3. **Penalty cap** `min(0.10, 0.01 * (n-5))` (prevents Value Loss explosion)
4. **Opponent ID** `opp_id = 1 - self._player_id` (dynamic)

---

## 1. 问题描述

Phase 1 (random opponent + ent_coef=0.04) failed to teach trade. All 5 iters showed `trade_frac = 0.00%`, `win_rate = 100%` (because random opponent also does nothing). The agent's optimal strategy is to never trade, since trade actions cost `-0.05` invalid penalty or risk losing money, while HOLD/PASS is free.

**Gemini's diagnosis (confirmed by data)**:
- Without an opponent-relative reward, agent has no incentive to catch up
- Without an inactivity penalty, HOLD/PASS is the cheapest safe action
- Without an explicit trade bonus, the policy has no positive gradient toward HIRE/SELL/BUY

**Phase 2 goal**: rewrite the reward function so HOLD/PASS is no longer the dominant equilibrium.

---

## 2. 实验依据

- Phase 1 log: `log/eval_loop_phase1.log` — 5 iters, all `trade_frac=0.0`
- Phase 1 train_eval.csv (iter_01): win_rate=100% at step 50K–150K (agent never trades, opponent does nothing, "win" by survival) → collapses to 0% only after opponent random actions occasionally eat money, but agent never learns to trade in response
- Phase 1 iter_02 summary: `action_dist={0: 2157}` — 100% HOLD
- Phase 1 iter_01 summary: `action_dist={4: 2157}` — 100% PASS
- Gemini advice: trade bonus + relative reward + inactivity penalty (see `docs/REWARD_AND_TRAINING_REDESIGN_20260811.md` §2)

---

## 3. Reward function redesign

### Current reward (after P0-3 + P0-4)

```python
def _compute_reward(self, raw_obs):
    money_delta = current_money - self._prev_money
    if reward_type == "sparse":
        reward = 0.0
    else:
        reward = money_delta / 10000.0   # P0-3
    return reward, {"money_delta": money_delta}

def step(self, action):
    reward += invalid_penalty  # -0.05 if invalid
    if terminated:  # P0-4: only on real game-end
        if won:
            reward += 10.0  # Phase 2 will change to 8.0 (see below)
        else:
            reward += -5.0  # Phase 2 will change to -4.0 (see below)
```

### Phase 2 reward (Gemini-corrected)

```python
def _compute_reward(self, raw_obs, action, is_valid):
    """Phase 2 reward: relative wealth + trade bonus + capped inactivity penalty.

    Gemini-corrected (2026-08-11):
      * trade bonus 0.05 → 0.008  (must be < HIRE cost 0.01, else Sugar Rush)
      * counter reset ONLY on (action in [1,2,3] AND is_valid)
        (illegal actions KEEP counter growing — prevents -0.05 bypass)
      * penalty capped at min(0.10, 0.01*(n-5))
        (prevents Value Loss explosion when agent stuck idle)
    """
    farm = raw_obs.farms[self._player_id]
    current_money = farm.get("money", 0)
    agent_d = current_money - self._prev_money
    self._prev_money = current_money

    # Opponent money for relative reward — use dynamic ID, NOT hardcoded farms[1]
    # (Gemini bug 4 fix: when self._player_id == 1, opponent is farms[0])
    opp_id = 1 - self._player_id
    opp_money_now = raw_obs.farms[opp_id].get("money", 0)
    if self._prev_opp_money is None:
        self._prev_opp_money = opp_money_now
    opp_d = opp_money_now - self._prev_opp_money
    self._prev_opp_money = opp_money_now

    if self.reward_type == "sparse":
        # Sparse mode: only terminal bonus (added in step()). Per-step = 0.
        return 0.0, {"money_delta": agent_d, "opp_money_delta": opp_d}

    # 1. Relative wealth (replaces dense /10000)
    reward = (agent_d - 0.4 * opp_d) / 10000.0

    # 2 & 3. Trade bonus + inactivity counter (Gemini-corrected)
    is_trade_action = action in [1, 2, 3]
    if is_trade_action and is_valid:
        # ONLY successful trades clear the inactivity counter
        self._consecutive_safe = 0
        reward += 0.008  # < HIRE money cost (0.01) → HIRE is net-negative
    else:
        # HOLD, PASS, AND illegal trade attempts all increment counter
        self._consecutive_safe += 1

    # Inactivity penalty with cap (Gemini bug 3 fix)
    if self._consecutive_safe > 5 and self._has_tradeable_state(raw_obs):
        penalty = min(0.10, 0.01 * (self._consecutive_safe - 5))
        reward -= penalty

    # 4. Clip
    reward = float(np.clip(reward, -3.0, 3.0))

    return reward, {"money_delta": agent_d, "opp_money_delta": opp_d}
```

### Helper

```python
def _has_tradeable_state(self, raw_obs) -> bool:
    """True if agent CAN trade (money ≥ HIRE cost OR wheat in shed).

    Inactivity penalty only applies when this is True — otherwise HOLD/PASS
    is the only legal action and should not be punished.
    """
    farm = raw_obs.farms[self._player_id]
    private = raw_obs.private
    shed = private.shed if isinstance(private.shed, dict) else {}
    money = farm.get("money", 0)
    wheat = shed.get("WHEAT", 0)
    return money >= 100 or wheat > 0
```

### State to track across steps

- `self._consecutive_safe`: int, reset to 0 on `(action in [1,2,3] AND is_valid)`, incremented on HOLD/PASS/illegal
- `self._prev_money`: existing, money tracking
- `self._prev_opp_money`: NEW, opponent money tracking (init to None; set on first step)

---

## 4. Magnitude budget (per episode, Gemini-corrected)

| Component | Magnitude | Times per episode | Cumulative |
|---|---|---|---|
| 1. Relative wealth | ±0.001–0.01 per step | 720 | ±0.7–7.2 |
| 2. Trade bonus | **+0.008** per valid trade (was 0.05) | ~50 (if active) | **+0.4** |
| 3. Inactivity penalty | **min(-0.10, -0.01 × (n-5))** per step (capped) | ~100 (if inactive) | **bounded ≤ -0.10/step** |
| 4. Invalid penalty | -0.05 per invalid | ~50 | -2.5 |
| 5. Terminal | +8 / -4 once | 1 | ±4 |
| 6. Clip | -3 to +3 | per step | bounded |

**Net effect per HIRE (valid, with $100 cost)**:
- Money: `-100 / 10000 = -0.01`
- Trade bonus: `+0.008`
- **Net: -0.002** (slightly negative — agent must trade *profitably*, not just trade)

**Net effect per HOLD/PASS (consecutive, has tradeable state)**:
- After 10 steps: `-0.10` (capped)
- After 100 steps: `-0.10` (capped — no Value Loss explosion)
- After 200 steps: `-0.10` (capped)

**Net effect per invalid action**:
- `-0.05` penalty + counter++ → keeps inactivity penalty growing

### Why this should work (Gemini-corrected)

- **Per step**: dense signal ~±0.01 (similar to P0-3)
- **Per trade**: `+0.008` bonus, NOT enough to overcome money loss on bad trades
- **Per inactivity**: small penalty so 100 idle steps = max `-0.10/step` (one loss)
- **Terminal**: still `±8`, the dominant signal
- **Net**: smart trade actions (gain money) yield positive reward; HOLD/PASS without trade costs -0.10/step → must trade OR lose
- **No Sugar Rush**: trade bonus < HIRE cost → can't profit by spam-trading
- **No Bypass**: illegal actions can't reset counter
- **No Value Loss Explosion**: penalty capped at -0.10/step

---

## 5. 改动范围

| File | Change | Lines |
|---|---|---|
| `src/envs/kagriculture_env.py` | `_compute_reward` signature + body, add `_has_tradeable_state` helper, add `_consecutive_safe` + `_prev_opp_money` state | ~30 lines |
| `src/envs/kagriculture_env.py` | `step()` call site passes new args | ~5 lines |
| `src/envs/kagriculture_env.py` | `reset()` clears `_consecutive_safe` and `_prev_opp_money` | ~3 lines |
| `src/envs/kagriculture_env.py` | Constructor initializes new state | ~3 lines |

No changes to action mapping, observation, training script, or eval loop.

---

## 6. 代码改动 (详细)

### `__init__`

```python
# Before:
self._won = False
self._player_id = 0

# After:
self._won = False
self._player_id = 0
self._consecutive_safe = 0   # NEW: counter for inactivity penalty
self._prev_opp_money = None   # NEW: opponent money for relative reward
```

### `reset()`

```python
# Before:
self._step_count = 0
self._episode_reward = 0.0
self._won = False  # P0-1 fix

# After:
self._step_count = 0
self._episode_reward = 0.0
self._won = False  # P0-1 fix
self._consecutive_safe = 0   # NEW: reset inactivity counter
self._prev_opp_money = None   # NEW: will be set on first step
```

### `step()`

```python
# Before (calls _compute_reward):
reward, reward_info = self._compute_reward(new_raw_obs)

# After:
reward, reward_info = self._compute_reward(
    new_raw_obs,
    action=action,
    is_valid=is_valid,
    # NOTE: opp_money reading moved INTO _compute_reward (Gemini bug 4 fix)
)
```

### `_compute_reward` (full rewrite, Gemini-corrected)

```python
def _compute_reward(self, raw_obs, action, is_valid):
    """Phase 2 reward: relative wealth + trade bonus + capped inactivity penalty.

    Gemini corrections (2026-08-11):
      * trade bonus 0.05 → 0.008 (Gemini bug 1: Sugar Rush)
      * counter reset ONLY on (action in [1,2,3] AND is_valid) (Gemini bug 2: Bypass)
      * penalty capped at min(0.10, 0.01*(n-5)) (Gemini bug 3: Value Loss)
      * opp_id dynamic, no hardcoded farms[1] (Gemini bug 4: hardcode)
    """
    farm = raw_obs.farms[self._player_id]
    current_money = farm.get("money", 0)
    agent_d = current_money - self._prev_money
    self._prev_money = current_money

    # Phase 2: opponent money via dynamic ID
    opp_id = 1 - self._player_id  # Gemini bug 4 fix
    opp_money_now = raw_obs.farms[opp_id].get("money", 0)
    if self._prev_opp_money is None:
        self._prev_opp_money = opp_money_now  # first step init
    opp_d = opp_money_now - self._prev_opp_money
    self._prev_opp_money = opp_money_now

    if self.reward_type == "sparse":
        return 0.0, {"money_delta": agent_d, "opp_money_delta": opp_d}

    # 1. Relative wealth
    reward = (agent_d - 0.4 * opp_d) / 10000.0

    # 2 & 3. Trade bonus + inactivity counter (Gemini-corrected)
    is_trade_action = action in [1, 2, 3]
    if is_trade_action and is_valid:
        # ONLY successful trades reset counter
        self._consecutive_safe = 0
        reward += 0.008  # < HIRE cost 0.01 → HIRE is net-negative
    else:
        # HOLD, PASS, illegal → counter increments
        self._consecutive_safe += 1

    # Inactivity penalty with cap
    if self._consecutive_safe > 5 and self._has_tradeable_state(raw_obs):
        penalty = min(0.10, 0.01 * (self._consecutive_safe - 5))
        reward -= penalty

    # 4. Clip
    reward = float(np.clip(reward, -3.0, 3.0))

    return reward, {"money_delta": agent_d, "opp_money_delta": opp_d}

def _has_tradeable_state(self, raw_obs):
    """True if agent CAN make a valid trade (has money for HIRE or wheat in shed)."""
    farm = raw_obs.farms[self._player_id]
    private = raw_obs.private
    shed = private.shed if isinstance(private.shed, dict) else {}
    money = farm.get("money", 0)
    wheat = shed.get("WHEAT", 0)
    return money >= 100 or wheat > 0
```

### Terminal block (in `step()`)

```python
# Before:
if terminated:
    if self._won:
        reward += 10.0
    else:
        reward += -5.0

# After:
if terminated:
    if self._won:
        reward += 8.0   # was 10.0
    else:
        reward += -4.0  # was -5.0
```

---

## 7. 训练计划

| Setting | Value | Rationale |
|---|---|---|
| GPU | cuda:0 OR cuda:1 (whichever is idle) | Either works; one GPU at a time |
| Opponent | start with random (Phase 1 default), can flip to trained later | Phase 2 reward should work vs either |
| Steps per iter | 280k | Same as before |
| Iters | 3 | Stop early on success |
| ent_coef | 0.04 (Phase 1 default kept) | Don't change two things at once |
| Trade threshold | 0.10 (kept from Phase 1) | Conservative for first Phase 2 iter |

### Launch

```bash
# Pick idle GPU
GPU=$(nvidia-smi --query-gpu=index,utilization.gpu --format=csv,noheader,nounits | \
  awk -F',' '$2 < 20 {print $1; exit}')
echo "Using GPU $GPU"

CUDA_VISIBLE_DEVICES=$GPU nohup python -u scripts/eval_loop.py \
    --max_iters 3 \
    --steps_per_iter 280000 \
    --device cuda \
    --opponent random \
    --ent_coef 0.04 \
    --num_eval_episodes 3 \
    --trade_threshold 0.10 \
    > log/eval_loop_phase2.log 2>&1 &
```

### Stop criteria

- `trade_frac >= 10%` (early stop)
- `win_rate vs random >= 90%` (early stop)
- 3 iters done (hard stop)

---

## 8. 预期效果

| Metric | Phase 1 (broken) | Phase 2 (expected) |
|---|---|---|
| trade_frac | 0% | **≥ 10%** within iter 1 |
| Inactivity counter in `_consecutive_safe` | n/a (always 0 or huge) | bounded (penalty kicks in) |
| `mean_reward` per step | around 0 (no signal) | positive when trade / negative when idle |
| Iter time | 22 min | ~22 min (unchanged) |

### What "success" looks like

- iter_01 reports `trade_frac ≥ 10%`
- `action_dist` shows HIRE/SELL/BUY > 0
- `replay.html` shows colored trade pills appearing within first 100 steps
- `summary.json` `trade_frac > 0.05`

### What "failure" looks like

- Still 0% trade → trade bonus too small or inactivity penalty too small
- 100% trade but 0% win → trades are bad (need better reward shaping)
- High trade + high win → SUCCESS, ready to try trained opponent

---

## 9. 风险

| Risk | Likelihood | Mitigation |
|---|---|---|
| Trade bonus too aggressive → agent does bad trades | Medium | Cap to 0.05 (not 0.10); monitor win_rate |
| Inactivity penalty too aggressive → frantic HIRE loop | Low | Gated on `_has_tradeable_state` (only when has money/wheat) |
| Relative reward too noisy (random opp has high variance) | Medium | α=0.4 conservative; can lower later |
| Total reward magnitude shifts → existing hyperparams need retuning | Medium | Keep ent_coef=0.04 unchanged; monitor policy_loss |
| `opp_money` reading fails (state[1] missing during reset) | Low | Use `try/except` + default to 0 |

### Rollback plan

Revert `src/envs/kagriculture_env.py` to last git commit (or manually re-apply P0-1, P0-2, P0-3, P0-4, P1-5 fixes only — no Phase 2).

Or: `--reward_type sparse` already exists as an env constructor arg; can use it to bypass Phase 2 reward without code revert (will lose Phase 2 features but keep P0 fixes).

---

## 10. 设计权衡 (for Gemini to challenge)

1. **Why 0.05 trade bonus, not 0.10 or 0.01?**
   - 0.05 / step = +2.5 per 50 trades, comparable to one terminal win (+8). Big enough to matter.
   - 0.10 / step = +5 per 50 trades, would dominate terminal. Risk of "spam trade for points".
   - 0.01 / step = +0.5 per 50 trades, too weak to overcome HOLD/PASS inertia.

2. **Why α=0.4 for relative reward, not 0.8 (Gemini's value) or 0.2?**
   - α=0.8 might overwhelm the per-agent money delta (agent sees opp gain as huge penalty).
   - α=0.4 means 40% of opp's gain is subtracted from agent's reward. Balanced.
   - α=0.2 might be too weak to create real pressure.

3. **Why inactivity starts at >5 steps, not >3?**
   - 5 gives the agent 5 free HOLD/PASS at episode start (when state is poor).
   - 3 would penalize too early.
   - Why -0.01 per step above threshold (not -0.05)?
   - Keeps penalty small; -0.05/step would dominate the +0.05 trade bonus.

4. **Why clip at ±3.0?**
   - Trade bonus + trade penalty stack could spike.
   - ±3 is enough headroom for normal steps; extreme spikes get clipped.

5. **Why keep P0-3 dense (relative wealth /10000), not just remove dense?**
   - Without dense, only terminal ±8 fires — sparse reward, slow PPO convergence.
   - /10000 normalizes agent wealth change to similar scale as relative reward.

6. **Why keep P0-4 (terminal only on terminated)?**
   - Still correct: don't reward "won by step 720 cutoff".
   - Phase 2 just changes the magnitude (±8 instead of ±10), not the trigger.

7. **Could we just remove HOLD/PASS from the action space?**
   - Yes, in Phase 4 (MaskablePPO with action masking). For Phase 2 we keep them
     but make them costly.

8. **What if agent learns to spam HIRE every step (to get trade bonus)?**
   - `_has_tradeable_state()` gates the inactivity penalty, not the trade bonus.
   - So spam HIRE works for trade bonus (+0.05/step) but loses money.
   - Relative reward (agent_d - 0.4*opp_d)/10000 punishes self-money loss.
   - Net: spam HIRE ≈ -0.05 per step (money_loss) + 0.05 (trade bonus) ≈ 0. So no net gain.
   - Good: only smart trades (gain money) yield positive reward.

9. **Doesn't Phase 2 reward design favor trading even when opponent is weak?**
   - Yes. Trade bonus is opponent-independent. That's the point: trade should always be slightly incentivized.
   - But the relative reward part depends on opponent; vs random opponent, opp_d ≈ 0, so
     relative reward ≈ agent_d / 10000. Agent still incentivized to grow own money via smart trades.

10. **Why expose reward_type CLI arg already exists but not used?**
    - It exists for backward compat. Phase 2 doesn't need to add new CLI args.
    - We can add `--phase2_reward {on,off}` later if needed.

---

## 11. References

- [`docs/REWARD_AND_TRAINING_REDESIGN_20260811.md`](REWARD_AND_TRAINING_REDESIGN_20260811.md) — Gemini advice analysis
- [`logs/2026-08-11-model-eval-analysis.md`](../logs/2026-08-11-model-eval-analysis.md) — model sweep
- [`docs/CHANGE_SPEC-phase1-random-curriculum-20260811.md`](CHANGE_SPEC-phase1-random-curriculum-20260811.md) — Phase 1 spec (failed)
- [`docs/TRAINING_SPEC.md`](TRAINING_SPEC.md) — current code spec
- [`log/eval_loop_phase1.log`](../log/eval_loop_phase1.log) — Phase 1 run (5 iters, all 0% trade)
- [`src/envs/kagriculture_env.py`](../src/envs/kagriculture_env.py) — env code to be modified

---

## 12. Verbatim code diff preview (for review)

```diff
--- a/src/envs/kagriculture_env.py
+++ b/src/envs/kagriculture_env.py
@@ class KagricultureEnv:
     def __init__(self, ...):
         self._won = False
         self._player_id = 0
+        self._consecutive_safe = 0
+        self._prev_opp_money = None

     def reset(self, ...):
         self._step_count = 0
         self._episode_reward = 0.0
         self._won = False  # P0-1 fix
+        self._consecutive_safe = 0
+        self._prev_opp_money = None
         ...

     def step(self, action):
         ...
         is_valid = self._is_action_valid(action, raw_obs)
         invalid_penalty = 0.0
         if not is_valid:
             action_str = {}
             invalid_penalty = -0.05
         else:
             action_str = self._action_to_kaggle(action)
         opponent_action = self._get_opponent_action()
         self._kaggle_env.step([action_str, opponent_action])
         new_raw_obs = self._kaggle_env.state[0].observation

+        # Phase 2: pass action+is_valid. opp_money is read inside _compute_reward
+        # via dynamic opp_id = 1 - self._player_id (Gemini bug 4 fix).
-        reward, reward_info = self._compute_reward(new_raw_obs)
+        reward, reward_info = self._compute_reward(
+            new_raw_obs,
+            action=action,
+            is_valid=is_valid,
+        )
         reward += invalid_penalty

         terminated = self._kaggle_env.done
         truncated = self._step_count >= MAX_STEPS
         done = terminated or truncated

         if terminated:
             p0_money = new_raw_obs.farms[0].get("money", 0)
             p1_money = new_raw_obs.farms[1].get("money", 0)
             self._won = p0_money > p1_money
             if self._won:
-                reward += 10.0
+                reward += 8.0   # Phase 2: was 10.0
             else:
-                reward += -5.0
+                reward += -4.0   # Phase 2: was -5.0
         elif truncated:
             self._won = False

-    def _compute_reward(self, raw_obs) -> Tuple[float, Dict]:
+    def _compute_reward(self, raw_obs, action, is_valid) -> Tuple[float, Dict]:
         farm = raw_obs.farms[self._player_id]
         current_money = farm.get("money", 0)
-        money_delta = current_money - self._prev_money
+        agent_d = current_money - self._prev_money
         self._prev_money = current_money
-        reward_info = {"money_delta": money_delta}
+
+        # Phase 2: opponent money via dynamic ID (Gemini bug 4 fix)
+        opp_id = 1 - self._player_id
+        opp_money_now = raw_obs.farms[opp_id].get("money", 0)
+        if self._prev_opp_money is None:
+            self._prev_opp_money = opp_money_now
+        opp_d = opp_money_now - self._prev_opp_money
+        self._prev_opp_money = opp_money_now
+
+        if self.reward_type == "sparse":
+            return 0.0, {"money_delta": agent_d, "opp_money_delta": opp_d}
+
+        # 1. Relative wealth (replaces dense /10000)
+        reward = (agent_d - 0.4 * opp_d) / 10000.0
+
+        # 2 & 3. Trade bonus + inactivity counter (Gemini-corrected)
+        is_trade_action = action in [1, 2, 3]
+        if is_trade_action and is_valid:
+            # Only successful trades clear counter
+            self._consecutive_safe = 0
+            reward += 0.008  # < HIRE cost 0.01 → HIRE is net-negative (no Sugar Rush)
+        else:
+            # HOLD, PASS, illegal → counter increments
+            self._consecutive_safe += 1
+        if self._consecutive_safe > 5 and self._has_tradeable_state(raw_obs):
+            # Capped penalty — prevents Value Loss explosion (Gemini bug 3)
+            reward -= min(0.10, 0.01 * (self._consecutive_safe - 5))
+
+        # 4. Invalid penalty (applied here AND in step(), but step() will double-apply)
+        #    Actually invalid penalty is applied in step() after _compute_reward returns;
+        #    we don't apply it in _compute_reward to avoid double-counting.
+
+        # 5. Clip
+        reward = float(np.clip(reward, -3.0, 3.0))
+
-        if self.reward_type == "sparse":
-            reward = 0.0
-        else:
-            reward = money_delta / 10000.0  # P0-3
-        return reward, {"money_delta": money_delta}
+        return reward, {"money_delta": agent_d, "opp_money_delta": opp_d}

+    def _has_tradeable_state(self, raw_obs) -> bool:
+        """True if agent CAN make a valid trade (has money for HIRE or wheat in shed)."""
+        farm = raw_obs.farms[self._player_id]
+        private = raw_obs.private
+        shed = private.shed if isinstance(private.shed, dict) else {}
+        money = farm.get("money", 0)
+        wheat = shed.get("WHEAT", 0)
+        return money >= 100 or wheat > 0
```

---

## 13. Review checklist for Gemini

Please critique:

1. **Magnitudes**: are 0.05 (trade), 0.01 (inactivity), 0.4 (alpha), ±8/±4 (terminal), ±3 (clip) reasonable?
2. **Gate**: is `_has_tradeable_state()` correctly checking "can trade"? Should it also check `hires_today > 0` for HIRE eligibility?
3. **Missing components**: are there other mechanisms we should add (e.g., terminal-only "trade in last 50 steps" bonus to push urgency at endgame)?
4. **Inactivity counter reset**: I reset to 0 on ANY non-HOLD/PASS action (idx 0 or 4). Should illegal-trade attempts also reset (so agent isn't punished for trying)?
5. **Opponent money reading**: `state[1].observation.farms[1]` — is this reliable across Kaggle env resets, or do we need a guard for first step?
6. **Reward clipping at ±3**: should it be tighter (±2) to prevent spikes, or looser (±5) to allow bigger swings?
7. **Terminal scale (was ±10/±5, now ±8/±4)**: is this the right balance, or should we keep ±10/±5 and just clip?
8. **Relative reward vs sparse reward toggle**: should we make Phase 2 reward contingent on a `--phase2_reward` flag so we can A/B test vs the current P0 reward?

---

## 14. Sign-off

Once Gemini approves (or suggests tweaks), I will:
1. Apply the diff above to `src/envs/kagriculture_env.py`
2. Smoke-test in isolation (single 720-step episode)
3. Launch Phase 2 loop on idle GPU
4. Wait for first iter, verify `trade_frac > 0%`
5. If success → Phase 2 iter 2 / 3. If still 0% → escalate to Phase 3 (MaskablePPO).