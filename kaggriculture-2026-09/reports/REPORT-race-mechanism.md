# Sell-layout race mechanism — lockstep replica, the `race_layout` layer, and what the frontier actually does

Date: 2026-09-19. Champion / baseline: `data/tapeopt/rgcs/main.py` (ladder 2,147.5).
Instrument: `scripts/ab_duel.py`, paired, seats alternating, 30 towns × 2 seats = 60 games
per variant, delta = mean per-seed (candidate wallet − champion wallet).
Champion file is never modified: every variant is a copy under `data/race/<variant>/main.py`.

## 0. Headline

| question | answer |
|---|---|
| Did a sell-layout layer beat the champion? | **Yes.** Best variant `data/race/outer_prem/main.py`: **delta +597, t=+9.87, W/L 58/2 over 60 games** (+0.58%), and on 30 *fresh* towns (seeds 9100–9129) **+676, t=+10.70, W/L 57/3**. Every action counter is byte-identical to the champion's, including `MKT_SELL` (18,619 vs 18,619 in-sample, 18,838 vs 18,838 out-of-sample): the entire gain is the order of the market list. |
| Is the frontier's own +4,407 explained by sell scheduling? | **No.** Two measurements below show its "37.7% more SELL orders" is a request-pattern artefact (85,884 requested units → 1,591 executed, i.e. the champion's 1,580), and that its edge tracks a **herd swap (geese → sheep when the town unlocks YARN_STORE)**, correlated −0.68 with the per-seed delta. |
| Reproduced the engine's clearing exactly? | Yes — 4 independent checks, 0 mismatches, including 2,872 player-steps of real games (`data/race-lockstep-test.txt`). |

## 1. Engine semantics replicated (`scripts/lockstep.py`)

From `kaggle_environments/envs/kaggriculture/kaggriculture.py` (1.32.7):

* `market_price(item, inventory, params)` is a **pure function of that item's market
  inventory**, floored at `PRICE_FLOOR = 1`; parameters come from `MARKET_PARAMS`
  (hardcoded copy; the observation's `market` dict contains **only** `inventory` and
  `prices` — verified, there is no `params` key and no local run overrides it).
* `_process_market` clears the two market lists **slot by slot**: slot *i* of player 0
  against slot *i* of player 1, one unit at a time, and slot *i* runs to exhaustion
  before slot *i+1* is even parsed. Both players are quoted the **same pre-commit
  price** for a paired unit; player 0 commits first (irrelevant for SELL, both see the
  same quote).
* `_commit_unit`: SELL needs `shed[item] > 0`, adds `price` to money and adds **1 to the
  market inventory only if `price > 1`**. BUY_PRODUCT is only legal for WHEAT/FERTILIZER
  and is quoted at the *post-buy* inventory, needs `money >= price` and
  `sum(shed) < shed_capacity`. BUY_SEED/BUY_ANIMAL are fixed-price, shed-capped.
  A failed commit kills the whole order (`order_states[p] = None`). Orders past
  `maxMarketOrdersPerTurn` (10) are dropped; HIRE/BUY_LAND are atomic per slot.
* `_town_consume` is the only upward force on prices: every step with `step % 4 == 0`
  each unlocked shop consumes 1 unit of each product it sells (2 if it sells exactly
  one product), and every 24 steps the town centre consumes 1 of each non-fertilizer.

### The lemma the whole mechanism rests on

Let `c` be the number of units of item X already sold in this turn by *either* player.
Every commit quotes `price = f_X(I0 + c)` (caveat: units sold at the $1 floor do not
raise the inventory, and the two players' commits in one iteration share one quote).
Therefore:

1. **A unit's price depends only on its position in the global unit order of that item,
   not on who sells it.**
2. **Paired units (same item, same slot, on both sides) earn the same price and
   contribute exactly zero to `revenue_me − revenue_opp`.** The differential comes only
   from *unpaired* units, so the whole lever is the slot layout of our own lots given a
   predicted rival layout — an assignment problem, exactly what the public notebook's
   `_v44y_lockstep` / `_v44y_factor_margin` pair also maximises.
3. Items are **independent** (only a WHEAT/FERTILIZER BUY_PRODUCT touches another
   item's inventory, and it is itself an order of that item), so a per-item replay is
   exact and cheap. All the layer's simulations use this.

## 2. Replication evidence

`scripts/test_lockstep.py` (`data/race-lockstep-test.txt`), all four checks pass:

```
A. price model: 12942 checks over 720 steps x 2 players (seed 9000) -> mismatches 0
   observation market keys seen: ['inventory', 'prices']
B. clearing: 400 random trials -> failures 0
C. clear_item vs clear (per-item decomposition): 300 trials -> mismatches 0
D. real game seed 9000: final [110917.0, 110917.0], 719 steps, money mismatches 0
D. real game seed 9001: final [109282.0, 109282.0], 719 steps, money mismatches 0
   total 2872 player-steps replayed, mismatches 0
RESULT: PASS
```

* **A** — for every step × product, `market_price(item, inventory[item])` reproduces the
  observation's own `prices[item]` (12,942 checks, 0 mismatches).
* **B** — randomised order pairs against the real engine: a real env is reset, the
  market inventory, both sheds, both money balances, `hires_today` and the unlocked
  quadrant count are injected, then `env.step()` is called with the trial's two market
  lists (including malformed orders, qty ≤ 0, unknown items, HIRE, BUY_LAND, BUY_SEED,
  BUY_ANIMAL, BUY_PRODUCT, shed exhaustion and shed-capacity overflow). The replica's
  final **money, market inventory and both sheds** all match the engine exactly.
* **C** — the layer's fast path (`clear_item`, per item) sums to the full replica's joint
  revenue on SELL-only lists.
* **D** — 719 steps × 2 players × 2 real champion games, replaying the champion's own
  order lists (HIRE ×8, BUY_PRODUCT, BUY_SEED, multi-slot lots) and comparing the
  predicted money with the money the engine produced: 0 mismatches.
  **This check needs the market-time shed**: `interpreter` applies this step's farmer/hand
  actions (DROP/PICKUP) *before* `_process_market`, so replaying from the observation's
  shed mispredicts every step with a DROP (224 mismatches of 1,438 player-steps);
  `scripts/race_trace.py` recomputes the shed with the engine's own
  `_apply_unit_action`, after which the mismatch count is 0.

Known limitations (documented in the module): the replica models the published rules only;
`clear_item` ignores money (irrelevant for SELL) and caps a player's sellable units at
`stock[item]` per order, so two orders of the same item in one turn can over-estimate
availability by at most the overlap; `marketParams` configuration overrides are supported
through the `params` argument but are never exercised.

## 3. The layer (`scripts/build_race.py` → `data/race/<variant>/main.py`)

Two hooks, both injected by the builder, both off by default in the champion:

* `race_hook = "chassis"` — a method `Chassis._race_layout` called immediately **before**
  `action["market"] = action["market"][: cfg["max_orders"]]`, i.e. last in the chassis'
  market chain, exactly as briefed. `_View` is patched to expose `market_inv` and `town`
  (note: `_View` already has a *method* `inv(idx)` — storing the market inventory under
  `.inv` silently breaks five call sites and disables the whole chain, which is exactly
  what happened on the first build; it showed up as a 34k/152k score instead of 110k/110k).
* `race_hook = "outer"` — a new outermost `agent` wrapper appended after the ~120 public
  wrapper agents that sit *outside* the chassis. **This mattered**: those wrappers insert,
  drop and re-sort market orders after the chassis ran, and the champion's own file
  contains all of them (`_r37_reorder_sales` + `_r37_quote_priority` re-sort contiguous SELL
  blocks, `_r51_close_warehouse` adds sales, `_r127_priority`/`_r128_credit_supply` prepend
  BUY_PRODUCT orders). Measured with `scripts/race_diag.py`: with the chassis hook only
  **4 of the 12 emitted layouts reached the engine unchanged**; with the outer hook
  **9 of 9**.
* `race_hook = "both"` runs both passes (the outer pass repairs what the wrappers did).

The search (`scripts/race_layer.py`, spliced verbatim into the built agent):

* rival hypotheses: `clone` = our own pre-layer list (default; the rival in a duel is the
  same lineage running the same layers on nearly the same prices), `tape` = the raw tape
  action for this step, `none` = empty list (a provable no-op control), `min` = pick the
  layout with the best *worst case* over clone and tape;
* per contested item, the slot's simulated margin comes from `clear_item`; the slot
  assignment is solved exactly (brute force over the small contested set);
* quantities are never touched, non-SELL orders keep their slots, unplaced sells keep
  their relative order; a slot past the end is padded with `[]` (the engine parses it as
  "no order", so padding only delays what follows);
* `race_items` restricts the search to high-value items (the slot budget is the scarce
  resource, and spending it on WHEAT/FERTILIZER crowds out the items whose price slope
  actually pays);
* every quantity and the number of orders are preserved, so `MKT_SELL` is unchanged by
  construction — confirmed in every duel JSON (see table).

## 4. Measured variants (60 games each: 30 towns × 2 seats, vs the champion)

| variant | settings | delta | t | W/L | MKT_SELL cand/base |
|---|---|---|---|---|---|
| `control` | `race_layout=0` (layer inert) | **+0** | +0.00 | 5/5 (30 ties) | 18,616 / 18,616 |
| `clone` | chassis hook, clone | +304 | +7.48 | 56/4 | 18,614 / 18,614 |
| `tape` | chassis hook, tape hypothesis | +114 | +4.91 | 55/5 | 18,614 / 18,614 |
| `minhyp` | chassis hook, worst case of clone+tape | +304 | +7.47 | 56/4 | 18,614 / 18,614 |
| `mineobj` | maximise `revenue_me` instead of the margin | +304 | +7.50 | 56/4 | 18,616 / 18,616 |
| `premium` | chassis hook, premium items only | +372 | +7.45 | 54/4 | 18,614 / 18,614 |
| `outer` | outer hook, clone | +386 | +8.32 | 57/3 | 18,620 / 18,620 |
| `outer_wm` | outer hook, WOOL+MILK only | +170 | +4.11 | 57/3 | — |
| `outer_prem` | **outer hook + premium items** | **+597** | **+9.87** | **58/2** | 18,619 / 18,619 |
| `outer_wms` | outer hook, WOOL+MILK+STRAWBERRY | +597 | +9.87 | 58/2 | — |
| `outer_prem5` | outer hook, premium + EGG | +577 | +9.84 | 58/2 | — |
| `outer_prem_g0` | as `outer_prem`, `min_gain=0` | +597 | +9.87 | 58/2 | — |
| `outer_prem_rs` | as `outer_prem`, rival shed unlimited | +597 | +9.87 | 58/2 | — |
| `prem_wm` | chassis hook, WOOL+MILK only | +121 | +3.41 | 53/5 | — |
| `both_prem` | both hooks + premium items | +562 | +9.88 | 57/3 | — |
| `both_prem_min` | both hooks, premium, worst-case hypothesis | +562 | +9.89 | 57/3 | — |
| `outer_prem` (OOS seeds 9100–9129) | **out-of-sample confirmation** | **+676** | **+10.70** | **57/3** | 18,838 / 18,838 |
| `outer` (OOS seeds 9100–9129) | outer hook, all items | +467 | +8.29 | 57/2 | — |

Two controls behave as they must: `control` gives **delta exactly 0 with byte-identical
wallet and action counts** (5 wins / 5 losses are the 20 non-tied games), and `nonehyp`
cannot reorder by construction. The "different parameters, identical result" trap was
checked explicitly rather than assumed: `outer_prem` / `outer_wms` / `outer_prem_g0` /
`outer_prem_rs` are byte-identical *because the extra item (MELON), the extra threshold and
the rival-shed assumption never win or bind in these games*, not because the layer died —
verified with `scripts/race_diag.py` (`race_tried=238, race_considered=7, race_reorders=5`,
identical emitted layouts), while `outer_wm` (WOOL+MILK), `outer_prem5` (+EGG), `both_prem`
and the `tape`/`none` hypotheses all move the numbers, and `layer_fallbacks == 0` and
`race_errors == 0` in every variant. The hook choice is also a measured effect, not a
detail: chassis +386, outer +386→+597 with premium items, both +562.

Champion wallet on this 60-game panel: 103,021–103,280; the best variant earns 103,617.

## 5. The ceiling of the mechanism (`scripts/race_headroom.py`)

For every step of a recorded game we know both players' true market lists, so the oracle
(the best layout with **perfect** knowledge of the rival's layout) can be computed:

| game (mirror, champion vs champion) | actual per-step margin | oracle | honest (clone-hypothesis) layout |
|---|---|---|---|
| seed 9000 | 0 | +513 | +316 |
| seed 9001 | 0 | +963 | +742 |

The oracle gains are concentrated in the last two days (steps 647–695: +193, +588) where
lots are largest and the price slope steepest, and they come from rotations of the item
order (put the steep-slope item first, push the shallow one later). The measured +597
average is therefore **at or slightly below the perfect-information oracle** for these
games — which is why the magnitude is ~0.6% and not ~4%.

## 6. What failed, and why

* **Deferring sales (previous attempt, `sell_spread`)** — −2,815 at t=−6.65; not revisited.
* **Splitting a lot across two slots** — analysed and rejected on theory, not implemented:
  with a single rival lot per item, putting all of our units in the earliest free slot
  strictly dominates splitting them between that slot and a later one (the price the *k*-th
  global unit receives is the same for everyone, so extra units must go as early as
  possible; the only effect of a split is to demote some of our own units). The oracle
  search over single-slot assignments already captures the available gain.
* **`tape` as the rival model** (+114, t=4.91): the tape misses the champion's own reactive
  sells (`sell_lead`, `dead_stock`, `_r37_reorder_sales`), so it mispredicts the rival's
  layout; `clone` is measurably better. Worst-casing over both (`min`) adds nothing.
* **The in-chassis hook alone**: only 4 of 12 emitted layouts survive the wrapper chain,
  which caps the realisable gain at ~+300 instead of ~+600.
* **The frontier's "+37.7% SELL orders"**: covered in §7 — it is not extra sales.

## 7. What the public frontier's +4,407 actually is

`scripts/race_sell_compare.py` (one game, seed 9000, frontier at seat 0):

```
CAND: 470 SELL orders on 287 steps, requested 85,884 units, executed  1,591 units, revenue 130,195
BASE: 323 SELL orders on 239 steps, requested  1,597 units, executed  1,580 units, revenue 130,347
```

The frontier requests **85,884** units and the shed lets it sell **1,591** — the same as the
champion's 1,580. Its extra 147 orders are orders that fail immediately (`SELL <item> 9000`
against a shed holding single digits), so the counter difference is an artefact of the
request pattern, not of more or better-scheduled sales. At seed 9000 the whole game differs
by +145.

Where the +4,407 does come from: `scripts/frontier_herd_diag.py` records, for all 30 duel
towns, the shop list, the final animal census and the wallet delta:

```
corr(delta, geese cand-base)                 = -0.68   (the frontier ends with FEWER geese)
corr(delta, sheep cand-base)                 = +0.52
corr(delta, count(YARN_STORE in day-8 shops))= +0.50
seeds WITH a YARN_STORE: n=23 mean delta +5,336
seeds WITHOUT          : n=7  mean delta +1,353
```

The frontier converts geese into **sheep** when the town unlocks a YARN_STORE (its own
public lineage ships exactly this: `_y_target(kind, shops, cfg)` with `yarngeese`/`yarnsheep`
and `days=(8,11)`), so it produces WOOL at ~$160–240/unit instead of EGG at ~$35. At seed
9005 it ends with 17 sheep vs the champion's 16 and sells 393 wool units vs 353, all at a
slightly better average price, for +12,969 revenue — and the same town shows +12,873 wallet
(+11,411 at seed 9015, +12,113 at seed 9027, …). At seed 9000, where no YARN_STORE is drawn,
the census is identical and the delta is +145.

So: the frontier's advantage is a **farm-side herd swap**, not market scheduling. Its
largest deltas are exactly the seeds where the yarn store appears.

## 8. Caveats

* The panel is 30 towns (9000–9029) for every variant, plus an **out-of-sample** run on
  9100–9129 for the winner (`+676, t=+10.70, 57/3`, i.e. the effect is not seed-range
  overfitting; champion wallet on that panel is 96,170).
* Magnitude is small (+597 on a ~103k wallet, +0.58%); the t-statistic is large because the
  paired per-seed delta is very consistent (SE ≈ 60), not because the effect is big. This
  is a real but modest gain, not a solution to the 4,400-point gap.
* The search assumes the rival's *executed* quantity equals its request capped by our own
  projected shed (`race_rival_shed="mine"`, the default); `"none"` (unlimited) measures
  byte-identically, so this assumption is not load-bearing on this panel.
* `race_headroom.py`'s oracle is exact but only over single-slot assignments of our own
  lots; it is a lower bound on the true oracle and an upper bound on any honest layer.
* The layer is inserted as a new outermost wrapper in the *copy*; the champion itself is
  untouched, but note that the built file therefore has two extra hook points relative to
  the champion (a dormant `Chassis._race_layout` and the active outer wrapper).
* Nothing has been submitted to Kaggle (out of scope by instruction).

## 9. Build recipe and recommended next step

```bash
# rebuild the winner from scratch (champion file untouched)
python scripts/build_race.py --name outer_prem
# verify the layer runs clean (layer_fallbacks == 0, race_errors == 0, layouts survive)
python scripts/race_diag.py --variant outer_prem --seed 9000
# decision instrument
python scripts/ab_duel.py --cand data/race/outer_prem/main.py \
    --base data/tapeopt/rgcs/main.py --seeds 9000-9029 --procs 10 \
    --label outer_prem --out data/race/duel-outer_prem.json
```

`data/race/outer_prem/main.py` (sha256 `22920a02d8b16b20…`, rebuilt twice from
`scripts/build_race.py` with identical hashes) = champion + `Chassis._race_layout` (inert,
`race_hook="outer"`) + an outermost `agent` wrapper running the layout search
(`race_hyp="clone"`, `race_items=["WOOL","MILK","STRAWBERRY","MELON"]`). Settings live in
`_SETTINGS`; removing the `race_layout` key restores the champion exactly (`control`).
Re-measured on the final artifact after the last builder edit: **+597, t=+9.87, 58/2**
(`data/race/duel-outer_prem-recheck.json`), identical to the original run, and
**+676, t=+10.70, 57/3** on the fresh 9100–9129 towns. Clean-run check on that artifact:
`race_tried=238, race_reorders=5, race_errors=0, layer_fallbacks=0, entry_fallbacks=0`,
and 5 of 5 emitted layouts reached the engine unchanged.

Recommended next step, in order:

1. **Do not chase sell scheduling for the remaining +3,800.** The mechanism is now
   measured at its oracle ceiling (§5); the frontier's real edge is the YARN_STORE-driven
   goose→sheep swap (§7), worth ~+5,300 on the 23 seeds where the yarn store appears. Port
   that mechanism into our own lineage (a herd-swap layer keyed on `town.unlocked_shops`,
   around days 8–11) and re-measure with `ab_duel.py`. That is a much larger and cheaper
   win than any further layout tuning.
2. Then re-run `outer_prem` as a stacking layer on top of the herd fix; the two mechanisms
   are independent (market-side vs farm-side) and should add.
3. Submit only after (1) and (2) are measured; submission stays a human-approved step.

## 10. Artifacts

* `scripts/lockstep.py`, `scripts/test_lockstep.py` (+ `data/race-lockstep-test.txt`) —
  replica and its four checks.
* `scripts/race_layer.py`, `scripts/build_race.py` — the search and the builder
  (`data/race/variants.json` lists all 25 settings).
* `scripts/race_probe.py`, `scripts/race_trace.py`, `scripts/race_diag.py`,
  `scripts/race_headroom.py`, `scripts/race_sell_compare.py`,
  `scripts/frontier_herd_diag.py`, `scripts/race_sweep.sh` — probes used above.
* `data/race/duel-*.json` / `.log`, `data/race/sweep-round{1,2,3}.txt`,
  `data/race/herd-diag.{json,txt}`, `data/race/duel-outer_prem.json`.
