# CHANGE_SPEC-phase1-random-curriculum — start with random opponent + ent_coef=0.04

> **Date**: 2026-08-11
> **Author**: Phase 1 of Gemini advice implementation
> **Based on**: [`docs/REWARD_AND_TRAINING_REDESIGN_20260811.md`](REWARD_AND_TRAINING_REDESIGN_20260811.md) §5 (Phase 1 plan)
> **Reviewer check**: see [`docs/REVIEW-phase1-random-curriculum-20260811.md`](REVIEW-phase1-random-curriculum-20260811.md)

---

## 1. 问题描述

Gemini's "躺平陷阱" diagnosis: long training against the trained RF collapses the policy to HOLD/PASS-only (confirmed in [`logs/2026-08-11-model-eval-analysis.md`](../logs/2026-08-11-model-eval-analysis.md)).

**Phase 1 goal**: give the agent an **easy opponent (random)** so it can learn basic trade actions (HIRE/SELL/BUY) without being overwhelmed, AND increase exploration entropy so it doesn't collapse to HOLD/PASS even during training.

Two changes:
1. `--opponent` default flips from `trained` → `random` (Phase 1: easy baseline only)
2. `ent_coef` default bumps from 0.01 → 0.04 (more exploration)

No reward function changes (those are Phase 2).

---

## 2. 实验依据

- `logs/2026-08-11-model-eval-analysis.md` — model sweep: all 12 saved models score 0% vs trained RF, vs random some trade 100% (early) and 0% (late). Late training collapses to PASS/HOLD only.
- `docs/REWARD_AND_TRAINING_REDESIGN_20260811.md` §3 — Gemini analysis: "trained RF is too strong; novice agent can't find winning gradient; collapses to minimize penalty = don't act".
- Current iter_01_20260811_031855 (running on GPU 0) is using `--opponent trained` + default `ent_coef=0.01` — likely to repeat the collapse pattern.

---

## 3. 改动范围

| File | Change | Lines |
|---|---|---|
| `scripts/train.py` | `--opponent` default `trained` → `random` (Phase 1 only) | ~1 line |
| `scripts/train.py` | `--ent_coef` default `0.01` → `0.04` (Phase 1+) | ~1 line |
| `scripts/eval_loop.py` | pass through `--ent_coef` to subprocess call | ~1 line |

No env changes. No reward function changes. No spec breaks.

---

## 4. 代码改动

### Before (`scripts/train.py:204,213`)

```python
p.add_argument("--opponent", type=str, default="trained",
               choices=["random", "trained"])
...
p.add_argument("--ent_coef", type=float, default=0.01)
```

### After

```python
p.add_argument("--opponent", type=str, default="random",  # Phase 1: start easy
               choices=["random", "trained"])
...
p.add_argument("--ent_coef", type=float, default=0.04)   # Phase 1: more exploration
```

### Before (`scripts/eval_loop.py:74` — `train_one_iter`)

```python
"--n_steps", "2048",
"--batch_size", "64",
"--eval_freq", "50000",
"--eval_episodes", "5",
```

### After

```python
"--n_steps", "2048",
"--batch_size", "64",
"--eval_freq", "50000",
"--eval_episodes", "5",
"--ent_coef", str(getattr(args, "ent_coef", 0.04)),
```

Plus add `--ent_coef` to `eval_loop` argparse with default `0.04` (matches `scripts/train.py`).

### Out of scope (Phase 2+)

- Reward function: relative wealth, trade bonus, inactivity penalty, terminal scale
- Action masking switch: MaskablePPO migration
- VecNormalize wrapper
- Curriculum switch logic (we'll do that in Phase 2)

---

## 5. 训练计划

| Setting | Value | Rationale |
|---|---|---|
| GPU | **cuda:1** (idle, 0% util) | Don't disrupt GPU 0's running iter |
| Opponent | **random** | Easy baseline, agent should win by trading |
| Steps per iter | 280k | Same as before (~30 min) |
| Iterations | 3-5 | Stop early on success |
| ent_coef | **0.04** | Was 0.01 — 4× more exploration |
| Other hyperparams | unchanged | lr=3e-4, gamma=0.99, etc. |

### Launch

```bash
CUDA_VISIBLE_DEVICES=1 nohup python -u scripts/eval_loop.py \
    --max_iters 5 \
    --steps_per_iter 280000 \
    --device cuda \
    --opponent random \
    --ent_coef 0.04 \
    --num_eval_episodes 3 \
    --trade_threshold 0.10 \
    > log/eval_loop_phase1.log 2>&1 &
```

(using separate log file so we don't clobber the GPU 0 loop's log)

### Stop criteria

- `trade_frac >= 10%` (looser than current 5% to account for random opponent)
- OR `win_rate >= 80%` vs random (the agent should crush random)
- OR 5 iters done

---

## 6. 预期效果

| Metric | Before (vs trained, ent_coef=0.01) | After (vs random, ent_coef=0.04) |
|---|---|---|
| Trade % | 0–6.5% | **>20%** (random is easy enough to learn) |
| Win rate vs random | 100% (random does nothing) | 100% (still easy) |
| Win rate vs trained | 0% | n/a (we don't eval vs trained in Phase 1) |
| Time to first trade action | never | **~50K steps** (iter 1) |

### What "success" looks like for Phase 1

- `trade_frac` climbs from 0% to 10%+ within 1-2 iters
- Action distribution shows HIRE/SELL/BUY pills (color-coded) appearing in `replay.html`
- `win_rate vs random` stays at 100% (it should — random is weak)

---

## 7. 风险

| Risk | Mitigation |
|---|---|
| Ent_coef=0.04 too high → training instability | If `policy_loss` blows up or `entropy_loss` doesn't decay, fall back to 0.02 |
| Random opponent too easy → agent overfits to random and never generalizes | Phase 2 will mix in trained RF once basic trade patterns are established |
| GPU 1 conflict with anything | `nvidia-smi` shows 0% util / 3 MiB; safe to use |
| New defaults silently break someone else's run | Document prominently in `TRAINING_SPEC.md` after merge |

### Rollback

```bash
# Revert defaults:
#   --opponent → "trained"
#   --ent_coef → 0.01
```

Or in code: revert the two defaults in `scripts/train.py`.

---

## 8. Gate 1 verification plan

After iter 1 completes:

```bash
# 1. Did trade_frac improve?
cat eval_reports/iter_*/summary.json | grep trade_frac

# 2. Action distribution
cat eval_reports/iter_*/summary.json | grep action_counts

# 3. Visual check
#   Open eval_reports/iter_NN_<ts>/report.html
#   Open eval_reports/iter_NN_<ts>/replay.html
#   Look for HIRE/SELL/BUY pills (green/orange/red, not blue/purple)
```

**Pass criteria**:
- `trade_frac >= 10%`
- `action_counts` shows non-zero entries for HIRE/SELL/BUY indices
- `replay.html` shows colored trade-action pills

**Fail criteria**:
- `trade_frac < 5%` → opponent random is STILL too easy? Or ent_coef needs further bump?
- `trade_frac > 50%` but `win_rate < 90%` → trading but losing money, reward shaping still off

---

## 9. References

- [`docs/REWARD_AND_TRAINING_REDESIGN_20260811.md`](REWARD_AND_TRAINING_REDESIGN_20260811.md) — Gemini advice analysis
- [`logs/2026-08-11-model-eval-analysis.md`](../logs/2026-08-11-model-eval-analysis.md) — model sweep
- [`docs/TRAINING_SPEC.md`](TRAINING_SPEC.md) — current spec
- [`docs/REPLAY_BUG_REPRODUCTION_20260810.md`](REPLAY_BUG_REPRODUCTION_20260810.md) — PASS-every-step bug