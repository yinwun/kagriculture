# Herd/TURN edits (Task 9) — the binding gate is measured, the channel is closed, and the residual is plan data

Date: 2026-09-19. Base: the STACK `data/forward/wool_drain1_outerprem/main.py` (submitted,
ref 56349751). Instrument: `scripts/ab_duel.py` (paired, seats alternating, 60 games per
panel) plus the gate probe and `scripts/race_timing.py`.

## 0. Headline

1. **What binds is the eligibility gate, not cash or capacity.** The champion's own 6-sheep
   investment (`_V233`, "bounded, financed six-sheep SE discovery") fires on only **2 of 14
   probed towns**. Across all 14 towns the budget and capacity decline counters are **0**, so
   cash and shed space never bind. At seed 9009 every condition passes (WOOL 233 ≥ 220,
   WHEAT 41 ≤ 45, three quadrants, no blocked pen tiles, empty shed, cash 12,056 against a
   ~10,000 requirement) **except** `town.unlocked_shops.count('YARN_STORE') >= 2`, which is
   1. The gate also needs `day == 12` at hour ≤ 1.
2. **Every narrow candidate loses**, including the one that actually fires the mechanism:

| candidate (one edit, applied to the stack) | IS delta | t | W/L | towns changed |
|---|---|---|---|---|
| `yarn1` — yarn threshold 2 → 1 (the measured gate) | **−3,374** | **−2.94** | 7/23 | 12 / 30 |
| `d11` — fire one day earlier (day 12 → 11) | −295 | −1.00 | 5/7 | 1 / 30 |
| `plus1` — buy 7 instead of 6 at the same step | −19 | −1.00 | 5/7 | 1 / 30 |
| `yarn1_d11` — both edits | −295 | −1.00 | 5/7 | 1 / 30 |

   Out-of-sample was not run for these: none won in-sample (and three of the four change at
   most one town per panel), so per protocol nothing advanced. The candidate that matters is
   `yarn1`, and on the 12 towns where it changes anything it loses **−8,434 each**.
3. **Why it loses — the mechanism works but does not pay.** At seed 9009 `yarn1` fires and
   creates exactly the intended thing: commit requests 2, **sheep-days 239 → 341 (+102)**,
   sheep 11 → 17 from day 13, **216 wool units harvested**. Across the 30-town panel it also
   adds FEED +2,592, CARE +2,592, COLLECT_FERTILIZER +2,446, MOVE +2,366, PLACE +1,106 — and
   **takes those turns out of the crops: FERTILIZE −1,078, WATER −440, PLANT −40**. The extra
   wool also depresses its own price. The champion's authors gated this layer at
   `YARN_STORE >= 2` for exactly this reason, and my measurement confirms it is not a slack
   gate.
4. **The runtime claim from the brief is not borne out**: a plan edit that adds 6 animals and
   ~2,600 extra actions per agent changes the per-step wall clock by nothing measurable
   (both 0.5 ms mean, p95 0.7–0.8 ms, worst step 46 ms vs 57 ms in the same run; an earlier
   run under 10-way parallel load showed the same shape at 1.8 vs 2.4 ms). The agent's cost
   is dominated by fixed per-step work, not by the number of animals.

## 1. Which constraint binds (measurement, 14 towns)

`_V233` gate components at step 288/289 (its only firing window is day 12 hour ≤ 1):

| seed | yarn | WOOL | WHEAT | quadrants | blocked tiles | shed sheep | cash | commit |
|---|---|---|---|---|---|---|---|---|
| 9005 | 2 | 241 ✓ | 37 ✓ | NE,NW,SW ✓ | no | 0 ✓ | 14,286 ✓ | **fires** |
| 9009 | **1 ✗** | 233 ✓ | 41 ✓ | NE,NW,SW ✓ | no | 0 ✓ | 12,056 ✓ | blocked |
| 9002 | **0 ✗** | **154 ✗** | 42 ✓ | NE,NW,SW ✓ | no | 0 ✓ | 13,189 ✓ | blocked |
| all 14 towns | ≥2 on 1 town | — | — | — | — | — | — | 2 requests, **0 budget declines, 0 capacity declines** |

So the ordering of constraints is: **eligibility (yarn count, then the WOOL price floor) ≫
nothing else**. Cash is 12k–14k against a ~10k requirement with a 3k reserve; the shed is
empty at that step with a 100-unit cap and 12 incoming; pens and hands are available (the
layer hires two workers itself). That is why the brief's "if cash or capacity binds, stop"
case does not apply — I proceeded, and the candidates still lost on their own merits.

## 2. Per-town evidence that the mechanism is real but unprofitable

`yarn1` (the firing candidate), in-sample:

* sheep-days 239 → 341 at seed 9009 (+102; the frontier's own advantage is +27), sheep
  11 → 17 from day 13, 216 wool units harvested by the layer itself;
* 12 of 30 towns change at all (the gate is town-specific); the other 18 are exact ties;
* **mean delta on the 12 changed towns: −8,434**; the 7 wins are towns where the change is
  tiny; the aggregate −3,374 with t=−2.94 is therefore a coherent loss, not noise;
* the action counters show the crowding-out mechanism directly (FERTILIZE −1,078 in a
  season where fertilising is worth four figures per town, WATER −440, MOVE +2,366).

`d11`, `plus1`, `yarn1_d11`: on the one town where they change anything they lose ~8.8k
(`d11`, `yarn1_d11`) or ~0.6k (`plus1`); everywhere else they are bit-identical ties. The
day shift alone cannot fire where the yarn gate blocks, which is exactly what §1 predicted.

## 3. Runtime (first-class, as requested)

`scripts/race_timing.py`, seed 9000, whole-agent per-step time, same run for both:

| agent | mean | median | p95 | worst step |
|---|---|---|---|---|
| stack | 0.5 ms | 0.2 ms | 0.8 ms | 56.5 ms |
| `yarn1` (6 more animals, +2,600 actions/game) | 0.5 ms | 0.2 ms | 0.7 ms | 45.9 ms |

(An earlier run under 10-way parallel load reported 1.8 ms vs 2.4 ms for the layer variants;
the absolute numbers track machine load, the conclusion does not.) A plan edit of this size
does not move the per-step cost, so runtime is not a constraint on plan work either.

## 4. Assessment: is the remaining ~75% reachable from our lineage?

**No — not by editing our parameters, and I do not believe it is reachable at all without a
newer upstream tape snapshot or a from-scratch re-plan.** The reasoning, from this round and
the five before it:

* Every *parameter* of our plan that we can name has now been tested and closed: the herd
  composition swap (Task 2, −982/−5,087), sheep-day quantity and timing (this round, −3,374
  where it fires), care/feed coverage (measured equal-or-better than the frontier's), the
  wheat flow (Task 5, −2.5% of the gap), the route/tape selection (Task 4, best alternative
  +24 with every other tape 3k–9.8k worse), and the whole market layer on four axes
  (Tasks 1, 3, 6, 8: +790 extracted against a perfect-information oracle of +513/+963 —
  i.e. exhausted).
* What is left is not a parameter but the *plan data*: which turn each lot is offered in,
  which tiles are planted/watered/fertilised when, and the placement choreography. The two
  files' route tables are **disjoint (0 of 41 tapes byte-identical)** while every action
  count differs by only 1–3% — the frontier is a **newer snapshot of the same lineage**, and
  its edge shows up exactly where a newer snapshot would show it: the same units, the same
  day windows, identical pools and identical wool-on-sheep, ~+2.8 per unit of realised price.
* Options, honestly ranked: (a) obtain or reconstruct a newer upstream tape snapshot of this
  lineage and re-run the same measurements (cheap if the data exists, and the whole report
  chain above applies unchanged to it); (b) a from-scratch tape re-plan — a 719-step search
  whose every candidate needs a full 60-game paired duel (≈2–4 minutes) and whose objective
  is non-stationary because a plan edit can flip the shop draw; realistic effort is days to
  weeks with uncertain payoff; (c) change architecture away from tape replay, which
  discards everything measured here.
* The submitted line is therefore at its measured ceiling for this lineage: the stack is
  **+790 IS / +1,099 OOS over the champion**, i.e. ~18%/25% of the frontier's edge, and my
  recommendation is not to spend more on this lineage's parameters.

## 5. Best build, rebuild, artifacts

No new build: the best build remains the submitted stack.

```bash
python scripts/build_race.py --name outer_prem
python - <<'PY'
import sys; sys.path.insert(0, "scripts")
import build_forward
build_forward.build({"forward_items": ["WOOL"], "forward_drain": True},
                    "wool_drain1_outerprem", "data/forward",
                    base_path="data/race/outer_prem/main.py")
PY
# the Task-9 candidates (measured, NOT kept); each is one asserted single-site edit
for v in yarn1 d11 plus1 yarn1_d11; do
  .venv/bin/python scripts/build_herd_turn.py --name "$v"
done
.venv/bin/python scripts/ab_duel.py --cand data/herd/yarn1/main.py \
    --base data/forward/wool_drain1_outerprem/main.py --seeds 9000-9029 --procs 10 \
    --label herd_yarn1-IS --out data/herd/duel-herd_yarn1-IS.json
.venv/bin/python scripts/race_timing.py --cand data/herd/yarn1/main.py
```

Artifacts: `scripts/build_herd_turn.py`, `data/herd/{yarn1,d11,plus1,yarn1_d11}/main.py`,
`data/herd/sweep-t9-IS.txt`, `data/herd/duel-herd_*-IS.json`, and the gate probe output in
this report's §1 (`_V233` counters + gate components over 14 towns). All error counters 0
(`layer_fallbacks`, `entry_fallbacks`, `race_errors`) on every candidate; the protocol's
byte-identical control remains `data/rival/fwd_control` (Task 6: +0, every counter +0 on both
panels). Nothing submitted to Kaggle.
