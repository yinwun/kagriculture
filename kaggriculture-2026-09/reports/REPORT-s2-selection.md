# S2 selection-level aging — starvation fixed, the next single link is harvest-before-watering

Date: 2026-09-19. One change only: selection-level aging (starvation-scored job order).
Instrument: `scripts/s14_gate.py` (4-town day gate), the liveness audit, scheduler statistics.
Live submitted files untouched.

## 0. Headline

Selection-level aging worked as designed — **HARVEST 14 → 628** (champion ~484), FEED 0 → 103,
CARE 0 → 2, **COLLECT_FERTILIZER 0 → 2**, and the scheduler's completion rate went from 23/102
to **740/788** with mean assignment length 0.25 steps. But:

1. **WATER is still 0**, and that is now explained exactly: the engine gives non-ongoing crops
   `yield_units = 1` **at planting** (`_new_plant`), and my `_needs()` treats any
   `yield_units > 0` as HARVEST. So the units harvest each seedling the step after it is
   planted, the plant disappears before it can be watered, and the farm converts each seed
   into **1 unit** instead of up to 6 (wheat) — 628 harvests of one unit each.
2. **The funding chain therefore still fails at the same place**: COLLECT_FERTILIZER fires but
   only twice (few animals are ever placed/kept), so the day-1/2 fertilizer sale cannot fund
   the knife edge; cash still dies (22, 18, 40, 87, 28, 90, 126, 6, 6, 2, 0 …) and PLANT
   limps at 27. Day 10 is still a deficit (−18,482), so **gate 1d was not run and 20 towns
   were not reached**.
3. Per the brief's item 5 I stop here rather than bundling: **the next single link is the
   harvest-before-watering rule** (and, behind it, the animal count that limits fertilizer).

## 1. Funding chain, link by link

| link | target | measured (days 0–2 / whole game) | verdict |
|---|---|---|---|
| BUILD pen | > 0 | 3 / 3 | ✅ |
| PICKUP animal at shed | — | 10 / 11 | ✅ |
| PLACE animal | > 0 | 4 / 5 | ✅ |
| FEED / CARE | > 0 | 96 / 103, 0 / 2 | ✅ (FEED at scale) |
| **COLLECT_FERTILIZER** | > 0 | **0 / 2** | ⚠️ fires but rare (too few animals in pens) |
| day-1/2 fertilizer sale | funds the knife edge | cash 22 → 18 → 40 → 87 → 28 → 90 → 126 → 6 … | ❌ not funded |
| seed buys | land | PLANT 6 / **27** (was 225 when planting dominated) | ❌ limping |
| **WATER** | ~1,700 | **0 / 0** | ❌ **root cause identified below** |
| HARVEST | ~484 | **122 / 628** | ✅ at scale — but of seedlings |

**Root cause of WATER = 0 (measured, mechanistic):** `_needs()` returns `HARVEST` whenever
`yield_units > 0`, and for WHEAT/CARROT/MELON `_new_plant` sets `yield_units = 1` immediately.
The unit therefore harvests the crop the step after planting; the tile becomes empty and there
is never an unwatered plant for the WATER job to exist. The farm's yield per seed is 1 unit
instead of the watered maximum (up to 6 for wheat), which is why HARVEST is at scale yet the
cash never grows: 628 units of mostly-wheat at ~25 coins is ~15k gross over the season, but the
plan spends it on the same knife-edge schedule that the champion funds with *mature* crops and
animal produce.

## 2. Counters before/after vs the champion scale (per game)

| counter | Task 16 (fixed order) | **Task 17 (starvation-scored)** | champion (~) |
|---|---|---|---|
| PLANT | 225 | 27 | 239 |
| WATER | 0 | **0** | 1,700 |
| HARVEST | 14 | **628** | 484 |
| MOVE | 237 | 220 | 2,950 |
| PICKUP | 14 | 11 | 196 |
| DROP | 0 | 1 | 43 |
| PLACE | 6 | 5 | ~100 |
| COLLECT_FERTILIZER | 0 | **2** | ~375 |
| BUILD_PASTURE | 4 | 3 | ~15 |
| FEED / CARE | 3 / 0 | **103 / 2** | ~330 / ~400 |
| PASS | 602 | 195 | ~480 |

## 3. Scheduler statistics (the starvation change is visible here)

| metric | Task 16 | **Task 17** |
|---|---|---|
| started | 102 | **788** |
| completed | 23 | **740** |
| abandoned | 76 (75%) | **48 (6%)** |
| aged | 0 | 0 |
| mean steps / assignment | 3.7 | **0.25** |

The abandonment collapse (75% → 6%) is exactly the signature the brief predicted for selection
starvation: with the fixed priority order, units kept being re-assigned to PLANT and the
targets died under them; with the starvation-scored order, most assignments are immediate jobs
at the unit's own tile (hence the very short mean length) and complete.

## 4. 4-town day gate (same instrument and rows)

| day | Task 16 | **Task 17** | champion reference |
|---|---|---|---|
| 3 | −200 | **−152** | +0 |
| 4 | −692 | **−689** | +0 |
| 6 | −1,336 | **−1,111** | +7 |
| 8 | −1,872 | **−1,734** | +7 |
| 9 | −3,106 | **−2,946** | +39 |
| **10** | −18,477 | **−18,482** | +39 |
| 12 | −23,726 | **−22,537** | +39 |
| final | −158,371 | **−159,429** | +389 |

Marginal early improvement (−200 → −152 on day 3 etc.), day 10 unchanged. **1d not run; 20
towns not reached.**

## 5. Runtime and discipline

4-town gate ≈ 2 minutes; per-step cost unchanged (sub-millisecond mean, worst step still the
base champion's own setup). Liveness audit clean on every build (`violations []`,
`farmer_ops` high, counters differing between builds → not the inert signature).

## 6. Epistemic status

| claim | status |
|---|---|
| Selection-level aging removed the starvation (abandonment 75% → 6%, HARVEST/FEED/COLLECT all now fire) | **Verified** (counters + scheduler statistics) |
| WATER = 0 is caused by HARVEST firing on freshly-planted crops (`yield_units = 1` at planting) | **Mechanistic reading** of the engine's `_new_plant` plus the counter pattern (628 harvests, 0 waters, 27 plants); the fix is **unmeasured** |
| The funding chain still fails at the fertilizer/seed link | **Verified** (cash trace 22/18/40/87/28/90/126/6/6/2/0, PLANT 27) |
| The market program remains faithful | **Causal** (Task 13 controlled replay, unchanged) |
| Whether explicit θ can reach parity | **Unmeasured** (the farm is still not funded) |

## 7. Next single target (stop here, as instructed)

**Make HARVEST wait for the yield window and let WATER run first.** Concretely: a non-ongoing
crop should be harvested only when it can no longer gain (i.e. `day - planted_day >=
max_yield_day`, or `yield_units >= max_yield`), and WATER should be the top-priority job for any
planted crop that is not yet watered, before any harvest consideration. Success criterion, in
the brief's link order: **WATER > 0 on days 0–2** → crops mature → HARVEST yields multiple
units per seed → the day-1/2 sale and the seed buys are funded → the 4-town day gate. If the
gate still fails after that, the next link is the animal count (fertilizer supply: 2 collects
is far below the champion's ~375), which I would report as the single target rather than
bundling it here.

Artifacts: `scripts/plan_runtime.py` (starvation-scored selection, `_LAST_OP`, `_op_score`),
`data/plan/agents/full-<seed>.py`, `data/plan/s2-gate-selection.json`. Nothing submitted; no
live file modified.
