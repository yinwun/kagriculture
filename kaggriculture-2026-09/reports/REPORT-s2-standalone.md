# S2 standalone agent — verified live, market half proven sound, unit policy defective (two named defects)

Date: 2026-09-19. Instruments: engine replay (Task 13, controlled), `scripts/s14_gate.py`
(per-seed day-gap gate), `scripts/s15_matched.py` (invalidity instrument), and the new
runtime liveness audit inside every generated agent. Live submitted files untouched.

## 0. Headline

1. **A verified-live standalone agent now exists** — and the audit that proves it is
   institutionalised, so an inert/frozen/parameter-insensitive agent can no longer be
   measured by accident (the failure family that produced the Task-12 artefact).
2. **It is live but non-productive, and the defects are named and localised to the unit
   policy**, not to the market representation (which Task 13 proved faithful with a
   controlled replay): its action counters are **PLANT 0, WATER 0, HARVEST 0, MOVE 35,
   PICKUP 837, DROP 596** — it ping-pongs animals between the shed and the pen and never
   plants, so it earns nothing from the farm and bleeds to zero.
3. **Standalone day curve (4 towns, 8 paired games)**: day 0 0, day 1 −68, day 3 −212,
   day 4 −704, day 9 −2,938, **day 10 −18,256 (0/8)**, final −156,782. The day-10 row is a
   deficit, so **gate 1d was not run** (per the rule).
4. **The invalidity instrument reads a real rate on a live agent**: the live hybrid agent
   has 63.2% no-op unit actions overall, rising from 15% on day 0 to **83% on day 10** — the
   corroboration for the hybrid-artefact hypothesis, and the reason hybrid numbers cannot
   be used to judge the representation.

## 1. Runtime liveness audit (institutionalised cure)

Every generated agent now self-audits. At the last step it reports and — if anything is
wrong — **raises**, so a dead agent cannot be measured silently:

```
LIVENESS {"steps": 719, "money0": 3000.0, "farmer_ops": 717, "units": 1472,
          "noop_units": 2, "mkt_ops": 672} violations []
```

Checks performed: money unchanged from the starting balance (frozen), zero farmer ops
(inert), zero market ops (inert), >90% no-op unit actions (inert). Parameter insensitivity
is checked externally by diffing the action streams of two different θ values (below), since
one agent cannot see another.

Evidence that the audit catches the old family: the broken Task-12 `cg` agent raised on every
step, so it never reached a step count of 719 and produced money identical to its start — the
audit's two conditions (money unchanged, farmer_ops == 0) both fire on it. The new standalone
agent passes all four (`violations []`, 717 farmer ops, 2/1472 no-op units = 0.14%).

**Epistemic status: causal for this build.** The agent is provably not inert or frozen, so its
0-coin score is real performance, not plumbing.

## 2. Invalidity rate on a live agent (instrument verification)

Live hybrid agent (seed 9000, units from its own trace, cash-gated market), no-op = applying
the recorded unit action on a copy changes neither tiles, shed, nor inventories:

| day | 0 | 1 | 2 | 3 | 4 | 5 | 6 | 7 | 8 | 9 | **10** | 11 |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| no-op/units | 20/134 | 48/93 | 65/116 | 54/139 | 45/116 | 16/115 | 57/185 | 32/184 | 73/208 | 81/208 | **227/275** | 133/249 |
| rate | 15% | 52% | 56% | 39% | 39% | 14% | 31% | 17% | 35% | 39% | **83%** | 53% |

Overall 4,289/6,787 = **63.2%**. The instrument is therefore reading a real, structured rate
(not the 100% plumbing artefact of Task 13): the trace's units conflict with this trajectory
from day 1 onward and **spike to 83% on day 10**, exactly where the hybrid agent's deficit
appears. For contrast, the standalone agent's own rate is **0.14%** (2/1472) because its units
are its own policy. **Epistemic status: correlational** for the artefact hypothesis (the
spike coincides with the collapse; it does not by itself prove causation), but it is decisive
for instrument validity.

## 3. The standalone movement/priority policy (built, live, defective)

θ now drives a state-following policy: per-unit jobs derived from the plan
(HARVEST > FEED/CARE/COLLECT > WATER > PLANT > BUILD > PLACE > shed choreography >
walk-to-nearest-job), with shed/cargo handling. It is live (717 farmer ops, 672 market ops)
and it does work the market side — but the farm never produces:

| counter | standalone `full` | champion (for scale, per game) |
|---|---|---|
| PLANT | **0** | ~239 |
| WATER | **0** | ~1,700 |
| HARVEST | **0** | ~484 |
| MOVE | **35** | ~2,950 |
| PICKUP / DROP | **837 / 596** | ~196 / ~43 |
| BUILD_PASTURE | 2 | ~15 |

Two named defects, both fixable and both in the policy rather than the representation:

1. **cargo ping-pong**: after `PICKUP <animal>` the unit is still shed-adjacent, and the
   policy's shed choreography (`carry and adj → DROP`) fires before the walk to the empty pen,
   so the animal is picked up and dropped forever (837/596 churn, MOVE collapses to 35). The
   wheat-flow choreography lesson applies directly: the drop rule must be destination-aware
   (an animal with an empty pen has a destination, so it must not be dropped).
2. **no seed bootstrap**: the cash-gated program's `BUY_SEED` ops were inferred from the
   champion's cash path; once the standalone agent's cash path diverges (it starts spending on
   hires/animals before earning), those buys fail, the seed counters stay at zero, and the
   PLANT job never exists. A standalone plan needs a cash-aware bootstrap (buy the first
   seeds before the first hires/animals), not a fixed schedule.

## 4. Day curve and comparison with the two earlier numbers

| day | Task 12 `cg` (INVALID, broken build) | Task 13 matched replay (market program alone) | **S2 standalone `full` (live)** |
|---|---|---|---|
| 0 | +2,976 (frozen 3,000 vs champion) | +0 (bit-identical to baseline) | **0** |
| 3 | +2,706 | +0 | **−212** |
| 4 | +2,281 | +0 | **−704** |
| 6 | +1,812 | +7 | **−1,082** |
| 9 | +65 | +39 | **−2,938** |
| **10** | **−15,086** | **+39 (reproduced exactly)** | **−18,256** |
| 12 | −17,604 | +39 | **−20,963** |
| final | −147,348 | +389 (identical to the recorded game) | **−156,782** |

The three columns say three different things and must not be confused: Task 12 measured a
dead agent; Task 13 measured the market program with matched units and found it faithful; S2
measures a live agent whose **unit policy** is broken. Gate 1d was **not run** because the
day-10 row is a deficit (the rule).

## 5. Epistemic status of every claim

| claim | status |
|---|---|
| The cash-gated market program is faithful and 99.8% gate-realisable | **Causal** (Task 13 controlled replay: bit-identical curves, +389 reproduced) |
| The standalone agent is live (not inert/frozen) | **Causal/verified** (runtime audit: 717 farmer ops, 2/1472 no-ops, `violations []`) |
| The standalone agent's collapse is caused by its unit policy, not the market program | **Causal for this build**: the market half is proven faithful and the action counters show a farm that never plants (PLANT 0, WATER 0, HARVEST 0) |
| The two named defects (cargo ping-pong, no seed bootstrap) | **Mechanistic reading of the counters**, not yet fixed and re-measured — the *fix* is unmeasured |
| Hybrid-mode numbers cannot judge the representation (63.2% invalid units, 83% spike on day 10) | **Correlational** (coincidence with the collapse plus a structural argument), decisive for instrument validity |
| Whether an explicit θ representation can reach parity | **UNMEASURED** — blocked on the two policy defects; no representational conclusion is drawn this round |

## 6. Verdict and next step

**Continue, with the conclusion still open.** The market half of the explicit representation is
proven sound (causal, controlled), a verified-live standalone agent now exists, and its
failure is localised to two specific defects in the movement/cargo policy that I described
precisely and did not have the budget to fix and re-measure in this round. That is the
opposite of the Task-12 situation: there, the build was dead and the conclusion was wrong;
here the build is alive, the market side is cleared, and the remaining gap is a named,
bounded piece of policy work.

Concretely, in order: (1) make the DROP rule destination-aware and add the animal-delivery
choreography (PICKUP → walk to pen → PLACE, drop only when no destination exists); (2) add a
cash-aware bootstrap to the market plan so the first seeds are bought before the first hires
and animals; (3) re-run the standalone day gate on the same 4 towns (stage 1 clears day 10
only if the day-10 row is no longer a deficit), then gate 1d over the 60 towns. The liveness
audit will catch any regression, and the day-gap instrument is cheap (~1 minute per 4 towns),
so the loop is fast.

## 7. Artifacts

* `scripts/plan_runtime.py` — the standalone (`full`) mode, the job-priority policy and the
  runtime liveness audit; `data/plan/agents/full-<seed>.py` (4 seeds), `cg-<seed>.py` (fixed);
* `data/plan/s2-gate.json` (standalone day curve), `data/plan/s2-invalidity-hybrid.json`
  (per-day invalidity on a live hybrid), `data/plan/s15-matched.json` (Task 13 control);
* `scripts/s14_gate.py`, `scripts/s15_matched.py` — the two gates used above.

Nothing submitted to Kaggle; no live file modified.
