# S2 water/harvest ordering — the crop economy is fixed (4.0 units/crop), the funding link is now the animal count

Date: 2026-09-19. One change only: HARVEST waits for the yield window and WATER tops the
crop priority. Instrument: `scripts/s14_gate.py` (4-town day gate), counter/units telemetry,
scheduler statistics, liveness audit. Live submitted files untouched.

## 0. Headline

The root-cause fix worked exactly as predicted, and it is the first round where the **crop
economy is genuinely working**:

* **WATER 0 → 871** (champion ~1,700), **PLANT 27 → 304** (champion ~239), **MOVE 220 →
  3,299** (champion ~2,950);
* harvested units per crop rose from the **1.0 seedling baseline to ≈4.0** (134 harvest actions
  yielding **532 units**, of which WHEAT 526 and MELON 6) — i.e. the trap the brief identified
  is closed;
* the weed threshold was never reached: `max_unwatered = 1` (the engine weeds a plant at 2
  consecutive unwatered days), with 661 at-risk unit-steps, so watering now happens in time.

But the agent's score is still ~228 vs the champion's ~165,000, and the funding chain fails at
its last link: the plan's cash is consumed as fast as the farm earns it (cash trace 22, 18, 40,
87, 29, 91, 56, 16, 74, 72, 102, 0 …). **The next single link is the animal count / fertilizer
supply**, which the brief predicted: PLACE 5 (champion ~100), FEED 73 (~330), CARE 1 (~400),
COLLECT_FERTILIZER **1** (~375). Day 10 is still a deficit (−18,317) → **gate 1d not run; 20
towns not reached.**

## 1. Funding chain, link by link

| link | target | measured | verdict |
|---|---|---|---|
| WATER on days 0–2 | > 0 | **11 (whole game 871)** | ✅ fixed |
| crops mature | units/crop ≫ 1 | **≈4.0 units/crop (532 units / 134 harvests)** | ✅ fixed |
| weeds avoided | < 2 consecutive unwatered | `max_unwatered = 1`, at-risk steps 661 | ✅ |
| seed buys funded | PLANT ≈ 239 | **304** | ✅ |
| day-1/2 sale funds the knife edge | cash leaves ~22 | cash 22, 18, 40, 87, 29, 91, 56, 16, 74, 72, 102, 0 … | ❌ oscillates, never accumulates |
| animal income (milk/wool/egg/fertiliser) | PLACE ~100, COLLECT ~375 | **PLACE 5, COLLECT_FERTILIZER 1, FEED 73, CARE 1** | ❌ **binding link** |
| 4-town day gate, day 10 not a deficit | — | day 10 **−18,317** | ❌ |

Why the animal link binds: the agent's whole income is wheat (526 units ≈ 13k coins over the
season), while the plan it replays is the champion's — a plan whose spending assumes the
champion's income (~160k, of which animal produce and fertilizer are the majority). The farm's
cash therefore oscillates in the 20–100 band and is consumed immediately; nothing accumulates
to fund the plan's knife edge.

## 2. Counters vs the champion scale (per game)

| counter | Task 17 | **Task 18 (water fix)** | champion (~) |
|---|---|---|---|
| PLANT | 27 | **304** | 239 |
| WATER | 0 | **871** | 1,700 |
| HARVEST | 628 (seedlings) | **134 (≈4 units each)** | 484 |
| MOVE | 220 | **3,299** | 2,950 |
| PICKUP | 11 | 15 | 196 |
| DROP | 1 | 17 | 43 |
| PLACE | 5 | 5 | ~100 |
| COLLECT_FERTILIZER | 2 | **1** | ~375 |
| BUILD_PASTURE | 3 | 3 | ~15 |
| FEED / CARE | 103 / 2 | 73 / 1 | ~330 / ~400 |
| PASS | 195 | 51 | ~480 |

Per-crop harvested units (seed 9000): **WHEAT 526, MELON 6, total 532** over 134 harvest
actions = **3.97 units/harvest**, versus Task 17's 628 harvests at 1.0 unit each (628 units) —
so the same yield now comes from a quarter of the actions, and the *potential* is higher still
because most crops are harvested at the `max_yield_day` bound rather than at `max_yield`.

## 3. Scheduler statistics (churn returned with the new work mix)

| metric | Task 17 | **Task 18** |
|---|---|---|
| started | 788 | **1,835** |
| completed | 740 | **1,085** |
| abandoned | 48 (6%) | **750 (41%)** |
| aged | 0 | 0 |
| mean steps / assignment | 0.25 | **1.5** |

The abandonment rate rose again (41%) because the units now compete for the same *water/harvest*
targets — the scheduler has no tile-level reservation, so several units pick the same tile and
all but one see it invalidated. That is a real inefficiency and a candidate for a later
single change (tile reservation), but it is **not** the binding link for the funding chain
(the farm's yields are already at scale).

## 4. 4-town day gate

| day | Task 17 | **Task 18** | champion reference |
|---|---|---|---|
| 3 | −152 | −152 | +0 |
| 4 | −689 | −688 | +0 |
| 6 | −1,111 | **−1,074** | +7 |
| 8 | −1,734 | **−1,726** | +7 |
| 9 | −2,946 | −2,948 | +39 |
| **10** | −18,482 | **−18,317** | +39 |
| 12 | −22,537 | **−23,396** | +39 |
| final | −159,429 | **−167,830** | +389 |

Day 10 unchanged; the final is slightly worse (the farm now spends more on water/harvest work
without the animal income that funds the plan). **1d not run; 20 towns not reached.**

## 5. Runtime and discipline

4-town gate ≈ 2 minutes; per-step wall clock unchanged in shape (the standalone agent's own
work grew with MOVE 3,299, still far below the base champion's worst step). Liveness audit
clean on every build; counters differ from the previous build, so not the inert signature.

## 6. Epistemic status

| claim | status |
|---|---|
| HARVEST-on-seedlings is fixed and yields ≈4 units/crop | **Verified** (units per harvest 1.0 → 3.97; WATER 871; weed threshold never reached) |
| The crop economy now runs at champion scale (PLANT/WATER/HARVEST/MOVE) | **Verified** by counters (304/871/134@4units/3,299 vs 239/1,700/484/2,950) |
| The binding link is the animal count / fertilizer supply | **Mechanistic reading with counter evidence** (PLACE 5, COLLECT 1, FEED 73 vs ~100/~375/~330; cash oscillating 20–100); the *fix* is unmeasured |
| The market program remains faithful | **Causal** (Task 13 controlled replay, unchanged) |
| Whether explicit θ can reach parity | **Unmeasured** — but now for a specific, non-crop reason: the plan's spending assumes animal income the agent never earns |

## 7. Next single target (stop here)

**Place and keep animals at the champion's scale.** Concretely: the animal cycle currently
runs for only 5 placements because (a) `_pick_job` stops after the first animal type with shed
stock and never re-plans once the pens are full, (b) the plan's `BUY_ANIMAL` ops are the
champion's (cows on day 0, sheep/goats later) and are cash-gated at 20–100 coins, and (c) the
scheduler has no tile reservation, so several units contend for the same pen. The success
criterion in the brief's link order: **PLACE > 0 and COLLECT_FERTILIZER > 0 at champion scale
(≈100 and ≈375), the fertilizer/milk sale lands, cash stops oscillating at 22–100, then the
4-town day gate.** If that still fails the gate, the next link after it is the tile-reservation
inefficiency in the scheduler (41% abandonment), and I will report it as the single target
rather than bundling.

Artifacts: `scripts/plan_runtime.py` (yield-window rule, WATER-first priority, weed-risk
telemetry), `data/plan/agents/full-<seed>.py`, `data/plan/s2-gate-water.json`. Nothing
submitted; no live file modified.
