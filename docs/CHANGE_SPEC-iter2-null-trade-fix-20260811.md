# CHANGE_SPEC-iter2-null-trade-fix — action format bug + counter reset on real state change

> **Date**: 2026-08-11
> **Author**: Claude (post Phase 2 first iter)
> **Status**: **REVISED** — debug revealed the real root cause is **action format bug** in `main.py`, not reward function. Gemini's reward advice is still valuable for defensive depth.

---

## 1. 问题描述 (UPDATED with debug findings)

Phase 2 iter1 hit `trade_frac=100%`, `win_rate=100%`, but money stayed at ~$3,000 throughout. Gemini attributed this to a "Null/Dummy Trading" reward loophole (counter reset on action type alone). **Debug revealed the actual root cause is a simpler action format bug** in `main.py` and `main_numpy.py`.

### The REAL bug (debug-verified)

`main.py` returns Kaggle actions wrapped in a list of dicts:
```python
return [{"market": [["BUY_PRODUCT", "WHEAT", 1]]}]  # ← list of dicts (Format B)
```

But Kaggle env expects a single dict per player:
```python
return {"market": [["BUY_PRODUCT", "WHEAT", 1]]}  # ← single dict (Format A)
```

**Debug test (30 BUY_PRODUCT actions, kaggle env directly):**

| Format | Result |
|---|---|
| `{"market": [...]}` (A, single dict) | **money 3000→2974→2947→...** (works) |
| `[{"market": [...]}]` (B, list of dicts) | money stays 3000 (silent no-op) |

Kaggle env **silently no-ops** when action is wrapped in a list. So all 229 BUY + 490 SELL in iter1 episodes.json were **never executed** — agent was effectively doing HOLD every step.

### Why `win_rate=100%`

Since all agent actions were no-ops, agent's money stayed at $3,000. Random opponent sometimes does HIRE (-$100) or SELL (depends on wheat). Eventually:
- Agent money: $3,000 (no change)
- Opponent money: ~$2,030 (HIRE cost ate some)
- `p0_money > p1_money` → `won=True` (per P0-4 logic)

So iter1 was **doing nothing + "winning" by survival**, not "trading profitably".

### Verified by re-running iter1 model with FIXED main.py

```python
# Same iter 1 model, but main.py now returns single-dict format:
step   0: $2974   ← money went down 26 (BUY worked!)
step 100: $8      ← almost bankrupt
step 200: $1871   ← recovered via SELL
step 300: $3339   ← stable, SELL > BUY
step 719: $3339   ← terminal
```

**The model IS actually trading** — Phase 2 training is real. The "100% win with flat money" was an artifact of the format bug, not a training failure.

### Gemini's analysis (still valuable)

Even with format fixed, Gemini's reward fix is **defensive**: it prevents the agent from gaming the counter reset if future action-format bugs sneak back in. Specifically:
- Counter reset on `has_real_trade_effect` (not just action type) = double protection
- Empty-trade penalty `-0.01` = discourages low-value trade spam even when action format is correct

But the **immediate** fix is the action format. Reward fix is a follow-up enhancement.

---

## 2. 实验依据

- Phase 2 iter1 `summary.json`: `trade_frac=1.0`, `action_counts={0:0, 1:0, 2:1470, 3:687, 4:0}`, `win_rate=1.0` — full 100% trade but only SELL/BUY
- `episodes.json` money_traj: flat at $3,000 — looks like dummy trading
- **Debug test (this spec)**: confirmed Format B is no-op, Format A works
- **Re-run iter1 model with fixed main.py**: money actually moves $2974→$8→$1871→$3339 — model IS trading
- Gemini's review identified the symptom (zero effect despite high trade_frac) and proposed reward fix; our debug found the deeper cause (action format)

---

## 3. Two-part fix

### Part A (CRITICAL — applied): Fix `main.py` action format

```python
# Before (main.py:235-244):
if action == 0:
    return []  # HOLD
elif action == 1:
    return [{"market": [["HIRE"]]}]                  # ← list of dict (Format B, no-op)
elif action == 2:
    return [{"market": [["SELL", "WHEAT", 1]]}]      # ← Format B
elif action == 3:
    return [{"market": [["BUY_PRODUCT", "WHEAT", 1]]}] # ← Format B
elif action == 4:
    return [{"farmer": ["PASS"]}]                     # ← Format B
else:
    return []

# After (main.py:235-244):
if action == 0:
    return {}  # HOLD — empty dict (Kaggle "no actions this turn")
elif action == 1:
    return {"market": [["HIRE"]]}                     # ← single dict (Format A, works)
elif action == 2:
    return {"market": [["SELL", "WHEAT", 1]]}
elif action == 3:
    return {"market": [["BUY_PRODUCT", "WHEAT", 1]]}
elif action == 4:
    return {"farmer": ["PASS"]}
else:
    return {}
```

**Files changed**: `main.py` (and verify `main_numpy.py` if separate — actually `main.py` IS the submission tarball's main.py)

### Part B (DEFENSIVE — also applied): Gemini's reward robustness fix

Even with Part A, defensively patch the reward to require **real state change** for counter reset. This prevents:
- Future action-format regressions from re-introducing the dummy trade exploit
- Agents gaming the counter by issuing trade-class actions that Kaggle env doesn't execute (e.g., due to other limits we don't know about)

```python
def _compute_reward(self, raw_obs, action, is_valid) -> Tuple[float, Dict]:
    """Iter 2: reset counter ONLY on real state change, not just action type."""
    farm = raw_obs.farms[self._player_id]
    current_money = farm.get("money", 0)
    agent_d = current_money - self._prev_money
    self._prev_money = current_money

    # NEW: track wheat inventory change (no money_d tells us about wheat flows)
    current_wheat = self._kaggle_env.state[0].observation.private.shed.get("WHEAT", 0)
    if not hasattr(self, "_prev_wheat"):
        self._prev_wheat = current_wheat
    wheat_d = current_wheat - self._prev_wheat
    self._prev_wheat = current_wheat

    # Opponent money via dynamic ID
    opp_id = 1 - self._player_id
    opp_money_now = raw_obs.farms[opp_id].get("money", 0)
    if self._prev_opp_money is None:
        self._prev_opp_money = opp_money_now
    opp_d = opp_money_now - self._prev_opp_money
    self._prev_opp_money = opp_money_now

    if self.reward_type == "sparse":
        return 0.0, {"money_delta": agent_d, "opp_money_delta": opp_d,
                     "wheat_delta": wheat_d}

    # Real effect: money OR wheat actually moved
    has_real_trade_effect = (abs(agent_d) > 1e-5) or (abs(wheat_d) > 1e-5)

    # 1. Relative wealth
    reward = (agent_d - 0.4 * opp_d) / 10000.0

    # 2 & 3. Trade bonus + inactivity (FIXED)
    is_trade_action = action in [1, 2, 3]
    if is_valid and has_real_trade_effect:
        # ONLY executed trades clear counter
        self._consecutive_safe = 0
        reward += 0.01
    else:
        # HOLD, PASS, illegal, OR zero-effect trade → counter increments
        self._consecutive_safe += 1
        if is_trade_action and is_valid:
            reward -= 0.01  # punish empty BUY/SELL

    # Inactivity penalty (unchanged)
    if self._consecutive_safe > 5 and self._has_tradeable_state(raw_obs):
        penalty = min(0.10, 0.01 * (self._consecutive_safe - 5))
        reward -= penalty

    # 4. Invalid action penalty (applied in step(), not here)

    # 5. Clip
    reward = float(np.clip(reward, -3.0, 3.0))

    return reward, {"money_delta": agent_d, "opp_money_delta": opp_d,
                    "wheat_delta": wheat_d}
```

### `reset()` and `__init__` updates

```python
# __init__ additions:
self._prev_wheat = None

# reset() additions:
self._prev_wheat = None
```

---

## 4. Why this works

### Part A effect (the critical one)

| Step | Format B (broken) | Format A (fixed) |
|---|---|---|
| 0 (BUY) | `step([action, opp])` — Kaggle sees `action=[{"market":[...]}]`, treats as no-op | `step({"market":[...]}, opp)` — Kaggle deducts $26, adds wheat to shed |
| 1 (BUY) | Same no-op | Deducts $27, adds wheat |
| ... | 230+ BUYs all no-op | 230+ BUYs work, money goes from $3000 → $8 |
| 230+ SELLs | All no-op | All work, money rebounds to $3000+ |

### Part B effect (defensive — even with Part A fixed)

| Scenario | Without Part B | With Part B |
|---|---|---|
| Successful BUY (money −27, wheat +1) | counter=0, +0.008 | counter=0, +0.01 (slightly more reward) |
| Empty BUY (no money change) | counter=0, +0.008 (BAD: clears counter even though no effect) | counter++, −0.01 (penalty for empty trade) |
| HOLD | counter++ | counter++ (unchanged) |

If a future bug makes `_is_action_valid()` over-permissive (e.g., returns True for SELL when shed=0), Part B catches it. Otherwise Part A's fix is sufficient.

---

## 5. 改动范围

| File | Change | Lines |
|---|---|---|
| **`main.py`** (CRITICAL) | `return [...]` → `return {...}` for actions 1-4; `return []` → `return {}` for HOLD/else | 6 lines |
| `src/envs/kagriculture_env.py` (defensive) | `_compute_reward` tracks `_prev_wheat`, gates counter reset on real effect, adds empty-trade penalty | ~10 lines |
| `src/envs/kagriculture_env.py` | `__init__` and `reset()` initialize `self._prev_wheat` | 2 lines |

---

## 6. 训练计划

| Setting | Value | Rationale |
|---|---|---|
| GPU | idle one | Don't disrupt other jobs |
| Opponent | random (Phase 2 default) | Same as iter1 |
| Steps per iter | 280k | Same |
| Iters | 3 | Stop early on success |
| ent_coef | 0.04 (kept) | Same as iter1 |
| Trade threshold | 0.10 (kept) | Same |

### Launch

```bash
GPU=$(nvidia-smi --query-gpu=index,utilization.gpu --format=csv,noheader,nounits | \
  awk -F',' '$2 < 20 {print $1; exit}')

CUDA_VISIBLE_DEVICES=$GPU nohup python -u scripts/eval_loop.py \
    --max_iters 3 \
    --steps_per_iter 280000 \
    --device cuda \
    --opponent random \
    --ent_coef 0.04 \
    --num_eval_eval_episodes 3 \
    --trade_threshold 0.10 \
    > log/eval_loop_iter2.log 2>&1 &
```

### Stop criteria

- `trade_frac >= 10%` AND **money actually changes during episode** (not flat at $3,000)
- `win_rate vs random >= 90%`
- 3 iters done (hard stop)

---

## 7. 风险

| Risk | Mitigation |
|---|---|
| `private.shed` access fails (Struct differs in Kaggle version) | Verified by debug test — `private.shed.get("WHEAT", 0)` works |
| New format breaks the submission tarball (Kaggle rejects) | Format A is documented in kagriculture.json spec; should be accepted |
| Reward Part B causes training instability (`wheat_d` spikes) | Clip ±3 still applies; bounded |
| Part A fix alone is sufficient (Part B unnecessary) | Possible — but Part B is cheap insurance |

### Rollback

For Part A: revert `main.py` (just 6 lines). Phase 2 iter1 model still works (it's already trained). Just won't see effect.

For Part B: revert `_compute_reward` body. The new attributes (`_prev_wheat`) can stay; they're harmless.

---

## 8. References

- [`logs/2026-08-11-model-eval-analysis.md`](../logs/2026-08-11-model-eval-analysis.md) — model sweep
- [`docs/CHANGE_SPEC-phase2-reward-shaping-20260811.md`](CHANGE_SPEC-phase2-reward-shaping-20260811.md) — Phase 2 (just fixed)
- [`log/eval_loop_phase2.log`](../log/eval_loop_phase2.log) — Phase 2 loop output (1 iter done)
- [`eval_reports/iter_01_20260811_054021/`](../eval_reports/iter_01_20260811_054021/) — Phase 2 iter1 results
- [`docs/REWARD_AND_TRAINING_REDESIGN_20260811.md`](REWARD_AND_TRAINING_REDESIGN_20260811.md) — Gemini advice analysis
- [`src/envs/kagriculture_env.py`](../src/envs/kagriculture_env.py) — env to be modified
- [`main.py`](../main.py) — submission tarball entry point (CRITICAL)