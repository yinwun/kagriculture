# Reward Function & Training Strategy Redesign — Gemini advice evaluation
> **Date**: 2026-08-11
> **Status**: Analysis of Gemini's recommended changes vs current state. Phased implementation plan proposed.
> **Related**: [`logs/2026-08-11-model-eval-analysis.md`](../logs/2026-08-11-model-eval-analysis.md) (the model sweep that triggered this discussion)

---

## TL;DR — evaluation of Gemini's advice

Gemini's diagnosis is **95% correct** — the "躺平陷阱 / Passive Policy Collapse" framing matches our observed data exactly. Its solutions are **80% applicable**, with some magnitude risks not addressed. We propose a **3-phase implementation** starting with the highest-impact changes (curriculum learning, ent_coef bump) and gating later phases on whether the current in-progress training shows any trade-action recovery.

---

## 1. Diagnosis — Gemini's claims vs our data

### Gemini claim 1: Passive / Safe Policy Collapse

> "PPO converges to a local optimum that minimizes penalty — doing nothing at all."

**Status: ✓ CONFIRMED**

Evidence from `eval_models.py` run:

| Model | SELL | BUY | HIRE | PASS | HOLD | Trade % | Interpretation |
|---|---|---|---|---|---|---|---|
| ppo_v5_short (1M steps, NEW dense /10000) | 141 | 0 | 0 | 597 | 1419 | 6.5% | Partial collapse |
| iter_01..04 (280K steps each, NEW dense /10000) | 0 | 0 | 0 | varies | varies | 0% | Full collapse |
| ppo_v3 (5M steps, OLD dense /1000) | 0 | 0 | 0 | 2157 | 0 | 0% | Full collapse |
| ppo_v4_short (2.5M steps, OLD dense /1000) | 0 | 0 | 0 | 2157 | 0 | 0% | Full collapse |

**Trade-action fraction correlates negatively with training time after about 1M steps.** This is the textbook Passive Policy Collapse.

### Gemini claim 2: Absolute vs Relative wealth gap

> "HOLD gives $0 penalty while opponent accumulates money. Without relative penalty, agent thinks 'I'm not losing'."

**Status: ✓ CORRECT DIAGNOSIS**

The env currently uses `money_delta / 10000` per step, which means the agent is rewarded for its own money changes but ignores the opponent's. If both agent and opponent do nothing, both stay flat → agent thinks it's winning. If only opponent trades and grows, agent's reward signal is neutral → no pressure to catch up.

### Gemini claim 3: Dense reward too compressed

> "÷ 10000 makes reward signal near zero, advantages can't differentiate good vs bad trades."

**Status: ⚠️ PARTIALLY CORRECT, RISK OF OVER-CORRECTING**

Our pre-P0-3 code used `÷ 1000`, which was too big (PPO could game `money_delta` to fake "winning"). After P0-3 it's `÷ 10000`, which Gemini correctly identifies as too small. But going back to `÷ 1000` would re-introduce the original spoofing. The right answer is somewhere in between, plus other mechanisms (relative reward, terminal signal, action bonuses) to provide signal at multiple time scales.

### Gemini claim 4: Missing opponent-relative penalty

> "If opponent grows and agent doesn't, agent gets no signal that it's falling behind."

**Status: ✓ CORRECT, RELATED TO #2**

Same root cause as #2. This is why Gemini's proposed `R_relative = ΔWealth_agent - α · ΔWealth_opponent` is a good fix.

---

## 2. Gemini's proposed fixes — evaluation

### Fix 1. Relative wealth difference reward

> `R_relative = (ΔWealth_agent - α · ΔWealth_opponent)`

| Aspect | Evaluation |
|---|---|
| Solves the right problem? | ✓ Yes — directly addresses the "躺平" root cause |
| Magnitude | ⚠️ α=0.8 might be too aggressive; recommend α=0.3–0.5 |
| Stability | ⚠️ Opponent's money change is non-stationary; may hurt PPO convergence |
| Implementation cost | Low — env already tracks `opp_money` from RF inference |

**Verdict: ✓ Implement, with α=0.4**

### Fix 2. Inactivity penalty (consecutive HOLD/PASS)

> `if consecutive_holds > 3: penalty = -0.01 * (consecutive_holds - 3)`

| Aspect | Evaluation |
|---|---|
| Solves the right problem? | ✓ Yes — directly penalizes the collapse mode |
| Magnitude | ✓ Small (-0.01/step) is appropriate |
| Risk | ⚠️ Could push agent toward **frantic action** (HIRE every step) instead of smart action. Need to gate the penalty so it only applies when the env has tradeable resources (money for HIRE, wheat for SELL) |
| Implementation cost | Low — track `_consecutive_safe_count` in env |

**Verdict: ✓ Implement with gating — only apply penalty if env has tradeable state**

### Fix 3. VecNormalize / dynamic reward scaling

> Use SB3 VecNormalize or running σ normalization

| Aspect | Evaluation |
|---|---|
| Solves the right problem? | ✓ Yes — keeps gradient signal alive |
| Magnitude | ✓ Adaptive |
| Stability | ✓ Designed for PPO |
| Implementation cost | ⚠️ Medium — VecNormalize expects VecEnv; we have single-env. Need wrapper class or env-side tracking |
| Risk | ⚠️ Online σ with non-stationary signal (opponent behavior) can be unstable |

**Verdict: ⏸ DEFER — too complex for now, monitor P0 fixes first**

### Fix 4. Trade shaping (per-step trade bonus + sparse terminal)

> `+0.02 for valid trade action`, `±2.0 terminal` (vs current ±10)

| Aspect | Evaluation |
|---|---|
| Solves the right problem? | ✓ Yes — explicit positive signal for trade |
| Magnitude | ⚠️ 0.02 per trade × 100 trades = 2.0 cumulative, comparable to terminal. Not too big. |
| Risk | ⚠️ Reducing terminal from ±10 to ±2 might re-flatten the win signal. Keep ±5 to ±8. |
| Implementation cost | Low |

**Verdict: ✓ Implement, but keep terminal at ±8 (not ±2)**

---

## 3. Gemini's training strategy — evaluation

### Strategy 1. Curriculum learning (opponent sampling)

> 70% random opponent + 30% trained RF opponent; ramp up RF share as agent improves

| Aspect | Evaluation |
|---|---|
| Solves the right problem? | ✓✓ **THIS IS THE KEY FIX** — without it, no reward tweak can make a novice agent beat a strong RF |
| Magnitude | ✓ 70/30 split is sensible |
| Risk | ⚠️ Per-reset switching creates non-stationarity. Recommend: per-**episode** switching (deterministic within an episode) |
| Implementation cost | Low — env already supports `opponent={random, trained}` parameter |

**Verdict: ✓✓ IMPLEMENT IMMEDIATELY — highest expected payoff**

### Strategy 2. Higher ent_coef (0.01 → 0.05–0.08)

> Force exploration of BUY/SELL longer

| Aspect | Evaluation |
|---|---|
| Solves the right problem? | ✓ Yes — discourages premature convergence to HOLD |
| Magnitude | ⚠️ 0.08 is high; might destabilize. Recommend 0.03–0.05 |
| Risk | ⚠️ Higher ent_coef = more random actions = longer convergence |
| Implementation cost | Trivial — CLI flag |

**Verdict: ✓ Implement at 0.04 — modest bump**

---

## 4. Critical things Gemini DIDN'T mention

These are equally important to flag for the team:

### 4.1 MaskablePPO is the actual fix

The cleanest solution to "PPO learns to avoid illegal actions" is **MaskablePPO** (sb3-contrib). It uses `action_masks()` (which we exposed in P1-5!) so the policy can never sample HIRE/SELL/BUY when invalid. This removes the entire `-0.05` penalty that drives the collapse.

> Gemini didn't mention MaskablePPO. We should add it to Phase 2 or 3.

### 4.2 Phase-1 action space is the fundamental constraint

We only have 5 actions, 2 of which are "safe". Even with the best reward shaping, an MLP policy may struggle to learn trade strategies that beat a well-tuned RF. **Long-term**: Phase-2 (8 actions) or Phase-3 (15+ actions) gives the policy more expressive power.

### 4.3 Don't reset P0 fixes

The current reward code (P0-1 reset, P0-2 shared kaggle_env, P0-3 dense /10000, P0-4 terminal only on terminated, P1-5 action_masks) was carefully balanced. If we change reward magnitude, we may need to re-tune other constants. **Don't revert P0-3 (÷10000) back to ÷1000 even if Gemini's plan seems to require it.**

### 4.4 Currently-running training is the first data point

`eval_loop.py` iter_01_20260811_031855 is currently training with P0/P1 fixes in place. If it produces ANY trade actions >0%, that means P0-3 (dense /10000) alone is enough — we may not need Gemini's full plan. **Wait for iter_01 results before changing reward code.**

---

## 5. Proposed phased implementation plan

### Phase 1 — Lightweight changes (do these first)

Risk: low. Expected: agent starts exploring trade actions.

| Change | File | Effort | Expected effect |
|---|---|---|---|
| Curriculum learning (70/30 split) | `src/envs/kagriculture_env.py` | 1h | Agent gets easier wins early, builds confidence |
| `ent_coef` 0.01 → 0.04 | `scripts/train.py` (default) | 5min | More random action sampling early |
| Keep P0/P1 fixes unchanged | — | — | Don't regress |

### Phase 2 — Reward shaping (after Phase 1 results)

Risk: medium. Expected: explicit trade incentive, prevents total collapse.

| Change | File | Effort | Expected effect |
|---|---|---|---|
| Per-step trade bonus (+0.02 for valid HIRE/SELL/BUY) | `_compute_reward` | 1h | Explicit positive signal for trade |
| Relative wealth penalty (α=0.4) | `_compute_reward` | 1h | Opponent growth pressure |
| Inactivity penalty (-0.01 × consecutive_safe, gated) | `_compute_reward` | 2h | Force trade when resources exist |
| Adjust terminal bonus from ±10 to ±8 | `step()` | 5min | Avoid swamping other rewards |

### Phase 3 — MaskablePPO migration (most impactful, highest risk)

Risk: requires `sb3-contrib` and architectural change.

| Change | File | Effort | Expected effect |
|---|---|---|---|
| Switch `from stable_baselines3 import PPO` → `from sb3_contrib import MaskablePPO` | `scripts/train.py` | 4h | Eliminates illegal-action collapse mode entirely |
| Add `--algo {ppo,maskable_ppo}` CLI flag | `scripts/train.py` | 1h | Backward compatible |
| Validate parity (PPO vs MaskablePPO on simple env) | `tests/` | 4h | Confidence in switch

### Phase 4 — VecNormalize + Phase-2 actions (long-term)

Risk: medium-large. Expected: better long-term convergence + more action options.

| Change | File | Effort | Expected effect |
|---|---|---|---|
| Add VecNormalize wrapper (or env-side running σ) | `src/envs/kagriculture_env.py` | 1d | Adaptive reward scaling |
| Expand action space from 5 → 8 (Phase-2 actions: BUY_SEED, SELL_STRAWBERRY, SELL_MILK, BUY_ANIMAL) | `src/envs/kagriculture_env.py`, `docs/03-ACTION-SPACE.md` | 2d | More trading options |

---

## 6. Decision gate: when to advance phases

**Gate 1 (after iter_01_20260811_031855 completes)**:
- If `trade_frac > 5%` → P0 fixes alone are sufficient. Stop at Phase 1 (just add curriculum).
- If `trade_frac = 0%` → P0 fixes insufficient. Proceed to Phase 2.

**Gate 2 (after 2 iters of Phase 2)**:
- If `trade_frac > 20%` AND `win_rate > 30%` → ship Phase 2 model.
- Else → proceed to Phase 3 (MaskablePPO).

**Gate 3 (after Phase 3)**:
- If `win_rate > 50%` vs trained → ship.
- If `trade_frac > 50%` but `win_rate < 50%` → consider Phase 4 (action expansion).

---

## 7. References

- [`logs/2026-08-11-model-eval-analysis.md`](../logs/2026-08-11-model-eval-analysis.md) — model sweep that motivated this
- [`docs/TRAINING_SPEC.md`](../docs/TRAINING_SPEC.md) — current spec
- [`docs/03-ACTION-SPACE.md`](./03-ACTION-SPACE.md) — action space phases
- [`docs/REPLAY_BUG_REPRODUCTION_20260810.md`](./REPLAY_BUG_REPRODUCTION_20260810.md) — why model collapses to PASS
- [`src/envs/kagriculture_env.py`](../src/envs/kagriculture_env.py) — current reward code
- [`scripts/eval_models.py`](../scripts/eval_models.py) — eval script

---

## 9. Quick-start: implement Phase 1 today

If user approves, the fastest path to value:

```bash
# 1. Add opponent sampling to env init
#    (50/50 random/trained, per-episode)
# 2. Set ent_coef=0.04 in scripts/train.py default
# 3. Wait for current iter_01_20260811_031855 to finish (~17 min)
# 4. If trade_frac > 0%, current P0 fixes already work
#    → just rerun the loop with new defaults
# 5. If trade_frac = 0%, proceed to Phase 2 (reward restructuring)
```

Estimated total time to Phase 1 done: 1-2 hours. To Phase 2 done: 3-4 hours. To Phase 3 (MaskablePPO): 1-2 days.