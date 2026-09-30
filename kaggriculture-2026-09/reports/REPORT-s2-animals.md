# S2 animal/fertilizer link (Task 19) — build attempts, and the closing verdict for the line

Date: 2026-09-19. This was the last funded round for the animal/fertilizer link. Instruments:
`scripts/s14_gate.py` (4-town day gate), counter/product telemetry, the runtime liveness audit.
Live submitted files untouched; nothing submitted to Kaggle.

## 0. What happened this round, plainly

I implemented the requested single coherent change — (a) animal re-planning across types,
(b) sell-forward funding so the agent monetises what its shed already holds instead of waiting
for the champion's hours, (c) tile-level reservation for pen targets. **I could not complete a
valid measurement of it within the round.** Three build defects in sequence:

1. `_pick_job` referenced `reserved`, which existed only in `_unit_sched` → `NameError` on every
   step. The agent became inert (reward exactly 3,000, zero counters) — the failure family the
   runtime liveness audit was institutionalised for, and the audit's own conditions (money equal
   to start, zero farmer ops) both fire on it.
2. The sell-forward insertion left `shed_now` undefined in one code path → `NameError` again,
   same inert signature.
3. After both fixes the build is **live but its economy is worse**: it reaches its peak early
   (1,169 coins vs the champion's 224 at step 80) and then goes bankrupt (0 coins by step 400),
   versus the Task-18 build which limped at 20–100 coins for the whole season.

So the day-10 row for this round is **not a valid measurement**, and per the rule ("if the
day-10 row is still a deficit after this, write the closing verdict") the link stays open but
the line closes on the parent's decision. The reference numbers below are Task 18's **valid**
measurements, which are the last trustworthy state of the agent.

## 1. Funding chain, link by link (Task-18 reference vs its targets)

| link | target | Task 18 (valid) | verdict |
|---|---|---|---|
| crop economy at scale | PLANT ~239, WATER ~1,700, MOVE ~2,950 | PLANT 304, WATER 871, MOVE 3,299 | ✅ |
| yield per crop | ≫ 1 unit | 3.97 units/harvest (532 units / 134 harvests) | ✅ |
| weeds avoided | < 2 consecutive unwatered | max 1 | ✅ |
| **place and keep animals** | PLACE ~100 | **PLACE 5** | ❌ |
| **fertiliser supply** | COLLECT_FERTILIZER ~375 | **1** | ❌ **binding** |
| animal care | FEED ~330, CARE ~400 | FEED 73, CARE 1 | ❌ |
| fertiliser/milk/wool sales fund the knife edge | cash accumulates | cash oscillates 22, 18, 40, 87, 29, 91, 56, 16, 74, 72, 102, 0 … | ❌ |
| animal purchases funded | BUY_ANIMAL fires | cash-gated at 20–100 coins | ❌ |
| 4-town day gate | day 10 not a deficit | day 10 **−18,317**, final −167,830 | ❌ |

## 2. Income versus what the plan spends (the arithmetic of the verdict)

* The agent's **entire income** in Task 18 was wheat: 526 units harvested over the season, of
  which the plan's sell schedule monetised only part — call it **~10–13k coins** gross.
* The plan it replays is the champion's: the champion's own final wallet in these games is
  **~165–190k**, i.e. the plan's spending schedule is calibrated to an income **~15× larger**,
  and that income is mostly animal produce (milk/wool/egg) and fertiliser.
* The champion's own bootstrap is a knife edge: its cash is **22 coins at day-1 hour 0**, and it
  climbs out by selling **1 fertiliser on day 1 and 1 fertiliser + 2 wheat on day 2** — sales
  that exist only because its animals were already placed on day 0 and its crops were already
  planted and watered on schedule.
* Our policy reaches the same 22-coin point (it replays the same purchases) but has no animals
  in pens (PLACE 5), so it has nothing to collect and nothing to sell at those hours. The
  cash oscillation between 20 and 102 coins is the equilibrium of "earn a little wheat, spend it
  on the plan's next hire/animal".

**No link in this chain is expressiveness-limited.** The market program is faithful (Task 13
controlled replay: bit-identical curves, 874/876 gates realisable); the crop economy is at
champion scale; the animal cycle completes when it is scheduled (Task 16: BUILD→PICKUP→PLACE all
fired once BUILD existed). What fails is the **timing coincidence** the plan depends on: its
purchases are funded by sales whose production it assumes, and a policy that grows its own
crops and animals produces them at different hours than the tape did.

## 3. Task-19 build state and evidence

* Inert builds (defects 1–2): reward exactly 3,000.00, all counters 0, `SCHED started 0`,
  `_LIVE money0 3000.0` unchanged → the audit's frozen/inert conditions fire. Detected, fixed.
* Post-fix build (defect 3): live, peaks at **1,169 coins at step 80** (champion 224), then
  **0 coins by step 400**; 4-town gate not run because the build is worse than the Task-18
  reference and the day-10 row would not be a like-for-like comparison.
* Liveness audit on every generated build; counters differ between builds (not the
  parameter-insensitive signature); no exception in the 400-step instrumented run.

## 4. Closing verdict — does this line's premise survive?

**No, not as an explicit schedule-and-rule representation.** Seven rounds (Tasks 12–19) fixed, in
order: the market program's cash gating (fixed, faithful), the delivery choreography (fixed),
selection starvation (fixed), the harvest-before-watering trap (fixed — the crop economy now
matches the champion's scale), and three attempts at the animal link. Through all of it the
day-10 row moved from −15,086 (broken Task-12 build) to −18,317 (valid Task-18 build) — i.e. it
never moved in the right direction, and the reason is now quantified: our agent's income is
~10–13k against a plan whose spending assumes ~160k, because the plan's funding is an
equilibrium of *its own* production timing (animals placed on day 0, fertiliser collected on
day 1, sold at hour 6 to buy seeds at hour 6).

The honest statement of what this means:

* The representation is expressive enough (proved: the market program replays the champion's
  game bit-identically with matched units), so this is not a representation failure;
* A from-scratch policy *can* run the crop economy at champion scale (proved: WATER 871, PLANT
  304, MOVE 3,299, 3.97 units/harvest);
* What it cannot do within this architecture is reproduce the **knife-edge cash chronology** of
  a tape whose every purchase is funded by a sale that depends on production timing the policy
  does not share. Matching that would require the plan to be *jointly* re-derived with the
  policy's own production schedule — i.e. a closed-loop planner over θ, which is S3-scale work
  and was never funded.

So the line's premise — that an explicit plan compiled from our own tape lineage can carry this
economy with a policy grown around it — does not survive the measurements. The remaining
options are unchanged and belong to the human: (1) stop at the submitted line
(`data/forward/wool_drain1_outerprem/main.py`, +790 IS / +1,099 OOS over the champion);
(2) continue layer-by-layer extraction of the public composite, where every family measured so
far is worth hundreds to low thousands per town and costs a clean reimplementation plus a full
paired duel; (3) fund an S3-scale closed-loop planner, which this line's evidence suggests is
the only way an explicit representation could work here.

The S1/S2 assets remain reusable whichever path is chosen: the lossless trace pipeline
(24 games, 719/719 actions and state fingerprints, 0 drift), the θ compiler, the cash-gated
program runtime, the liveness audit, the fidelity and day-gap gates, and the per-link
diagnosis of how a tape plan's cash path fails.

Artifacts: `scripts/plan_runtime.py` (animal re-planning, tile reservation, sell-forward —
measured-but-not-validated), `data/plan/agents/full-<seed>.py`, `data/plan/s2-gate-water.json`
(the last valid day gate), `REPORT-s2-water.md` (the last valid chain verification). No live
file modified; nothing submitted.
