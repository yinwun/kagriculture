# Wool lot timing: availability vs offer (Task 7) — verdict (a), not (b); anti-sign measured

Date: 2026-09-19. Base for every duel: the STACK `data/forward/wool_drain1_outerprem/main.py`
(submitted, ref 56349751). Instrument: `scripts/wool_lot_timing.py` (per-step wool
availability and offers for both seats, with the engine's own `_apply_unit_action` replaying
each step's unit actions on a copy) plus `scripts/ab_duel.py` for the duels.

## 0. Verdict

* **(b) is NOT reachable, and is not what happens.** The sellable pool (shed + hands) is
  **identical** between the two agents early (24.4 vs 24.3, summed per-town means over 11
  towns) and so is the wool standing on the sheep (24.7 vs 24.6). The units are not there
  earlier on their side; they are not `waiting` unsold on ours either.
* The frontier simply **offers far more and sells slightly more**: offered early 1,945 vs
  1,108 (+75%) but executed only +134 (+12/town), and the executed difference is
  concentrated — **0 on 6 of the 11 towns**, +50/+37/+37/+10 on the rest.
* Its wool cash advantage is therefore **(a) production-side (a small herd/turn edge,
  +11 units/town, matching the +27 sheep-days already measured) plus a within-window
  price edge (+$8/unit)**, not a re-sequencing of stock we already hold.
* Our existing forward layer already drains the shed buffer (2.14 → 1.09 units standing at
  seed 9009) and still moves the day-window split by **exactly zero** — explained with
  numbers in §2.
* **Anti-sign probe finished: −15,307, t=−18.35, W/L 0/60** in-sample against the stack.
  The sign our search assumes is now measured, not assumed.

**No new build: the stack remains the best build, and the fraction of the frontier's
+4,407 explained stays ~18% in-sample / ~25% out-of-sample.**

## 1. Availability vs offer (11 towns: 6 in-sample, 5 out-of-sample)

Per-step, per seat: `in_shed` (shed at market time), `in_hands` (farmer + hands),
`on_sheep` (wool standing on that seat's sheep tiles), `offered` (wool units requested),
`executed` (sold, stock-capped, from the replica). Summed over towns, split at day 23/24:

| window | metric | frontier | champion | delta |
|---|---|---|---|---|
| days 0–23 | executed | 1,242 | 1,108 | **+134** |
| | offered | 1,945 | 1,108 | **+837** |
| | pool (shed+hands) mean | 24.4 | 24.3 | **+0.1** |
| | in shed mean | 9.2 | 11.0 | −1.8 |
| | in hands mean | 15.2 | 13.3 | +1.9 |
| | on sheep mean | 24.7 | 24.6 | **+0.1** |
| days 24–29 | executed | 530 | 509 | +21 |
| | pool mean | 47.6 | 44.7 | +3.0 |
| | on sheep mean | 36.9 | 37.0 | −0.1 |

So the *availability* profile is the same; the frontier holds its (identical) stock in
hands rather than in the shed, and calls for ~75% more units than exist. Per town the
early executed delta is 0, 50, 10, 0, 37, 0, 0, 37, 0, 0, 0 — a few-town effect, which is
why the seed-9009 case (172 vs 162) looked like a systematic window shift and is not.

Cross-check on the two original seeds in depth (seed 9009): early executed 172 vs 162,
early offered 229 vs 162, early pool mean 2.60 vs 4.29 (the frontier's pool is *smaller*),
early on-sheep 3.68 vs 5.07. The frontier sells more early with a *smaller* standing pool
because it turns its stock over faster, not because it has more stock.

## 2. Why `wool_drain1` moves the day-window split by exactly zero (with evidence)

Measured directly, stack (`wool_drain1_outerprem`) vs champion, seed 9009:

| window | metric | stack | champion | delta |
|---|---|---|---|---|
| days 0–23 | executed | 163 | 163 | **0** |
| | offered | 163 | 163 | **0** |
| | pool mean | 3.24 | 4.29 | −1.05 |
| | in shed mean | 1.09 | 2.14 | **−1.05** |
| | on sheep mean | 5.03 | 5.03 | 0 |
| days 24–29 | executed | 65 | 65 | 0 |
| | pool mean | 5.15 | 5.97 | −0.82 |

So the layer **does** its job on the buffer — it cuts our standing shed stock of wool by
about half — but the *offered total per window is unchanged*, and therefore so is the
executed total. The three candidate explanations from the brief resolve as follows:

1. **not "the gate is too strict"**: the layer fires (it removed a mean of ~1 unit of
   standing stock) — the stock it releases is real;
2. **not "it only re-slots within a turn"** — it does work across turns within the window
   (the buffer is lower at every step), but
3. **it is the stock/pinning answer**: our standing buffer is only ~2 units, and the
   window totals are pinned by production and collection, which are *identical* (on-sheep
   wool and the pool match to 0.1 units). Every unit the layer releases early is displaced
   1:1 by a tape sell of the same item inside the same window, so the window totals cannot
   move; the whole measured gain of the layer (+2,537 at seed 9009, +790/town aggregate on
   the IS panel) is **within-window re-timing**, not cross-window movement.

Consequence: **(b) is unreachable** — there is no hidden cross-window stock to re-offer;
the days-0–23/24–29 split of our own tape is a production-and-collection consequence.

## 3. Where the wool channel actually is, and its ceiling

* units: the frontier sells **+675 wool units over the 60 duel towns (+11/town)**, which
  matches the **+27 sheep-days/town (+8%)** measured earlier at ~0.5 wool per sheep-day;
  the residual wool gap is production-side (category (a)).
* price: **+$8/unit** within the same windows (Task 5), i.e. ~+1,400/town of cash — this is
  the part our stack attacks, and the part with the measured +790/town capture.
* leftovers are not the source: at the last step the frontier leaves 19 wool units
  (shed+hands+on-sheep) over 6 towns versus our 34 — we leave ~2.5 units/town more, worth
  only ~$150/town.
* ceiling of the reachable part: a herd/turn edit worth ~+8% of wool output is a
  production edit; per the RNG finding (the day-6 shop draw shares the weed-spawn RNG
  stream, so the tape can change) it needs one full paired duel per candidate, no screens.

## 4. Anti-sign probe (finished)

The earlier `anti` variant never acted because the layer's final selection re-scores every
candidate with the true margin and rejected the deliberately-bad layout. Added
`race_force_anti` (hypothesis-gated on `race_hyp == "anti"`, so no other variant can reach
the branch) which accepts the anti-chosen layout outright. Verified: `race_forced_anti`
= 116 layouts accepted in one game, and the control (`fwd_control`, byte-identical to the
stack) still produces a market stream identical to the stack's (0 differing steps), so the
new branch does not touch it.

Result, in-sample, 60 games, forced anti vs the stack:

| candidate | delta | t | W/L | wallet |
|---|---|---|---|---|
| `rl_antiF_stack` (deliberately punished layout) | **−15,307** | **−18.35** | **0/60** | 97,436 vs 112,742 |

**The sign the search assumes is confirmed**: choosing the layout the interleaving punishes
loses ~15.3k per town, with zero wins in 60 games. The lever's dynamic range is therefore
of the order of ±15k, while our search extracts +0.79k — it captures ~5% of the range. That
is the most precise statement of the residual available: the constraint is not the sign and
not the data (Task 6: the observable channel gives quantities, never slots), it is the
search's inability to identify the layout the rival will actually play.

## 5. Updated accounting and recommendation

* Fraction of the frontier's +4,407 explained: **~18% IS / ~25% OOS** (the stack), unchanged.
* The residual is now: (i) production-side herd/turn (+8% wool output, plan edit, duels
  only) ≈ +1,400/town; (ii) within-window price (+$8/unit, ≈ +1,400/town), attacked by our
  market layers and captured at +790/town; (iii) a wide unexploited layout range (±15k
  swing, we take 0.79k) whose binding limit is rival-layout uncertainty.
* Recommended next step: **robust layout optimisation under rival-layout uncertainty** —
  optimise against a set of plausible rival layouts (clone, implied-quantities, empty, and
  adversarial placements) rather than one point prediction, since the probe shows the
  objective is steep but the prediction is weak. That is still market-layer-only work (no
  RNG exposure, fast iteration) and it attacks the largest measured inefficiency we have.
* Do not spend more on: cross-day offer layers (unreachable, §2), the observable rival
  channel (Task 6 negative), forward item sets beyond wool (Task 6 negative), the plan side
  of wheat/herd (Tasks 2 and 5 negative).

## 6. Artifacts and rebuild

```bash
.venv/bin/python scripts/wool_lot_timing.py --seeds 9009 --daily           # in depth
.venv/bin/python scripts/wool_lot_timing.py --cand data/forward/wool_drain1_outerprem/main.py \
    --base data/tapeopt/rgcs/main.py --seeds 9009                          # layer's effect on the pool
.venv/bin/python scripts/wool_lot_timing.py --seeds 9000,9005,9009,9015,9027,9101,9104,9109,9120,9124,9129 \
    --procs 8 --out data/wool-lot-timing.json                              # aggregate
python - <<'PY'
import sys; sys.path.insert(0, "scripts")
import build_race, build_forward
build_race.build({"race_layout":1,"race_hyp":"anti","race_hook":"outer","race_force_anti":1},
                 "rl_antiF_race", "data/rival")
build_forward.build({"forward_items":["WOOL"],"forward_drain":True}, "rl_antiF_stack", "data/rival",
                    base_path="data/rival/rl_antiF_race/main.py")
PY
.venv/bin/python scripts/ab_duel.py --cand data/rival/rl_antiF_stack/main.py \
    --base data/forward/wool_drain1_outerprem/main.py --seeds 9000-9029 --procs 10 \
    --label anti-forced-IS --out data/rival/duel-antiforced-IS.json
```

Artifacts: `scripts/wool_lot_timing.py`, `data/wool-lot-timing.json`,
`data/rival/rl_antiF_{race,stack}/main.py`, `data/rival/sweep-anti.txt`,
`data/rival/duel-antiforced-IS.json`. All error counters 0 (`layer_fallbacks`,
`entry_fallbacks`, `race_errors`) on every variant measured in this round; the control is
byte-identical to the stack and reproduces it exactly.
