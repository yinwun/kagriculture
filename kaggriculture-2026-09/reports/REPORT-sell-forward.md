# Sell-FORWARD layer — measured, and the mechanism it actually uses

Date: 2026-09-19. Incumbent to beat: `data/race/outer_prem/main.py` (submitted, ref
56348775; +597 in-sample / +676 out-of-sample). Champion/baseline:
`data/tapeopt/rgcs/main.py`. Instrument: `scripts/ab_duel.py` (paired, seats
alternating, 30 towns × 2 seats = 60 games per panel).

## 0. Headline

| candidate | in-sample 9000–9029 | out-of-sample 9100–9129 |
|---|---|---|
| `wool_drain1` (forward alone) | +358, t=+2.57, 47/13, 103,289 vs 102,931 | **+493, t=+3.74, 51/9**, 96,434 vs 95,942 |
| `wool` (forward alone, unbounded) | +201, t=+3.09, 51/9 | +321, t=+2.90, 51/9 |
| `outer_prem` (incumbent, race only) | +597, t=+9.87, 58/2 | +676, t=+10.70, 57/3 |
| **stack: forward + `outer_prem`** | **+790, t=+5.29, 53/7**, 103,502 vs 102,712 | **+1,099, t=+7.84, 57/3**, 96,701 vs 95,602 |

The forward layer alone clears the bar out-of-sample but not in-sample; the **stack
clears it on both panels** and is the best build this repo has measured: +790
in-sample and +1,099 out-of-sample over the champion, i.e. +193 / +423 on top of the
submitted incumbent. `layer_fallbacks == 0` and `entry_fallbacks == 0` in every run.

**But the mechanism is not the one we were chasing.** The layer does *not* move units
out of the day-24 price collapse — the day-window split is bit-identical with and
without it (below). Its gain is a within-turn interleaving effect, the same lever the
race layer exploits, which is why the two are partially redundant.

## 1. What the layer does (`scripts/build_forward.py`)

`Chassis._forward_sells`, called last in the chassis' market chain (immediately before
the `action["market"][: max_orders]` truncation, i.e. after `clamp_sells`): for each
item in `forward_items`, sell the whole projected shed every step instead of waiting
for the tape's scheduled lot — merging into an existing SELL of the same item when the
market list is already full, and never asking for more than the projected shed so the
engine never rejects it. It never modifies or suppresses a tape order; the tape's own
later order simply finds less stock (the champion's `clamp_sells` bounds it), so the
total sold per item is unchanged — measured: identical totals in both windows.

Levers, all OFF by default (`forward_items = None` → `control` is behaviour-identical
to the champion): item set (`wool`, `wool_milk`, `premium`, `all`), start/stop step,
`forward_min_price`, `forward_drawdown` (cap on units per step), and
`forward_drain` (cap the step's extra units at the town's own demand rate for that item
— a single-product shop consumes 2 units, any other 1, every 4 steps, plus 1 per 24
steps from the town centre; taken from the engine's `SHOPS` table).

Interaction with the layers that already sell: `sell_lead` is ON in the champion and
pulls up to `block_turns = 72` steps of planned sells forward; `dead_stock` and
`terminal_liquidation` are OFF. The forward layer never writes into `sell_lead`'s
suppression bookkeeping (`sell_state`) — it only *adds* quantity — so the two cannot
double-sell: the stock is the shared bound and `clamp_sells` (running just before it)
re-derives the tape quantities. That is deliberate: any suppression bookkeeping would
have to be threaded through three layers of state for no measured benefit.

## 2. Mechanism evidence (the parent asked for this specifically)

Wool, per player, on one game with the layer vs the champion alone, using the
validated market-time shed (`scripts/lockstep.py` + `scripts/race_trace.py`):

| seed | variant | total wool units | days 0–23 | days 24–29 | mean price |
|---|---|---|---|---|---|
| 9009 | `wool_drain1` | 228 | **163** | 65 | **119.9** |
| 9009 | champion | 228 | **163** | 65 | 111.8 |
| 9005 | `wool_drain1` | 359 | 216 | 143 | 239.4 |
| 9005 | champion | 359 | 216 | 143 | 239.3 |
| 9009 | `wool` | 236 | 164 | 72 | 112.4 |
| 9009 | champion | 236 | 164 | 72 | 110.4 |

**The units, the day-window split and the totals are identical.** What changes is the
mean realised price within the same turns (+8.1/unit at seed 9009), i.e. the added
order occupies a different slot of the same turn and takes the better part of that
turn's price walk. By the parent's own criterion — *"a wallet gain with no movement
into the high-price window means the gain is not the mechanism"* — **the collapse-
avoidance story is not what the layer is doing**, and it cannot be: the front-loaded
units have to exist in the shed first, and our production/shed limits mean the day-24
wool is produced on day 24.

The residual (frontier vs champion) timing effect therefore has two separable parts,
and only the small one is reachable from our side:

* frontier `sheep-days` 8,548 vs our 7,900 at seed 9005 (+8%) — that is a *farm-side*
  difference (more/earlier sheep) that produces the ~65 extra wool units; no sell
  layer can create them;
* at seed 9009, where sheep-days are equal (5,896 vs 5,844), the frontier still earns
  +3,578 on *fewer* wool units — that part is within-turn/interleaving, and that part
  is what both our race layer and this forward layer capture (a few hundred per game,
  not a few thousand).

## 3. Stacking with the incumbent

`python scripts/build_forward.py` does not read `data/race/`; the stack is built by
passing the race build as the base (the race builder already consumed the `_SETTINGS`
anchor, so the forward settings are applied by updating `_IMPL.chassis.cfg` at import):

```bash
python - <<'PY'
import sys; sys.path.insert(0, "scripts")
import build_forward
build_forward.build({"forward_items": ["WOOL"], "forward_drain": True},
                    "wool_drain1_outerprem", "data/forward",
                    base_path="data/race/outer_prem/main.py")
PY
```

Stack vs incumbent: +790 vs +597 in-sample (+193) and +1,099 vs +676 out-of-sample
(+423). Partially redundant (standalone was +358/+493) but clearly additive, and both
components pass the bar in the stack. `race_errors == 0`, `layer_fallbacks == 0`.

## 4. A broken build, caught by the counters (worth recording)

The first stack-capable version of the builder guarded the `_View` patch with
`if "unlocked_shops" not in src:` — but the champion's own module docstring contains
the string `unlocked_shops`, so the guard skipped the patch, `view.town` did not exist,
the layer raised every step, and the chassis' outer handler fell back to the raw tape
for the whole game. Signature: −32,430 (t=−8.52) and *byte-identical* results for two
different parameter values. Fix: test for `"self.town = list("`, i.e. for the patch
itself, and assert it in the builder. The fixed build reproduces the pre-break
sha256 exactly (`wool_drain1` = `6fe6ed2e3829`), 61 forward orders, 0 fallbacks.

## 5. Honest accounting against the frontier's +4,407

* Forward layer alone: **+358 (8%) in-sample, +493 (11%) out-of-sample** — of which
  none is the collapse-avoidance mechanism.
* Race layer (`outer_prem`): +597 (14%) / +676 (15%).
* Both together: **+790 (18%) / +1,099 (25%)**.
* Not explained (75–82%): the frontier's sheep-days advantage (a farm-side plan
  difference), its wheat availability (+52 / +78 units per game at identical average
  prices), and the rest of its within-turn price edge that our slot assignment does not
  reach because our tape does not put the same stock on the market in the same turns.
  Both files replay disjoint tape tables (0 of 41 route tapes byte-identical) with
  otherwise ~1–3% identical action counts, so the residual is inside its plan, not in a
  single switch we can flip.

**Per-seed unevenness:** the race layer's gain is highest exactly on the yarn-shop
seeds already identified (46/0 on the 23 YARN_STORE towns, +632) and small elsewhere;
the forward layer is spread more evenly (47/13 and 51/9 across the panels) — it wins
small on most towns and loses on a few.

## 6. Recommended next step

1. Keep the stack (`data/forward/wool_drain1_outerprem/main.py`) as the candidate; it
   is strictly better than the incumbent on both panels (+790/+1,099 vs +597/+676) and
   the two components are independent layers, so it is a low-risk change.
2. The remaining 75–82% is not reachable by re-timing or re-slotting our own orders:
   the frontier's advantage includes more sheep-days and more wheat, i.e. its *tape
   plan* differs. The highest-value next experiment is a route/plan comparison on the
   seeds where our router picks the worst tape (the 41-route screen at t=+0.14 was a
   6-game screen — it needs 30 seeds per promising route), or an honest re-tune of the
   farm plan on the YARN_STORE shop tuples.
3. Do not submit anything; submission stays with the parent.

## 7. Rebuild commands

```bash
python scripts/build_forward.py                      # all forward variants (control included)
python scripts/build_forward.py --name wool_drain1    # forward alone
python - <<'PY'                                       # stack on the incumbent
import sys; sys.path.insert(0, "scripts")
import build_forward
build_forward.build({"forward_items": ["WOOL"], "forward_drain": True},
                    "wool_drain1_outerprem", "data/forward",
                    base_path="data/race/outer_prem/main.py")
PY
python scripts/ab_duel.py --cand data/forward/wool_drain1_outerprem/main.py \
    --base data/tapeopt/rgcs/main.py --seeds 9000-9029 --procs 10 \
    --label stack-fwd+outerprem --out data/forward/duel-stack-outerprem.json
python scripts/ab_duel.py --cand data/forward/wool_drain1_outerprem/main.py \
    --base data/tapeopt/rgcs/main.py --seeds 9100-9129 --procs 10 \
    --label stack-oos --out data/forward/duel-stack-oos.json
```

Artifacts: `data/forward/{control,wool,wool_milk,premium,all,wool_d10,wool_d20,wool_g5,wool_draw1,wool_draw2,prem_draw2,wool_drain1,wool_drain2,prem_drain1}/main.py`,
`data/forward/wool_drain1_outerprem/main.py`, `data/forward/variants.json`,
`data/forward/sweep{1,3}.txt`, `data/forward/duel-*.json`, `scripts/forward_diag.py`
(day-window diagnostic; note it uses the pre-unit-action shed and therefore *under*-counts
absolute units — the table in §2 comes from the validated `race_trace` pipeline instead).
