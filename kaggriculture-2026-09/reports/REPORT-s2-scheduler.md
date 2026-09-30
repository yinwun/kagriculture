# S2 sequenced scheduler — the animal cycle now completes; the failing link is job-selection starvation (WATER / COLLECT_FERTILIZER)

Date: 2026-09-19. Instrument: `scripts/s14_gate.py` (per-seed 4-town day gate), the runtime
liveness audit, and the scheduler's own statistics. Live submitted files untouched.

## 0. Headline

The sequenced scheduler is implemented and it **breaks the delivery deadlock**: PLACE went
0 → 6, BUILD_PASTURE 0 → 4, PICKUP churn 324 → 14, PLANT 0 → 225 (champion scale ~239). But
the plan's cash path is **still not realisable**, and the failing link is now precise:

> **COLLECT_FERTILIZER = 0 and WATER = 0, because the job-selection order starves them**
> (PLANT is chosen before any work scan, and FEED/CARE outrank COLLECT). No fertilizer is
> collected, so the plan's day-1/2 `SELL FERTILIZER 1` ops have nothing behind them; the
> agent therefore stays on the champion's own knife edge (cash 22 at day-1 hour 0) and never
> funds the seed buys that would let the farm grow. Day 10 is still a deficit (−18,477), so
> **gate 1d was not run**.

The scheduler needed aging in *assignment* handling (implemented) but also in **job
selection**, which it does not have — this is the same starvation failure mode the brief
warned about, one level up from where I first applied the fix.

## 1. Chain verification, link by link (seed 9000, days 0–2 counters)

| link | target | measured | verdict |
|---|---|---|---|
| BUILD a pen | > 0 | **BUILD_PASTURE 4** | ✅ |
| PICKUP an animal at the shed | — | PICKUP 14 (churn was 324) | ✅ churn fixed |
| PLACE it in the pen | > 0 | **PLACE 6** | ✅ (was 0) |
| FEED / CARE | > 0 | FEED 3, CARE 0 | ⚠️ partial |
| **COLLECT_FERTILIZER** | > 0 | **0** | ❌ **starved by FEED/CARE (priority 1 vs 3)** |
| **day-1/2 `SELL FERTILIZER`** | funds the knife edge | nothing to sell | ❌ follows from the above |
| seed buy | land the melon seeds (160 coins) | partially: PLANT 225 over the game from cheap wheat seeds at 1–90 coins | ⚠️ limps, never funded properly |
| **WATER** | ~1,700/game | **0** | ❌ **starved: PLANT (seed branch) is chosen before the work scan, and WATER ranks below FEED/CARE** |
| HARVEST | ~484 | 14 | ❌ consequence of no watering (plants die unwatered / yield 1) |

Money by day: **22, 18, 40, 87, 21, 51, 1, 1, 1, 0, 0, 0 …** — the same knife edge the
champion sits on (22 coins at day-1 hour 0), but the champion climbs out (fertilizer/wheat
sales) and the agent does not.

## 2. Counters before/after vs the champion scale (per game)

| counter | Task 15 (reactive) | **Task 16 (scheduled + BUILD)** | champion (~) |
|---|---|---|---|
| PLANT | 0 | **225** | 239 |
| WATER | 0 | **0** | 1,700 |
| HARVEST | 0 | **14** | 484 |
| MOVE | 249 | **237** | 2,950 |
| PICKUP | 442 | **14** | 196 |
| DROP | 372 | 0 (carried animals are delivered, not dropped) | 43 |
| PLACE | 0 | **6** | ~100 |
| COLLECT_FERTILIZER | 0 | **0** | ~375 |
| BUILD_PASTURE | 2 | **4** | ~15 |
| FEED / CARE | 0 / 0 | 3 / 0 | ~330 / ~400 |
| PASS | 40 | 602 | ~480 |

## 3. Scheduler statistics (evidence the scheduler runs, not just counters)

```
SCHED {"started": 102, "completed": 23, "abandoned": 76, "steps": 376, "aged": 0}
mean steps per assignment: 3.7
```

102 assignments started, 23 completed, 76 abandoned, 0 aged out, 3.7 steps per assignment.
The high abandonment rate (75%) is itself diagnostic: most assignments are dropped because
their target became invalid within a few steps — the signature of units competing for the same
tiles while the job-selection order keeps re-issuing PLANT (the seed branch) and FEED/CARE.
`aged = 0` confirms the age limit never fired, i.e. assignments die from invalidation, not
starvation — consistent with §1's diagnosis.

## 4. 4-town day gate (same instrument and rows as before)

| day | Task 15 (reactive) | **Task 16 (scheduler)** | champion-scale reference |
|---|---|---|---|
| 1 | −68 | **−68** | — |
| 3 | −200 | **−200** | +0 |
| 4 | −692 | **−692** | +0 |
| 6 | −1,082 | **−1,336** | +7 |
| 8 | −1,599 | **−1,872** | +7 |
| 9 | −2,938 | **−3,106** | +39 |
| **10** | −18,256 | **−18,477** | +39 |
| 12 | −20,963 | **−23,726** | +39 |
| final | −156,782 | −158,371 | +389 |

Day 10 is still a deficit → **1d not run; 20 towns not reached** (the current gate order is
(i) counters → (ii) 4 towns → (iii) 20 towns → (iv) 1d, and (i)/(ii) have not passed).

## 5. Runtime and discipline

4-town gate ≈ 2 minutes; per-step wall clock unchanged (sub-millisecond mean; the worst single
step remains dominated by the base champion's own setup). Liveness audit on every build:
`violations []`, `farmer_ops 142`, `units 1105`, `noop_units 577`, `mkt_ops 612` — live, and
the counters differ from Task 15's build, so not the inert/parameter-insensitive signature.

## 6. Epistemic status

| claim | status |
|---|---|
| The sequenced scheduler breaks the delivery deadlock (BUILD→PICKUP→PLACE completes) | **Verified** (PLACE 6, BUILD 4, PICKUP churn 324→14, scheduler stats) |
| The market program remains faithful | **Causal** (Task 13 controlled replay, unchanged this round) |
| Job-selection starvation is the binding link (COLLECT_FERTILIZER 0, WATER 0 despite available work) | **Mechanistic reading of counters plus the scheduler statistics** (75% abandonment, aged 0); the *fix* is unmeasured |
| The money curve improvement is nil because the funding link fails | **Verified by the same-coins day curve and the cash trace** (22/18/40/87/21/51/1/0) |
| Whether explicit θ can reach parity | **Unmeasured** — the farm has never been funded |

## 7. Next single target (one change, not bundled)

**Fix job-selection order and add selection-level aging**: (1) never let PLANT outrank
WATER/HARVEST on a farm that already has unwatered plants — the seed branch should yield to
the work scan when a higher-value job exists; (2) demote FEED/CARE below COLLECT_FERTILIZER
once an animal has fertilizer available, or add a per-op cooldown so each op type gets served
at least once per day; (3) re-check that water is applied before the `consecutive_unwatered`
limit turns plants into weeds. Success criterion for the next round is exactly the brief's
link order: **COLLECT_FERTILIZER > 0 and WATER > 0 on days 0–2, then the day-1/2 fertilizer sale
lands, then the seed buys execute, then the 4-town day gate.** If that chain holds and the day
curve still fails, the next link after it is the harvest-to-sale timing, and I will report that
as the single target rather than bundling.

Artifacts: `scripts/plan_runtime.py` (scheduler, BUILD link, statistics), `data/plan/agents/full-<seed>.py`,
`data/plan/s2-gate-sched.json`. Nothing submitted; no live file modified.
