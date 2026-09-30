# S1.5 disambiguation — the Task-12 cash-gated curve was a broken build; the market program itself is faithful

Date: 2026-09-19. Instrument: `scripts/s15_matched.py` — **engine replay** (both seats' recorded
actions replayed verbatim through the engine), not a played duel, so this round is a
controlled A/B rather than a statistical comparison. Live submitted files untouched.

## 0. Three results, in order of importance

1. **RETRACTION: Task 12's cash-gated day curve was produced by a broken build.** The
   generated `cg` agent referenced `farmer`/`hands` before defining them (my template's mode
   dispatch was ordered wrong), so it raised on **every step**; the harness fallback left it
   sitting on its 3,000 starting coins. That is exactly what its curve shows: "days 0–8
   positive, +1,404…+2,976" is an untouched 3,000-coin agent compared against the champion's
   small early worth, and the "day-10 watershed −15,086" is the **champion's own day-10
   expansion** against that frozen agent. The Task-12 conclusion ("cash-gating fixes the
   early phase but not the day-10 transition") is **withdrawn** — both halves of it were
   artefacts of a dead agent. This is the third occurrence of the same failure family the
   brief warns about, in a new guise: a *parameter- and behaviour-independent* curve.
2. **The market program is faithful and realisable when the unit actions are matched** — the
   parent's decisive experiment, and it is clean: replaying a recorded game with the
   **units verbatim for both seats** and seat 0's market replaced by the compiled cash-gated
   program reproduces the recorded game **exactly** (identical per-day liquid net worth,
   identical delta vs the champion, identical final wallet to the coin) and drops only
   **2 of 876** program ops at the cash gate. So the market representation neither causes
   nor hides a collapse: **it is sound.**
3. **The standalone configuration is still not validly measured.** After fixing the template
   bug, the standalone `cg` agent is inert: **100% of its trace-supplied unit actions are
   no-ops from day 0** (24/24 every day) and it is broke by day 7 (money 22 at end of day 0
   → 0 from day 7). That is a second, separate plumbing defect in the unit side of the
   generated agent, not evidence about the representation.

## 1. Experiment 1 — matched-trajectory counterfactual (the decisive test)

Recorded game: the live stack at seat 0, the champion at seat 1, seed 9000/9001. Both seats'
full action streams captured. Then two replays:

* **BASELINE** — both seats return their recorded actions verbatim. It reproduces the
  recorded game exactly (final 111,014 vs 110,625 → delta **+389**, which is the stack's
  known in-sample value at seed 9000 — an independent confirmation that the replay pipeline
  is lossless in a second mode).
* **COUNTERFACTUAL** — seat 0 keeps its recorded **unit** actions but its **market** orders
  come from the compiled cash-gated program; seat 1 verbatim.

| day | baseline cand / base / delta | counterfactual cand / base / delta | gate drops | ops kept/issued |
|---|---|---|---|---|
| 0 | 106 / 106 / +0 | 106 / 106 / +0 | 0 | 25/25 |
| 3 | 702 / 702 / +0 | 702 / 702 / +0 | 0 | 14/14 |
| 4 | 1,271 / 1,271 / +0 | 1,271 / 1,271 / +0 | 0 | 18/18 |
| 5 | 1,475 / 1,475 / +0 | 1,475 / 1,475 / +0 | 0 | 11/12 |
| 6 | 1,629 / 1,622 / +7 | 1,629 / 1,622 / +7 | 0 | 33/33 |
| 8 | 2,789 / 2,782 / +7 | 2,789 / 2,782 / +7 | 0 | 29/29 |
| 9 | 3,974 / 3,935 / +39 | 3,974 / 3,935 / +39 | 0 | 30/30 |
| **10** | **20,465 / 20,426 / +39** | **20,465 / 20,426 / +39** | **2** | 36/38 |
| 12 | 21,443 / 21,404 / +39 | 21,443 / 21,404 / +39 | 0 | 19/19 |
| final | 111,014 / 110,625 / **+389** | 111,014 / 110,625 / **+389** | (2 total) | 36/36 |

Seed 9001 is the same shape (final 109,632 / 108,813, delta +819 in both runs; 2 drops).

**Reading, and its causal status.** This is a *causal* result **within the matched
trajectory**: the only thing that changed between the two runs is the provenance of the
market orders, and the outcome is bit-identical. Note also what the day-10 row means: the
day-10 "jump" in absolute worth (+39 → 20,465 for the candidate, and the champion likewise)
is the *game's own* day-10 expansion — it is reproduced exactly, not turned into a deficit.
There is no market-side collapse to explain.

## 2. Experiment 2 — unit-action invalidity rate (corroboration)

The intent: per day, how often a trace-supplied unit action conflicts with our own live farm
state. Measured on the standalone `cg` agent (seed 9000), no-op = applying the action on a
copy changes neither tiles nor shed nor inventories:

| day | 0 | 1 | 2 | 3 | 4 | 5 | 6 | 7 | 8 | 9 | 10 | 11 | 12 | 18 | 24 |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| no-op/units | 24/24 | 24/24 | 24/24 | 24/24 | 24/24 | 24/24 | 24/24 | 24/24 | 24/24 | 24/24 | 24/24 | 24/24 | 24/24 | 24/24 | 24/24 |
| rate | 100% | 100% | 100% | 100% | 100% | 100% | 100% | 100% | 100% | 100% | 100% | 100% | 100% | 100% | 100% |

**100% from day 0 is not the artefact hypothesis being confirmed — it means the standalone
agent never applies its recorded units at all** (a plumbing defect in the generated agent's
unit path: the units it hands the engine have no effect even at step 0, where the recorded
game's own state and this agent's state are identical by construction). So experiment 2
cannot distinguish the hypotheses yet: it falsifies the *measurement*, not the
representation. The one thing it does establish is the size of the hazard the parent was
worried about — when the trajectory does not match, trace-supplied units can be inert, so
the hybrid scheme is only valid while the trajectories agree.

## 3. Gate realisability

* Matched trajectory: **874 of 876** program ops satisfy their inferred cash gate; the two
  drops are BUY_PRODUCT (feed) orders whose cash was consumed by an earlier op in the same
  step. So the program's gates, inferred from the champion's cash path, are realisable to
  99.8% — the program is not over-fitted to a cash trajectory that cannot occur.
* Standalone agent: the cash path diverges from **day 1** (money 18 vs the champion's 86)
  and reaches 0 by day 7, so the program's gates are unsatisfiable from that point — but
  that is a consequence of the agent being inert, not of the gates being wrong.

## 4. Kill-or-continue verdict

**The kill is LIFTED, and its premise is void.** The criterion was "if the ordered cash-gated
program STILL shows the day-4 negative and the ~8× day-10 jump, stop S2". The decisive
experiment shows there is no day-10 collapse attributable to the market program: with matched
unit actions the program reproduces the champion's game to the coin, including day 10, and
drops 2 of 876 ops. Task 12's evidence for the collapse was a broken build and is withdrawn.

**Causal vs correlational, stated plainly:**

* *Causal (engine replay, controlled):* the cash-gated market program is faithful — with the
  unit actions and the rival held fixed, it reproduces the recorded trajectory exactly. The
  market representation is therefore **not** the blocker.
* *Not established:* whether a **standalone** θ agent (its own units, its own movement) can
  reach parity. The generated agent that would test that is broken on the unit side (100%
  inert), so the standalone gate is **pending**, not failed. My Task-12 and Task-13 numbers
  from generated agents are superseded.
* *Correlational only:* the claim that the divergence hazard grows over the season — the
  matched runs show the trajectory does not diverge at all (0 no-ops attributable to
  divergence in the counterfactual), while the broken agent shows 100% inertness from step 0;
  neither establishes a day-9/10 divergence rate.

## 5. Next step (S2 item, per the parent's rule)

Experiment 1 clears the day-10 gate, so the S2 item is authorised — but the first job is not
the movement policy as such, it is to make the standalone agent *valid* and then measure it:

1. fix the generated agent's unit path (the trace units must actually reach the engine — the
   100%-no-op result is a plumbing bug, and the invalidity-rate instrument should then read
   the intrinsic rate the matched baseline shows, not 100%);
2. implement the movement/priority policy that replaces the trace units (MOVE is 176,950 of
   ~240,000 unit actions per game), i.e. the real S2 item;
3. re-run the day-10 gate on the same 4 towns with a *standalone* θ agent, then gate 1d.

Only after (3) is a statement about the explicit representation's viability defensible. The
Task-12 verdict ("the explicit-plan bridge does not exist") is **not supported**: what failed
was my build, twice, and the one controlled experiment that did run shows the market half of
the representation is sound.

## 6. Artifacts

`scripts/s15_matched.py` (matched replay + invalidity instrument), `data/plan/s15-matched.json`
(both runs, both seeds, per-day curves, drops), `data/plan/s15-exp2.json` (invalidity table),
`data/plan/agents/cg-*.py` (the generated agents, fixed template). Task-11 assets unchanged.
Nothing submitted; no live file modified.
