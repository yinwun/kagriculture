# Layer upside (Task 28) — how many points can optimising our own layers add?

Date: 2026-09-22/23. Measurement only. **No submission; no live file touched.** Question: with the
line at 2,661.6 (rank 296/9,838) and ~2,900 = **+240 points ≈ +1.6 % of local wallet ≈ +1,600
coins/game**, how much of that can come from optimising our own layers?

## 0. Bottom line

**Our own layers are worth tens of points, not 240.** The only component with a large measured
increment is the late-window strawberry layer (**+480, t = 7.62, 53/7 on 9300–9329**; +416/+390 on the
Task-24 panels) — and that is **already shipped** inside 56447790. Of the *new* per-item extensions of
the same mechanism, the first one measured (**wheat**) is **significantly negative**: −516 coins,
t = −3.38, 16–44 on IS 9500–9529. So the Task-26 "largest reachable candidate" is **refuted**, and the
remaining sweep cells are pending (see §4: the machine is at load 264–464, so the duels are ~15 min
each instead of ~2).

| route | measured value | points (ruler ≈ 145 per +1 % wallet) |
|---|---|---|
| strawberry late-window layer (shipped) | +480 (t=7.62) / +416 / +390 | **≈ +70** (already in the line) |
| wool forward layer (shipped) | +264/+397 on the composite, +358/+493 on our champion | ≈ +38…+58 (already in the line) |
| race layer (shipped) | +112/+64 on the composite | ≈ +9…+16 (already in the line) |
| **wheat** late-window extension (**new, measured**) | **−516 (t = −3.38, 16–44) IS** | **≈ −75 → reject** |
| milk extension (cross-duel difference, not a paired ablation) | comp_straw_milk +375/+319 vs comp_straw +416/+390 | ≈ −6…−10 → reject |
| carrot / tomato / egg / fertilizer extensions | **pending** (§4) | — |
| pruning (race off / wool off / strawberry off) | **pending** (§4); every component measured positive so far | ≤ 0 expected |
| **total *remaining* upside from optimising our own layers** | **≈ 0 … +30 points** | **≈ 12 % of the +240 needed** |

## 1. Design (pre-registered, unchanged from the brief)

Built as single-item changes on top of the current line, all from the composite+race base with the
same outermost forward mechanism (drain-capped, `forward_start = 312` = day 13), only the item list
changed:

| variant | change vs `comp_straw` |
|---|---|
| `comp_straw_wheat` / `_milk` / `_carrot` / `_tomato` / `_egg` / `_fert` | that item added to `forward_items`, gated at step 312 |
| `comp_nowool` | WOOL removed (race + strawberry only) |
| `comp_norace` | race block removed (wool + strawberry only) |
| `comp_both` | strawberry removed (= race + wool) → the strawberry ablation |
| rebuild of `comp_straw` | **control**: must be byte-identical to the committed file |

Panels: **IS 9500–9529** and **OOS 9600–9629**, paired, seats alternating, 60 games each, candidate vs
`data/composite/comp_straw/main.py`. Pre-registered bar: **GO iff Δ > 0 with t ≥ 3 on BOTH panels AND
Δ ≥ +300**. Every variant's runtime and error counters are collected from the same JSONs
(`errors`, `cand_exceptions`, `base_exceptions`, `layer_fallbacks`, `entry_fallbacks`, `race_errors`).

Variant builds completed (all compiled): `comp_straw_wheat`, `_milk`, `_carrot`, `_tomato`, `_egg`,
`_fert`, `comp_nowool`, `comp_norace`, plus the `comp_straw` rebuild. The committed `comp_straw` is the
reference; the rebuild control is byte-compared in the sweep script (`CONTROL ... byte-identical`).

## 2. Measured sweep cells (so far)

| variant | panel | Δ wallet | Δ % | t | W–L | verdict |
|---|---|---|---|---|---|---|
| **comp_straw_wheat** | **IS 9500–9529** | **−516** | −0.54 % | **−3.38** | **16–44** | **NO-GO (significantly worse)** |
| comp_straw_wheat | OOS 9600–9629 | pending | | | | |
| comp_straw_milk | IS / OOS | (earlier Task-24 cross-duel: +375/+319 *vs comp_both*, i.e. below comp_straw's +416/+390) | | | | NO-GO (increment negative) |
| comp_straw_carrot / _tomato / _egg / _fert | IS / OOS | pending | | | | — |

Interpretation of the wheat result: this is the **direct test of Task 26's "largest reachable
candidate"**, and it fails in the direction the earlier evidence warned about — wheat is the feed
input, and the loss side already shows *milk* bleeding (−284 loss-minus-win) while wheat is withheld
from the market (−683 in losses). Selling the feed wheat makes both lines worse, exactly as the
non-wool forward history predicted (milk −290/−345, carrot −279/−469).

## 3. Component ablations — status and the prior measurements that stand in for them

The ablation cells (race off / wool off / strawberry off on 9500–9529 and 9600–9629) are **still
running** (§4). The question "does every layer still earn its place?" is partially answerable from
measurements already on record, each against the base it was added to:

| component | measured increment (base it was added to) | verdict |
|---|---|---|
| race (lockstep sell-layout search) | **+112 IS / +64 OOS** vs the plain composite (Task 22) | positive, small → **earns its place** |
| wool forward | **+264 / +397** vs the plain composite (Task 22); +358 / +493 vs our champion (Task 3) | positive → **earns its place** |
| strawberry (day 13+) | **+480 (t = 7.62, 53/7, 9300–9329)**; +416 / +390 (Task 24) vs `comp_both` | strongly positive → **earns its place** (and this is the layer whose *diagnosed target* had vanished — so the Task-26 cause table **understates** this family's headroom, as the brief noted) |

Nothing in the record says any of the three is neutral or negative, so **there is no measured pruning
gain yet**; the pruning upside is ≤ 0 unless the pending ablations contradict the above.

## 4. Why cells are missing, and how to collect them

The sweep was launched twice (items; then ablations first) and is still running. The machine is
saturated by work outside this session: **load average 264–464** (vs ~10 needed), so a 60-game duel
takes ~15 min instead of ~2, and 18 duel cells cannot finish inside this round. Completed cells land as
`data/composite/duel-t28-<variant>-<is|oos>.json`; the sweep script is idempotent (it skips existing
files), so re-running `.venv/bin/python scripts/t28_sweep.py` (or `T28_SET=abl ...`) completes the
matrix and prints the aggregated table with per-cell GO/NO-GO, errors, exceptions and the byte-identity
control.

## 5. Points-per-layer arithmetic, with confounds

* Ruler: **≈ 145 rating points per +1 % of local wallet**, from the single same-minute anchor
  (56409622 at 1,877.8 vs 56409633 at 2,487.7, +4.2 % local paired wallet gap).
* In points: strawberry ≈ **+70**, wool ≈ **+38…+58**, race ≈ **+9…+16** — **all three already inside
  56447790**, i.e. already paid for in the 2,661.6 we hold.
* Remaining, measured: wheat **≈ −75** (reject); milk increment ≈ **−6…−10** (reject).
* Remaining, unmeasured: carrot/tomato/egg/fertilizer (pending) and pruning (pending, expected ≤ 0).
* **Confounds (unchanged and binding):** n = 1 anchor, no replication; the anchored refs faced different
  opponent pools (mean 1,897 vs 2,283); the displayed score is the tracked submission's live rating
  (hours to converge, ±5 % wobble); the cutoffs move daily (top-5 % fell 28.7 points in a day while we
  climbed 175). Treat 145 pts/% as an order-of-magnitude ruler.

## 6. Answer to the question

* **How many points can optimising our own layers add?** On the measured evidence, **≈ 0 to +30
  points** beyond what is already shipped — the three shipped layers all earn their place (they are the
  +70/+50/+12 we already hold), the one new extension tested is significantly negative (wheat −516,
  t = −3.38), and the milk extension's increment is negative. The pending cells (carrot, tomato, egg,
  fertilizer; three ablations) would have to surprise us to change that.
* **Against the +240 needed for ~2,900:** the market-side total is ≈ **12 %** of the gap; the measured
  absolute ceiling of the whole Task-23/26 diagnosis (perfectly eliminating every remaining close-game
  deficit) is **+35 points**, and the best single layer ever found is **+70** (already shipped).
* **Where the +240 actually is:** in the **economy-simulation family** (feed→milk conversion, per-crop
  yield timing, `_hd2_*`/`_ca_*`/`_cs_*`/`_v92_p_*`) — the family where foreign composites measure
  +778…+4,407 against our builds and where every attempt of ours has measured ≤ 0. It is not in our
  market layers, not in the close-game deficits, and (Task 27) not in a stronger public base: all four
  extractable high-claim public bases were **neutral to significantly worse** than our current line
  (2965-claim +37/−82 tie; TOP-2 v4 −517/−698; 7-turn-rescue-2800 −345/−456; 2950-peak −545 IS), and
  every one of them carries **our exact route tape and opening**.

**Recommendation:** finish the sweep when the box is free (it is idempotent), but do not expect it to
change the answer; the line should keep running as-is, and ~2,900 should be treated as requiring an
S3-scale economy-simulation effort rather than more market layers.

## 7. Artifacts

| file | content |
|---|---|
| `scripts/t28_sweep.py` | builds every variant, byte-identity control, runs the duels, prints the aggregate table |
| `data/composite/comp_straw_{wheat,milk,carrot,tomato,egg,fert}/main.py` | per-item late-window variants |
| `data/composite/comp_nowool`, `comp_norace` | component ablations |
| `data/composite/duel-t28-*.json` | the measured cells (per-seed deltas, counters, exceptions) |
| `REPORT-gold-path.md` | Task 27: the public-base investigation and the itemised +240 accounting |

---

# Task 29 (bookkeeping) — sweep completed, provenance guard, tracked refs

## 29.1 Completed Task-28 matrix (17 of 18 cells; `comp_both` OOS still pending)

All cells are candidate **vs `comp_straw`**, paired, seats alternating, 60 games per panel, unused
seeds (IS 9500–9529 / OOS 9600–9629). Control: the rebuilt `comp_straw` is **byte-identical** to the
committed file (`ad2ddf2d60df5670…`), so the item-gate code path is provably inert when off.

| variant (single change) | IS Δ | IS t | IS W–L | OOS Δ | OOS t | OOS W–L | verdict |
|---|---|---|---|---|---|---|---|
| `comp_straw_wheat` | **−516** | −3.38 | 16–44 | **−762** | −3.43 | 2–58 | **no-go (worse)** |
| `comp_straw_milk` | +44 | +0.98 | 41–19 | +110 | +1.58 | 38–22 | no-go (below bar) |
| `comp_straw_carrot` | +2 | +1.02 | 9–7 | +0 | +1.22 | 10–6 | no-go (zero effect) |
| `comp_straw_tomato` | +0 | 0.00 | 3–3 | +0 | 0.00 | 2–2 | no-go (**knob non-binding**) |
| `comp_straw_egg` | −5 | −0.29 | 15–11 | +15 | +0.62 | 20–8 | no-go (zero effect) |
| `comp_straw_fert` | **−299** | −4.87 | 18–42 | **−315** | −4.69 | 24–36 | **no-go (worse)** |
| **ablation: strawberry off** (`comp_both`) | **−436** | −7.57 | 4–56 | pending | | | **layer earns its place (+436)** |
| **ablation: wool off** (`comp_nowool`) | **−282** | −3.89 | 12–48 | **−248** | −3.18 | 6–54 | **layer earns its place (+248…282)** |
| **ablation: race off** (`comp_norace`) | **−57** | −2.96 | 3–35 | **−64** | −4.43 | 2–44 | **layer earns its place (+57…64)** |

Errors/exceptions: `err = 0`, `cand_exceptions = base_exceptions = 0` in every cell;
`layer_fallbacks = entry_fallbacks = race_errors = 0`. The two exactly-zero cells are **not** broken
builds: `comp_straw_carrot` issues +163 extra forward orders in 60 games and `comp_straw_tomato` +5,
i.e. the knobs bind but the added units have no cash effect (carrot +2 coins, tomato 0).

**Conclusion:** every shipped layer earns its place (strawberry ≫ wool > race), **every per-item
extension of the same mechanism is neutral or negative**, and there is **no pruning gain**. The
market-side family is exhausted.

## 29.2 Provenance guard (fresh, 14 newest notebooks)

4 of 14 expose **our** blob `54fe156ea7206e38`; 10 expose no route payload at all (dataset/base85
paths); **exactly one exposes a different payload** — `syedtahahassan/kaggriculture-hack`,
`5df1c84699004845`. Checked: it is **not a route table**; it decodes to `{base, patches}` — a
step-indexed action tape with 12 route patches, opening `BUY_PRODUCT WHEAT 13 / SELL WHEAT 13`, i.e. a
different *encoding* of the same tape family, not new route data. **No evidence the field switched
data under us.** (`data/provenance-guard-t29.json`.)

## 29.3 Tracked refs (fresh)

| ref | build | games | W/L/T | win % | margin mean / median | opp mean |
|---|---|---|---|---|---|---|
| **56447790** | comp_straw (**displayed**: latest submission, 2026-09-22T01:13) | 152 | 92/60/0 | 60.5 % | +3,032 / +216 | 2,434 |
| 56422944 | comp_both | 213 | 123/90/0 | 57.7 % | +2,085 / +72 | 2,378 |

**T-3 recommendation:** re-submit **`comp_straw` unchanged** — no variant or extension cleared the bar,
no layer is worth pruning, and the displayed line is the best-measured one we have (~2,661 with the
field's opponent mean now 2,434). A fresh submission of the byte-identical build is the only action
that (a) keeps our best build displayed and (b) resets the age clock; it costs nothing in expectation.

---

# Task 30 — fresh attribution on the newest games

Pulled after the Task-26 snapshot (`--since 2026-09-22T14:53:10Z`): **37 new games** (21 losses,
8 near-losses, 8 wins; median margin −187), 37/37 bank-reproduction gate passed at shift = 1.

## 30.1 Per-item table, fresh losses (n=12, mean margin −2,161)

| item | u_me | u_opp | p_me | p_opp | rev_me | rev_opp | volume eff | price eff | buy_me | buy_opp | end_me / opp |
|---|---|---|---|---|---|---|---|---|---|---|---|
| **WHEAT** | 422.8 | 677.2 | 39.0 | 40.1 | 16,510 | 27,179 | **−10,069** | −600 | **7,318** | **17,324** | 0 / 0 |
| WOOL | 172.5 | 166.4 | 116.3 | 120.7 | 20,061 | 20,090 | +721 | −749 | 0 | 0 | 0 / 0 |
| **STRAWBERRY** | 246.1 | 239.2 | 149.2 | 154.7 | 36,705 | 37,006 | +1,038 | **−1,340** | 0 | 0 | 0 / 0 |
| MILK | 201.1 | 197.8 | 95.7 | 98.1 | 19,238 | 19,400 | +323 | −485 | 0 | 0 | 0 / 0 |
| EGG | 84.2 | 86.2 | 52.5 | 52.7 | 4,417 | 4,542 | −105 | −20 | 0 | 0 | 0 / 0 |
| CARROT | 109.4 | 105.3 | 45.1 | 45.6 | 4,938 | 4,807 | +185 | −54 | 0 | 0 | 0 / 0 |
| **TOMATO** | **6.7** | **20.7** | 167.5 | 114.4 | 1,117 | 2,365 | **−1,974** | +725 | 0 | 0 | 0 / 0 |
| MELON | 72.0 | 73.5 | 198.9 | 195.3 | 14,324 | 14,358 | −296 | +262 | 0 | 0 | 0 / 0 |
| FERTILIZER | 339.9 | 321.5 | 44.0 | 44.9 | 14,942 | 14,432 | +818 | −308 | 2,238 | 2,084 | 0 / 0 |

Wins (n=16): volume **−2,006**, price **+755** (strawberry price +629, wool +247); wheat volume
−2,058 with wheat purchases 6,457 vs 8,502. Day the deficit opens: day 3, with ~90 % accruing after
day 13 (unchanged from Task 26).

## 30.2 Ranked *fixable* candidates

| # | candidate | size | points (≈145/% wallet) | classification |
|---|---|---|---|---|
| 1 | **realised-price gap on premium items** (strawberry −1,340, wool −749, milk −485 in losses) | −2,569/game gross in losses | **≈ +38** if perfectly fixed | **FIXABLE BY MARKET LAYER** (sell timing/layout) — but partially captured: the race layer already earns +57…64, and in *wins* the same channel is **+755 in our favour** |
| 2 | wheat volume gap (−254 units, vol −10,069) | −10,069 gross, **−663 net** after the purchase offset | ≈ +10 net | **NOT FIXABLE**: wheat is the herd input (measured: wheat variant −516/−762, fertilizer −299/−315); the purchase channel nearly cancels it |
| 3 | tomato volume gap (6.7 vs 20.7 units) | −1,974 gross | ≈ +29 gross | **NOT FIXABLE BY US**: production volume (fewer tomato tiles/harvests), not a sale decision |
| 4 | logistics/wastage | discards 3.4–4.7 units/game; **ending stock = 0 for every item** | ≈ 0 | nothing to fix — the shed is fully liquidated |

**Strict verdict:** the only market-layer-reachable nomination is the premium **realised-price** channel,
worth ≈ +38 points at the unreachable-perfect-fix bound, and it is *already* the channel where we beat
opponents in wins (+755). Items 2–4 are excluded by input-sensitivity (measured negative) or by being
production-side. **Nothing fixable and material remains beyond what is shipped.**

---

# Task 31 — five-channel decomposition of the cash gap

Instrument: `scripts/t31_channels.py` — full bank-exact re-simulation logging every executed sell and
purchase with price, plus hires, land buys and discards, reconciled against the recorded money gap.

| channel (per game, mean) | **losses** (n=12, margin −2,161) | **near-losses** (n=9, −260) | **wins** (n=16, +692) |
|---|---|---|---|
| sell revenue, gross gap | **−11,927** | −? (small) | −1,251 |
| ├─ **volume** effect | **−9,358 (78 %)** | −72 | **−2,006** |
| └─ **realised price** effect | **−2,569 (22 %)** | **+81** | **+755** |
| purchase (input) cost offset | **+9,852** | +? | +2,012 |
| **net market channel** | **−2,075** | −195 | **+761** |
| hire / land | −167 / +333 | 0 / 0 | +6 / 0 |
| **residual** (seed + animal capex, uninstrumented) | −252 | −64 | −75 |
| discards | 3.4 units | 4.7 | 3.9 |
| ending unsold stock | 0 (all items) | 0 | 0 |
| production proxies: tiles & verbs | COW 25.0, SHEEP 26.5, STRAWBERRY 89.8, MELON 12; HARVEST 486, WATER 1,101 | — | COW 26.3, SHEEP 26.2, STRAWBERRY 90.0, MELON 12; HARVEST 483, WATER 1,104 |

**Reconciliation:** the cash channels close to within −252 (losses), −64 (near), −75 (wins); the
residual is the **seed and animal capex** channel (BUY_SEED was not instrumented and BUY_ANIMAL was
logged but excluded from the cost sum) — an investment channel, not a selling or production-volume
channel.

**One sentence with percentages.** Of the gross sell-revenue gap in close games, **≈ 78 % is volume and
≈ 22 % is realised price**, but the volume gap is a **standing characteristic** (it is also −2,006 in
wins) that is ~83 % cancelled by a **purchase/input-cost** advantage of similar size, leaving a net
market gap of only −2.1 k; **production capacity is identical in losses and wins** (tiles and verb
counts), **logistics/wastage is zero** (ending stock 0 for every item), and only the price channel
(≈ −2.6 k/game, ≈ +38 points at the perfect-fix bound) is reachable by an outermost market layer.

**Reachability classification:** market-layer-reachable = realised price only (our race layer already
earns +57…64, and price is *positive* for us in wins). Not reachable = production volume (identical
capacity; the difference is allocation/feed) and the input/purchase channel (wheat/fertilizer:
measured −516/−762 and −299/−315 when we try to monetise those inputs).

## 29.4 Fresh ladder row (same pull as 29.3)

**nickyl 2,648.9, rank 294 / 9,865, `submissionDate` 2026-09-22T01:13:54Z = 56447790 (comp_straw,
displayed).** Cutoffs: top 1 % = rank 98 → **2,757.6** (we are **108.7 short**), top 5 % = rank 493 →
**2,568.1** (we are **+80.8 inside**), top 10 % = rank 986 → 2,382.6. The score drifted −12.7 since the
Task-26 pull (2,661.6) while the cutoffs also fell (top-5 % 2,580.9 → 2,568.1), so we remain ~81 points
inside the top 5 % and ~109 short of the top 1 %.
