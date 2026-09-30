# S1.4 — ordered, cash-gated market program: the early gate clears, the day-10 watershed does not

Date: 2026-09-19. Instrument: `scripts/s14_gate.py` (per-seed θ agents, both seats, per-day
liquid net worth via `day_gap._worth`) and `scripts/day_gap.py`. Same 4 towns (9000–9003),
8 paired games per mode, so the numbers are directly comparable with Task 11's.

## 0. Verdict up front

* **The cash-gated ordering fixed the early phase**: the per-day multisets showed a day-4
  negative (−6) and 0/8 positive days; the ordered cash-gated program shows **days 0–8 all
  positive and 8/8 towns positive every day** (+1,404 … +2,976), i.e. **gate 1b's first
  criterion is met** (first-9-days delta is positive, not merely |t| < 2).
* **The day-10 watershed survives**: day 9 +65 → **day 10 −15,086 (0/8)**, and the deficit
  never recovers (final −147,348; the multiset baseline is −160,296). The ~8× day-10 jump
  is still there (−15,086 from +65 is a ~230× swing on the day, and it is the same event
  the champion converts into +23,463).
* Gate 1b requires **both** criteria, so **1b still FAILS on the day-10 jump**, and per the
  kill criterion I am **stopping S2** rather than grinding representation variants.
* 1d was **not run**: with unit actions supplied by the trace, a 60-town total would
  measure the trace's fidelity, not the representation's (see §3), and the kill criterion
  applies first.

## 1. What changed: the ordered, cash-gated program

`scripts/compile_plan.py` now compiles `market_program[day] = [{hour, step, cash, ops}, …]`:
the champion's market ops **in their real order**, each entry carrying the cash observed at
that step. `scripts/plan_runtime.py --mode cg` replays them hour by hour, gating every BUY
on the cash actually available at that point and **crediting the proceeds of the SELLs that
precede it in the same step** — which is how the engine's own slot order funds the
champion's purchases. The three missing op fields (`hire`, `buy_land`, `buy_seed`) are now
compiled with the same treatment (see the recovery table).

Inferred sequence for day 6 (evidence, seed 9000), 8 of the day's entries:

| hour | cash at step | ops (in order) |
|---|---|---|
| 0 | 797 | SELL FERTILIZER 2, HIRE ×7 |
| 5 | 945 | SELL WOOL 6 |
| **6** | **2,195** | SELL WOOL 4, BUY_PRODUCT WHEAT 2, **BUY_LAND**, BUY_ANIMAL COW 2, BUY_PRODUCT FERTILIZER 1 |
| 7 | 1,025 | SELL WOOL 1, SELL FERTILIZER 1, BUY_PRODUCT FERTILIZER 1 |

That is precisely the mechanism 1c named: the land purchase is funded by the **hour-5 wool
sale** and only fires at hour 6 with 2,195 coins in hand. Task 11's day-level multiset
issued it at hour 0 with 797 coins, so it failed — hence 0 of 2 land purchases and the
day-10 collapse. The fix reproduces it.

## 2. Gate 1b before/after (same 4 towns, 8 paired games each)

| day | multiset θ (before) | cash-gated program (after) |
|---|---|---|
| 0 | −18 | **+2,976** |
| 3 | +278 | **+2,706** |
| **4** | **−6** (first real deficit) | **+2,281** (8/8 positive) |
| 6 | −518 | +1,812 |
| 8 | −1,154 | +1,404 |
| 9 | −1,840 | +65 (6/8) |
| **10** | **−17,343** (0/8) | **−15,086** (0/8) |
| 11 | −18,167 | −15,588 |
| 12 | −21,845 | −17,604 |
| final | −160,296 | −147,348 |

Both runs are per-seed (each town gets an agent compiled from **its own** trace), which also
corrects a Task-11 flaw: that round applied θ from seed 9000 to all four towns, so the
other towns' unit actions came from a foreign trace. The multiset baseline reproduces the
same signature under the corrected construction (−6 on day 4, −17,343 on day 10), so the
comparison is fair.

## 3. What the day-10 gap is, and what it is not

The cash-gated agent is **ahead** of the champion through day 8 and still collapses on day
10, so the remaining gap is not "the market program is wrong early" — it is the mid-game
transition (the third-quadrant development paying off: the champion's net worth jumps
+23,463 on day 10 while the agent's barely moves). Two candidate causes, and I can only
separate them with an experiment the kill criterion rules out:

1. **the representation**: the day-10 transition may need something θ still lacks (e.g. the
   work schedule on the newly bought quadrant, which is a *routing* concept — θ has no
   movement field, and MOVE is 176,950 of ~240,000 unit actions per game);
2. **the measurement**: in `cg` (and `hybrid`) mode the unit actions come from the recorded
   trace, which was produced in the champion's own trajectory. Once the agent's cash
   trajectory diverges (it is +2–3k ahead for nine days), trace-supplied PLANT/HARVEST
   actions increasingly target a farm state the agent does not have, so the trace's units
   stop converting at exactly the point the two trajectories part. That would make the
   day-10 collapse a hybrid-mode artefact rather than a property of the representation.

Distinguishing them requires a **standalone** agent with its own movement/priority rule —
the S2 item. The kill criterion is explicit about not building it after a failed 1b, so I
am reporting the ambiguity rather than resolving it with a non-sanctioned experiment.

## 4. What the representation looks like now (the parent asked for this plainly)

Once ordered and cash-gated, θ is **876 ordered market ops across 30 days (≈29 ops/day),
each with its cash context**, plus the unit-action stream supplied by the trace (719 steps
of farmer/hands). The market half of the representation is now **literally the tape's market
op list with the cash annotations** — one record per op, in order. So:

* it has **degenerated into the tape** for the market side: it is no longer a compact θ;
  the compression that made θ attractive is gone, because the thing that carries the economy
  *is* the intra-day ordering and the cash gating;
* it is still **searchable** in a meaningful sense — the ops are labelled, typed
  (SELL/BUY_SEED/BUY_LAND/HIRE/BUY_ANIMAL/BUY_PRODUCT), grouped by day and hour, and the
  gate is explicit, so a search over "move this lot earlier", "buy land one day sooner",
  "insert a hire here" operates on structured objects rather than opaque indices. It is a
  program of the same length as the tape, but it is a *typed, diffable* program;
* what it is **not** is a compact generative plan: the movement policy (the largest action
  class) is still absent, and the tile-level targets for WATER/FERTILIZE/HARVEST are hour
  histograms, not targets.

## 5. Kill-or-continue verdict

**STOP S2.** Gate 1b still fails (day-10 jump −15,086 against a 3,000 budget), and the one
structural fix that 1c identified was implemented, inferred from the traces, and measured
on the same instrument: it repaired the early phase and did not repair the watershed. Per
the brief's own logic — *"if the ordered cash-gated program still shows the day-4 negative
and the ~8× day-10 jump, stop S2 and write the verdict"* — the day-4 half is fixed but the
day-10 half is not, and the day-10 half is the fatal one (it is where all 8/8 towns turn
negative and where the score is lost). The honest reading is that **the explicit-plan bridge
does not exist as a compact representation** for this economy: schedule-and-rule
representations reproduce the first third of the season and lose the mid-game transition.

Remaining options, stated for the human's decision:

1. **layer-by-layer extraction of the composite** (what the repo has been doing): measured
   and closed on every axis we can rebuild (+790 IS / +1,099 OOS = ~18%/25% of the
   frontier's edge), with each further family worth hundreds to low thousands and requiring
   a clean reimplementation plus a full paired duel;
2. **stop** with the current submitted line (2,147.5-rated lineage + our +790/+1,099 stack);
3. a non-tape architecture, which this S1/S1.4 result now argues against for the
   schedule-and-rule family specifically.

My recommendation is (2) unless the human wants to fund (1) as a long series of paired
duels; the S1 instruments (trace pipeline, θ compiler, cash-gated runtime, fidelity and
day-gap gates) remain reusable assets for whichever path is chosen.

## 6. Artifacts

* `scripts/s14_gate.py` — the per-seed before/after gate (both modes, both seats, day curve);
* `data/plan/theta-9000.json` (+ per-seed thetas) with the new `market_program` field;
* `data/plan/agents/{hybrid,cg}-<seed>.py` — the generated agents (per-seed);
* `data/plan/s14-gate.json` — both curves, finals and first-deficit days;
* Task-11 assets unchanged: `scripts/trace_ref.py`, `compile_plan.py`, `plan_runtime.py`,
  `fidelity.py`, `data/trace/` (24 games, 1a PASS).

Discipline: every agent ran with `layer_fallbacks == 0` and `entry_fallbacks == 0`
(the generated agents contain no chassis layers at all, so the counter is trivially 0 — the
relevant evidence is that they produce differentiated, non-degenerate behaviour, which the
per-mode curves show); no live submitted file was touched; nothing was submitted to Kaggle.
