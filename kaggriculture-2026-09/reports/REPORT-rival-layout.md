# Rival-layout + forward item-set round (Task 6) — both hypotheses negative

Date: 2026-09-19. Live line / base for every measurement:
`data/forward/wool_drain1_outerprem/main.py` (the stack, ref 56349751).
Instrument: `scripts/ab_duel.py`, paired, seats alternating, 60 games per panel
(30 towns × 2 seats), in-sample 9000–9029 and fresh out-of-sample 9100–9129.

## 0. Headline

| candidate | in-sample vs the stack | out-of-sample vs the stack |
|---|---|---|
| `fwd_control` (byte-identical copy of the stack) | **+0, t=+0.00, 5/5, identical counters** | **+0, t=+0.00, identical counters** |
| (1) `fwd_milk` (forward layer on MILK) | −290, t=−2.09, 27/33 | −345, t=−2.81, 29/31 |
| (1) `fwd_carrot` (CARROT) | −279, t=−2.12, 19/41 | −469, t=−3.98, 9/51 |
| (1) `fwd_milkcarrot` | −291, t=−2.09, 27/33 | −345, t=−2.83, 29/31 |
| (1) `fwd_woolmilk` | −57, t=−1.41, 29/31 | +107, t=+1.82, 38/22 |
| (1) `fwd_four` (WOOL+MILK+CARROT+STRAWBERRY) | +4, t=+0.06, 32/27 | not measured (budget) |
| (2) `rl_implied_stack` (predicted rival layout) vs the stack | −265, t=−5.28, 9/51 | −274, t=−5.59, 8/52 |
| (2) `rl_implied_stack` vs the rebuilt clone control | −140, t=−6.74, 3/57 | −134, t=−7.41, 3/57 |
| (2) rebuilt clone control vs the stack (code-path check) | −177, t=−3.34, 27/33 | — |

**No new build. The best build stays `data/forward/wool_drain1_outerprem/main.py`, and the
fraction of the frontier's +4,407 explained stays ~18% in-sample / ~25% out-of-sample.**
Both Task-6 hypotheses are refuted, and the second one refutes my own Task-5 diagnosis
(the clone hypothesis is *better* than the observable rival channel, not the binding
limit).

## 1. Item-set extension (WOOL-only stays optimal)

The wool-only drain-keyed forward layer is the stack's existing component. Adding MILK,
CARROT, MILK+CARROT, or all four either loses or is a null:

* MILK and MILK+CARROT: −290/−291 in-sample and −345 in both out-of-sample rows; the
  per-seed spread is small (W/L 27/33 and 29/31), so this is a consistent small loss,
  not noise.
* CARROT: −279 in-sample and **−469, t=−3.98, 9/51** out-of-sample — the worst of the
  set, despite carrot having the second-largest unit gap in the Task-5 decomposition
  (+916 units over 60 towns). Adding units to our own carrot lots does not convert to
  money.
* WOOL+MILK: −57 in-sample, +107 out-of-sample (t=+1.82) — a null, not the Δ>0/t≥3 bar.
* All four: +4, t=+0.06 — a null.

Interpretation: the forward layer works only where the item's price is steeply
inventory-sensitive *and* our tape's own lots are small relative to the drain (wool).
For milk and carrot the same treatment adds units at moments when the price is not
recoverable by the drain, i.e. it just moves the collapse.

## 2. Predictive rival layout (the clone hypothesis wins)

Implementation (`scripts/build_race.py`, market-layer only, no farm change):

* the rival's per-item executed quantities are recovered exactly from public data —
  `inv_now − inv_prev = (our sells with price>1) + (rival sells with price>1) − town
  drain − (our executed BUY_PRODUCT) − (rival executed BUY_PRODUCT)`. Our side is
  computed with the replica; the drain from the engine's shop table (`SHOPS`, injected);
  the remainder is the rival's;
* their slot layout is NOT observable, so each recovered quantity is placed at the slot
  our own list uses for that item (the clone template) — the only slot information the
  game exposes;
* variants: `implied` (that schedule), `min2` (worst case over clone and implied),
  `hybrid` (implied when fresh, else clone), `anti` (maximise −D, the sign probe).

Two build bugs were caught by the counters before any duel, both of the "contradict
yourself" family the parent warned about: a helper I named `_race_schedule` shadowed the
renamed `race_layer.schedule` and emptied every contested set (the control stopped
matching the incumbent: 0 candidates against the incumbent's 11), and the observation
bookkeeping initially sat *behind* the step gates and only ran on searched steps, so the
implied schedule was permanently stale (`race_implied = 0` for whole games; the
bookkeeping now runs on every step, 222/719 steps produce an implied schedule). Two
further inference facts: our own BUY_PRODUCT orders move the same inventory and must be
subtracted (without that the inference goes negative and never fires), and sells at the
$1 floor do not raise the inventory, so they must be excluded too.

Result: **the observable-rival hypothesis is reliably worse than clone** — −140
(t=−6.74, W/L 3/57) in-sample and −134 (t=−7.41, 3/57) out-of-sample *against the
rebuilt clone control*, and −265/−274 against the incumbent stack. The consistency
(t≈7) rules out noise; this is a real, if small, loss. `min2` and `hybrid` collapse back
to the clone result, i.e. the worst-case and fallback wrappers simply refuse the implied
schedule wherever it differs.

**Sign probe: inconclusive, and I will not claim otherwise.** The `anti` variant
(choose the layout that minimises the margin) never acted: `race_considered = 124` but
`race_reorders = 0`, because the layer's final selection step re-scores every candidate
with the *true* margin and therefore always rejected the deliberately-bad layout — so the
variant degenerated to forward-only behaviour (delta +231 at seed 9000, i.e. the
no-reorder baseline). A valid sign probe needs the anti choice forced through the final
selection, which I did not have budget to build and measure. The analytical prediction
from `REPORT-race-mechanism.md` §1 stands untested by this round: in a slot the paired
units take equal prices, so the DIFFERENTIAL is produced only by the excess units — being
the larger side of a pairing scores positive, being smaller scores negative.

## 3. Why the clone hypothesis wins (and what that says about the residual)

The observable channel recovers *quantities*, never *slots*, and substituting observed
quantities into a guessed slot template loses ~140 vs simply assuming the rival mirrors
us. In a duel against a same-lineage build the clone assumption is nearly correct by
construction, so the observable channel mostly adds estimation noise.

That sharpens the residual to something more precise than "within-turn ordering":

* the frontier's whole edge is +4,409 per town on ~1,580 executed units — about **+2.8
  per unit averaged over every product**, while our two controllable market levers
  (slot layout + forward units) capture ~+0.5 per unit (the stack's +790 in-sample). So
  the mechanism may well still be interleaving, but we reach only ~18% of it;
* what our layers *cannot* touch: **which turn each of our lots is offered in**. The tape
  fixes that; the market layer may only re-slot within the turn and add units the shed
  already holds. The frontier's tape offers its lots on different turns;
* changing the turns our tape uses is a *plan* edit, and by the RNG finding (the day-6
  shop draw shares the weed-spawn RNG stream, so the tape itself can change) such an edit
  can only be judged by a full paired duel — one duel per candidate, no screens.

## 4. Honest list of what did not work in this round

* Forward layer on MILK / CARROT / MILK+CARROT / all four: negative or null on both
  panels (CARROT −469, t=−3.98 out-of-sample).
* Predictive rival layout from the public inventory delta: −140/−134 vs clone (t≈7),
  i.e. the clone hypothesis is better and my Task-5 "binding limit" diagnosis was wrong.
* Worst-case/hybrid wrappers over clone and implied: no effect beyond clone.
* Anti-direction sign probe: never acted (invalid as built) — reported as inconclusive,
  not as evidence in either direction.
* Two build bugs caught before measurement (helper name shadowing; bookkeeping behind the
  step gates) — both produced the "identical across parameters" signature and would have
  silently produced nulls.

## 5. Best build and rebuild command (unchanged)

```bash
# the live line, rebuilt from scratch
python scripts/build_race.py --name outer_prem
python - <<'PY'
import sys; sys.path.insert(0, "scripts")
import build_forward
build_forward.build({"forward_items": ["WOOL"], "forward_drain": True},
                    "wool_drain1_outerprem", "data/forward",
                    base_path="data/race/outer_prem/main.py")
PY
# measured, both panels, against the champion
python scripts/ab_duel.py --cand data/forward/wool_drain1_outerprem/main.py \
    --base data/tapeopt/rgcs/main.py --seeds 9000-9029 --procs 10 --label stack-IS \
    --out data/forward/duel-stack-outerprem.json
python scripts/ab_duel.py --cand data/forward/wool_drain1_outerprem/main.py \
    --base data/tapeopt/rgcs/main.py --seeds 9100-9129 --procs 10 --label stack-OOS \
    --out data/forward/duel-stack-oos.json
```

Artifacts: `data/rival/fwd_{control,milk,carrot,milkcarrot,woolmilk,four}/main.py`,
`data/rival/rl_{clone,implied,min2,anti,hybrid}_{race,stack}/main.py`,
`data/rival/sweep-part1.txt`, `data/rival/sweep-part2.txt`, `data/rival/duel-*.json`,
and the builder changes in `scripts/build_race.py` (SHOPS table, `_race_drain`,
`_race_my_inv_delta`, `_race_implied_rival`, `_race_item_schedule`, the `implied` /
`min2` / `hybrid` / `anti` hypotheses, and every-step bookkeeping in both hooks).

`layer_fallbacks 0`, `entry_fallbacks 0`, `race_errors 0` on every variant in this round;
the control (byte-identical copy of the stack) reproduced it exactly on both panels
(delta 0, all counters +0). Nothing submitted to Kaggle.
