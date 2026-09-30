# Replay diagnosis of the new line (Task 23) — where the remaining problems are

Date: 2026-09-21. Subject: ref **56422944** (`comp_both` = the public composite + our race and
wool-forward layers, submitted 08:17 UTC) vs its base **56409633** (the plain composite). Method:
replay-based attribution, not impressions. Nothing was submitted; no live file was modified.

## 0. Headline — direct answers

| question | measured answer |
|---|---|
| **Where do the remaining problems show up?** | In the **late game (day 13→29)**: our mean liquid gap is *positive through day 13* and turns negative after it (−71 at day 14 → −1,147 at day 29, new line). In wins the **same window** goes the other way (+599 at day 13 → +1,837). Nothing before day 13 separates losses from wins by more than noise. |
| **Which day does the deficit open?** | **Day 13–14**, in both refs (composite: +406 at day 13 → −655 at day 14 → −4,265 at day 29). Per-game "first deficit day" clusters at day 0–2 but at ±30-coin magnitude — noise-level and frequently reversed by day 9. |
| **Which items carry it?** | **STRAWBERRY** (new line: −2,168 in losses vs +101 in wins = **−2,269 loss-specific**) and **WHEAT** net of feed purchases (−1,070 vs −159 = −911). In the composite the same two appear (WHEAT −1,424 vs −237; STRAWBERRY −579 vs +182) plus **MILK** (−1,403 vs +118). |
| **Did our layers fire?** | Yes. Wool selling coverage rose from **39 to 59 steps/game (+51 %)** and wool units from 163 to 171/game; in local counters the forward layer acts ~77×/game. The race layer fires rarely (~3 reorders/game) and its replay signature is weak (+6 multi-SELL steps/game). |
| **Most actionable remaining problem** | The **day-13→29 liquidation plan for premium stock, strawberry first** (composite: milk too). Every farm-side explanation is ruled out: worker verbs and per-tile crop/animal mix are **identical** in losses and wins, no shop-tuple clustering, and the opponent does **not** out-produce us in units. |
| **Is it (a) timing, (b) a product, (c) a branch, or (d) a stronger opponent?** | **(a) yes — late-game market timing; (b) yes — strawberry (and milk for the composite); (c) no — no shop tuple, no herd/crop branch, no workload difference; (d) no — we sell *more* wheat than the opponent (890 vs 727 units) and parity on strawberry (246 vs 251), so they out-*earn*, they do not out-*produce*.** |

Ladder state (fresh leaderboard pull, 2026-09-21): **rank 862 / 9,734, displayed score 2,474.3**
(our row's `submissionDate` = 56422944). It has **not** passed 56409633's **2,487.7** — it is 13.4
points (0.5 %) short. 56422944: 81 games, **62/19/0 = 76.5 %** win, margin mean +5,923 / median +994
(opp mean rating 2,243). 56409633: 118 games, **79/33/6 = 66.9 %**, margin +5,607 / median +804
(opp mean 2,283). Board top: DSM 3,107.4, Majkel1337 3,101.4.

## 1. Method and its gate

136 replays downloaded (`competition_episode_replay`, cached in `data/replays/`): for each ref **all
losses + all near-losses (|margin| ≤ 500) + a rating-matched win control** = 61 games (56422944) and
75 games (56409633). Every game was rebuilt from its recorded actions and passed the **bank
reproduction gate: 61/61 and 75/75 reproduced the recorded rewards to the dollar** at `shift=1`, so
every state below is a trustworthy reconstruction.

Two instruments:
* **Exact market attribution** — the recorded actions are replayed through the official engine with
  the engine's own `_commit_unit` wrapped, logging every executed unit with its seat, item and price.
  This gives per-seat per-item units, revenue and average realised price, and shed-overflow discards.
* **Replay-derived state** — per-day liquid net worth for both seats using the `day_gap._worth` math
  (money + shed + hand cargo × that day's prices + seeds at cost), worker verb counters from the
  recorded actions, and per-tile farm composition from `farms[p].tiles` at each day boundary.

Two format gotchas found and worked around: the replay's top-level `id` is a **UUID** while the
numeric episode id is `info.EpisodeId` (keying on `id` silently returns `None`); and the engine's
`town.unlocked_shops` is **town-level and identical for both seats**, so it cannot explain a
within-game loss by construction.

## 2. Sample structure (loss-enriched by design, with a matched win control)

| ref | losses (< −500) | near-losses (−500..0) | wins (≥ 0) |
|---|---|---|---|
| 56422944 new line | 9 | 10 | 42 |
| 56409633 composite | 12 | 21 (27 by liquid gap) | 42 (36 by liquid gap) |

Class sizes differ slightly between tables because the cause script splits on the **liquid net-worth
gap** while the addendum splits on the **money margin**: a few games (only in the composite's set)
lost on cash while holding more goods, or the reverse. The new line's classes are identical under both
splits.

Margin shape, full population (all episodes, not just the sample): the new line's closest margins are
−246, −126, −118, −37, −37, −36, −33, −32, −1, +24, +49, +52 …; the composite's include **6 losses by
exactly −50 and 6 exact ties (0)** — 12 of its 119 games land on exactly {−50, 0}, and the new line
has **no** such value in 82 games. We have not identified the mechanism; it is the clearest
structural difference the two market layers made.

## 3. The day the deficit opens (the central measurement)

Mean per-day liquid net-worth gap (me − opp), from `data/replay-causes.json`:

| class | day 0 | day 9 | day 13 | day 14 | day 19 | day 24 | day 29 |
|---|---|---|---|---|---|---|---|
| **new line losses** (n=9) | +3 | +147 | **+98** | **−71** | −414 | −721 | **−1,147** |
| new line near-losses (n=10) | +3 | −30 | −30 | −30 | +1 | +8 | −103 |
| new line wins (n=42) | +4 | −5 | **+599** | +476 | +572 | +809 | **+1,837** |
| **composite losses** (n=12) | +13 | +499 | **+406** | **−655** | −1,647 | −2,767 | **−4,265** |
| composite wins (n=36) | +2 | +20 | **+145** | +66 | +120 | +440 | **+1,014** |

* **Losses and wins are indistinguishable until day ~10** and diverge in the **day 13→29** window,
  in opposite directions. The crossing is between day 13 and day 14 for both refs.
* Near-losses are a *flat* −30 all game: a tiny persistent deficit, not a late collapse.
* Per-game first-deficit day for the new line's losses: {0: 5, 2: 2, 14: 1, 25: 1} — the early
  "deficits" are ±30 coins and are usually reversed by day 9 (wins also show {0: 10}).
* Standard deviations are large (600–4,000 late), so these are means over few games; the *sign
  change at day 13–14* is the robust part, not the individual day values.

## 4. Item-level attribution

Net contribution per item = (my revenue − my spend) − (opponent revenue − opponent spend), mean per
game, over the loss-enriched sample; then split by outcome to separate **loss-specific** structure
from items that are simply where the money is.

**New line 56422944** (loss n=9, near n=10, win n=42):

| item | losses | near | wins | loss − win |
|---|---|---|---|---|
| **STRAWBERRY** | **−2,168** | −130 | +101 | **−2,269** |
| **WHEAT** | **−1,070** | −100 | −159 | **−911** |
| WOOL | −83 | −35 | +344 | −428 |
| CARROT | +312 | +168 | +665 | −354 |
| TOMATO | −3 | +0 | +342 | −345 |
| MILK | −152 | −68 | +163 | −315 |
| EGG | **+1,157** | +12 | +267 | **+891** |
| FERTILIZER | +762 | +61 | +82 | +680 |
| MELON | +384 | +0 | +88 | +296 |

**Composite 56409633** (loss n=12, near n=21, win n=42): MILK −1,403 vs +118 (−1,521), WHEAT −1,424
vs −237 (−1,187), STRAWBERRY −579 vs +182 (−762), TOMATO −1,333 vs +2 (one −21,317 game), EGG −310 vs
+49 (−358), MELON +721.

Common to both lines: **strawberry and wheat**. In both lines we are also *better* than the opponent at
eggs and fertilizer in losses — the loss is a mix of items, not a uniform underperformance.

**Volume vs price** (symmetric decomposition, losses+near, new line):

| item | units me / opp | avg price me / opp | volume effect | price effect | net |
|---|---|---|---|---|---|
| STRAWBERRY | 246.3 / 250.9 | 96.4 / 97.4 | **−825** | −270 | −1,095 |
| WHEAT | 890.5 / 726.7 | 38.5 / 38.2 | +6,682 | +394 | −559 (after feed purchases) |
| MILK | 201.4 / 200.3 | 90.6 / 91.6 | +68 | −175 | −108 |
| WOOL | 158.6 / 157.0 | 105.2 / 106.7 | +121 | −179 | −58 |

* Strawberry is **volume-led** (−825) with a small price component (−270).
* **Wheat**: we sell *more* units than the opponent (890 vs 727) but the net is negative because we
  buy more wheat (feed) — the deficit is a feed-vs-sell trade, not a sales failure.
* Milk/wool are almost purely **price** effects (−175/−179) — the market-timing component is small,
  and on wool our forward layer trades price for volume to net ≈ 0. This matches the earlier finding
  that the reachable market edge is ~+0.5/unit.

## 5. Farm side: identical in losses and wins (rules out (c) and (d))

Worker verbs per game, mean (new line loss / near / win): PLANT 240/238/239, WATER 1111/1096/1103,
HARVEST 493/484/486, FEED 339/331/338, CARE 416/415/412, COLLECT_FERTILIZER 380/380/379,
PLACE 106/102/106, PICKUP 200/206/196, DROP 46/49/44, PASS 540/501/550. The composite's table is the
same shape. **No loss-class difference larger than ~10 actions out of ~3,000.**

Per-tile farm composition (me − opp, mean tiles, days 6/12/18/24), new line: STRAWBERRY −0.4,
MELON −0.1, WHEAT −0.3, TOMATO 0.0, CARROT 0.0, SHEEP +0.2, COW +0.1, WEED −0.1 — i.e. **our farm is
tile-for-tile the same as the opponent's and the same in losses as in wins** (composite losses show
+2.0 strawberry / −0.9 tomato out of ~100 tiles, with the same values in wins).

So: not a production collapse, not a herd/crop branch difference, not a labour difference.

Shop tuple: no clustering — with 9 losses the most frequent day-6 tuple appears **twice**; the win
distribution is equally scattered; and the tuple is shared by both seats in a game and endogenous to
play (the shop draw shares its RNG with weed spawning), so it cannot be a within-game cause.

## 6. Did our layers fire?

| signature (mean per game) | 56422944 (ours) | 56409633 (base) | change |
|---|---|---|---|
| SELL steps / 719 | 265 | 251 | +6 % |
| steps with ≥ 2 SELL lots | 56 | 50 | +12 % |
| **steps with a SELL WOOL order** | **59** | **39** | **+51 %** |
| WOOL units sold | 171 | 163 | +5 % |
| shed-overflow discards (per game) | 14.3 | 13.8 | ≈ 0 |

The forward layer's footprint is clear (it sells wool on half again as many steps). The race layer's
signature is weak by construction: locally it fires ~3 reorders per game (`race_reorders` 185 / 60
games, `race_tried` 37,858) because it only acts when ≥ 2 SELL lots are present and it can improve the
layout. Its measured marginal value is correspondingly small: **+112 (IS, t=3.12) / +64 (OOS, t=2.75)**
for race alone, **+264/+397** for forward, **+324/+448/+590** for both (Task 22, 90 towns, pooled
+454, t=+7.05). **This round did not run a per-game counterfactual** (my seat replaced by the plain
composite in the same game), so per-game layer *value* is not measured here — the numbers above are
from the paired duels, and the replay evidence is the activity signature only.

## 7. Cause table

Automatic classifier (priority PRODUCT → VOLUME → PRICE → LATE → EARLY), then the refined table that
the measurements support. The automatic one is honest but saturates: with deficits of a few hundred
coins, one item trivially explains ≥ 50 % of the gap.

| ref | automatic class | games | mean deficit | common worst item | tags |
|---|---|---|---|---|---|
| new line | PRODUCT | 18/19 | +595 | STRAWBERRY | EARLY 10, LATE 5 |
| new line | EARLY | 1/19 | +629 | FERTILIZER | EARLY 1 |
| composite | PRODUCT | 33/39 | +1,626 | WHEAT | EARLY 17, LATE 6, VOLUME 2, PRICE 1 |
| composite | OTHER | 6/39 | +1 | MELON | (exact ties: liquid gap 0) |

Refined cause table (what the day-, item- and farm-level numbers actually support):

| cause class | games affected (new line / composite) | mean contribution | evidence |
|---|---|---|---|
| **late-game premium liquidation, strawberry-led (day 13–29)** | 9 / 12 losses (and most near-losses) | **−1,100 / −1,600** (strawberry −2,168 in new-line losses) | gap crosses zero at day 13→14; strawberry volume −825 |
| **wheat feed-vs-sell trade** | 13 / 25 of the loss+near games | **−559 / −482** net | we sell 890 vs 727 units yet net negative: feed purchases |
| **milk price/mix** | small in the new line, large in the composite | −315 / **−1,521** | composite losses only |
| market layout / timing on milk + wool | most games, both refs | −175 … −270 (price effect) | our layers already act; measured layer value +324/+448 |
| early reversible deficits | 10 / 17 | ±30 … ±50 | magnitudes below noise; wins show the same |
| farm-side production / herd branch | **0** | 0 | verbs and per-tile mix identical across outcomes |
| shop tuple | **0** | 0 | no clustering; town-level and shared |
| opponent out-producing in units | **0** | 0 | we sell ≥ their units on wheat and parity on strawberry |

## 8. The single most actionable remaining problem

**The day-13→29 liquidation plan for premium stock — strawberry first, then (in the composite) milk.**
Concretely: in the games we lose, from day 13–14 onward the opponent converts the *same* farm
(strawberry tiles, sheep, cows, weeds all within ±0.4 tiles; identical verb counts) into slightly more
realised value, and the deficit is carried by strawberry volume (−825 units-priced) and wheat's
feed-vs-sell balance (−559 net). Our market-layout layers are already firing and are worth
+324…+590/town (measured, Task 22), and the pure price component on milk/wool is only −175…−270, so
the remaining lever is **when and how much premium stock is sold in the last third of the game**, not
the clearing layout and not the farm.

Honest caveats:
* The absolute size is small: the new line's losses+near-losses average **−595** liquid coins
  (median deficit 312) against a ±5 % wobble in ladder scores; wins show the *same* items positive, so
  this is a marginal edge, not a structural leak. It is not obviously worth a submission on its own.
* The last-entry ±50 / tie cluster in the composite (12 of 119 games) is unexplained and absent from
  the new line — worth one dedicated look before it is dismissed.
* Not attributable from replays: the opponent's **rejected** orders (only executed commits are
  recorded), so we cannot see whether their layout attempts failed; nor per-crop labour allocation
  (the verbs are aggregate, though the per-tile mix shows the crops themselves are the same); nor can
  the town's shop draw be treated as exogenous (shared RNG with play).

## 9. Artifacts

| file | content |
|---|---|
| `scripts/replay_manifest.py`, `data/replay-manifest.json` | loss / near-loss / matched-win selection |
| `scripts/fetch_replays.py`, `data/replays/*.json` | 136 replays |
| `scripts/replay_attribute.py`, `data/replay-attr-newline.json`, `data/replay-attr-composite.json` | per-game day gaps, exact item execution, verbs, discards, layer signature |
| `scripts/replay_causes.py`, `data/replay-causes.json`, `log/causes.log` | cause table + volume/price decomposition |
| `scripts/replay_addendum.py`, `data/replay-addendum.json` | loss-specificity, shop tuples, verbs by class |
| `scripts/replay_tiles.py` | per-tile crop/animal mix by outcome |
| `log/attr-newline.log`, `log/attr-composite.log` | 61/61 and 75/75 bank-reproduction gates |
