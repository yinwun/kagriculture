# Uplift on the current line (Task 26) — what the 56447790 replays say now

Date: 2026-09-22. Subject: **56447790** (`comp_straw` = public composite + our race, wool and
day-13 strawberry layers), ~14 h on the ladder. Same instruments and discipline as Tasks 23/25
(instrumented bank-exact re-simulation, shift = 1). **Nothing was submitted; no live file touched.**

## 0. Headline

1. **Ladder: our row is 2,661.6, rank 296 / 9,838 (top 3.0 %).** We are **+80.7 above the top-5 %
   cutoff (2,580.9)** and **107.9 below the top-1 % cutoff (2,769.5)**. The reported ~2,650 is right:
   the line reached 2,661.6.
2. **The current games: 99 attributed, 99/99 bank-gated** (22 losses, 18 near-losses, 59 wins). The
   deficit **opens at day 3** (a −70 plateau) and losses stay within ~100 coins of wins until
   **~day 17**; from day 17 to 29 the two separate (+42 for wins vs −547 for losses at day 18,
   ending +914 vs −928). ~90 % of the deficit still accrues after day 13.
3. **The leading loss-specific item is WHEAT** (−683 in losses, −603 loss-minus-win), **volume-led**:
   we sell **577.9** wheat units against the opponents' **749.1** in close games. **The strawberry
   leak the layer was built for has fully inverted into a strength**: +758 in wins, only −163 in
   losses, unit parity (246.5 vs 247.6) and a realised price of **126.3** — the highest we have
   measured in any sample (96.4 in the Task-23 games, 118.9 in the Task-25 games).
4. **The mirror anomaly is gone for this line**: 0 exact ties, 0 exact ±50 and only 6/117 games
   (5.1 %) within ±60 coins, with a 0 % mirror share — versus 10.9–15.9 % within ±60 for the
   predecessor lines. Our layers do break the mirror cluster decisively.
5. **Field drift dominates everything else.** comp_straw's early half: 79.3 % wins against opponents
   averaging **2,180**; its late half: **50.8 %** against opponents averaging **2,635** (+455). The
   composite falls from 79.3 % to 34.1 % (2,098 → 2,479). The "remaining problem" is largely that the
   line now plays at its own level.
6. **Answer to the human's question:** the largest *market-side* candidate is a late-window **wheat
   liquidation** variant (estimated, not measured: +150…+400 coins/game ≈ +22…+58 points), but the
   dominant diagnosed leak is the **wheat→milk feed-conversion path**, which is an
   **economy-simulation** family, not a market-order one. And the ceiling is decisive: **perfectly
   eliminating every remaining close-game deficit is worth only +243 coins/game ≈ +0.24 % of local
   wallet ≈ +35 rating points** — a third of the 107.9 points the top-1 % tier costs.

## 1. Fresh ladder and tier arithmetic

Leaderboard pull 2026-09-22, 9,838 teams (was 9,786).

| ref | content | games | W/L/T | win % | margin mean / median | opp mean rating |
|---|---|---|---|---|---|---|
| **56447790** | comp_straw (tracked, displayed) | 116 | **76/40/0** | **65.5 %** | +4,118 / +276 | **2,405** |
| 56422944 | comp_both | 184 | 113/71/0 | 61.4 % | +2,452 / +128 | 2,368 |
| 56409633 | plain composite | 172 | 94/64/14 | 54.7 % | +3,721 / +298 | 2,293 |

**Our team row: score 2,661.6, rank 296 / 9,838, `submissionDate` 2026-09-22T01:13:54Z (= 56447790).**

| tier | rank | score | distance from 2,661.6 |
|---|---|---|---|
| top 1 % | 98 | **2,769.5** | **+107.9 needed** |
| top 5 % | 491 | **2,580.9** | we are **+80.7 above** it |
| top 10 % | 983 | 2,393.8 | we are +267.8 above it |

So **2,650 (and our 2,661.6) is above the top-5 % cutoff by ~69 (resp. 81) points and below the
top-1 % line by ~120 (resp. 108) points**; the top-1 % line is 2,769.5, held by rank 98. The field's
own cutoffs moved: top-5 % fell 2,609.6 → 2,580.9 while we climbed +175.

**Tier cost on our only ruler** (~145 rating points per +1 % of local wallet; single anchor, heavily
confounded — see §5): the next tier costs **+107.9 points ≈ +0.74 % of local wallet ≈ +740
coins/game** (against a base wallet of ~99,200). For scale: the *entire* cumulative measured value of
our three layers is `comp_both` +324…+590 and `comp_straw` +416/+390 ≈ **+740–980**. **The next tier
costs another full layer-stack's worth of local edge.**

## 2. Current-games cause table vs the two earlier ones

Refs differ between windows (Task-23/25 samples are `comp_both` games, Task-26 is `comp_straw`), so
build and time are confounded; this is a re-validation of the *diagnosis*, not a controlled A/B.

| | **Task-23 sample** (comp_both) | **Task-25 games** (comp_both) | **Task-26 current** (comp_straw) |
|---|---|---|---|
| attributed games (L / near / W) | 9 / 10 / 42 | 6 / 8 / 23 | **22 / 18 / 59** |
| bank-reproduction gate | 61/61 | 37/37 | **99/99** |
| deficit opens | day 13→14 (ahead until then) | behind from day 2–3 | **day 3 (−70 plateau)** |
| losses vs wins distinct from | ~day 10 | ~day 10 | **~day 17** |
| share of deficit after day 13 | ~100 % | ~92 % | **~90 %** |
| leading loss-specific item | STRAWBERRY −2,269 (volume-led) | WHEAT −593 (volume-led) | **WHEAT −603 (volume-led)** |
| strawberry: units me / opp | 246.3 / 250.9 | 246.0 / 246.0 | **246.5 / 247.6** |
| strawberry: price me / opp | 96.4 / 97.4 | 118.9 / 120.0 | **126.3 / 126.0** |
| strawberry: loss / win | −2,168 / +101 | −319 / +234 | **−163 / +758** |
| mirror share (selected games) | 0/61 = 0 % | 1/37 = 2.7 % | **0/99 = 0 %** |
| exact ties / ±50 (population) | 0 / 0 of 82 | 0 / 1 of 119 | **0 / 0 of 117** |
| \|margin\| ≤ 60 share | 11.0 % | 11.8 % | **5.1 %** |

Full item table for the current games (net of buys, mean per game):

| item | losses | near | wins | loss − win | volume / price in close games |
|---|---|---|---|---|---|
| **WHEAT** | **−683** | −60 | −80 | **−603** | u 577.9 vs 749.1 → volume **−6,662**, price −59 |
| WOOL | −176 | −38 | +292 | −468 | u 169.4 vs 168.5 → volume +99, **price −208** |
| **STRAWBERRY** | −163 | −27 | **+758** | −921 | u 246.5 vs 247.6 → volume −148, price **+77** |
| MILK | +30 | −52 | +315 | −284 | — |
| EGG | −80 | −36 | −116 | +35 | — |
| CARROT | +230 | +3 | −117 | +347 | — |
| TOMATO | +162 | 0 | −130 | +292 | — |
| FERTILIZER | +122 | +21 | +37 | +85 | — |

**New relative to both earlier tables:** (i) strawberry is no longer a leak under any measure — it is
the biggest *win-side* contributor and its realised price is the highest measured; (ii) **wheat is
negative in every class** (−683 losses, −60 near, −80 wins), i.e. a constant drag rather than a
loss-only leak; (iii) carrot and tomato are now *positive* for us in losses (they were the
composite's leading new losses in Task 25), so the bulk-crop story is not uniform — only wheat is.
No new opponent archetype appeared; the field change is strength, not type.

## 3. Are our three layers still earning their place?

| layer | what it acts on | current evidence | verdict |
|---|---|---|---|
| **race** (lockstep sell-layout search) | reorders SELL lots when ≥ 2 are present | **multi-SELL steps 66.7/game** (56 in the Task-23 sample), SELL steps 278/game; `race_errors = 0` in the duels | **still firing**; its measured marginal value stays +112/+64 (small but positive) |
| **wool forward** | sells wool stock as it appears | **WOOL-SELL steps 60.3/game**, 167 wool units/game, wool item net +292 in wins / −176 in losses, price −208 in close games | **still firing**; it trades ~1.3 coins/unit of price for volume (net ≈ −110 in close games, positive in wins) |
| **strawberry (day 13+)** | tops up strawberry sales to the town drain cap | unit parity with the opponent (246.5 vs 247.6), realised price **126.3** (best measured), item net **+758 in wins** vs −163 in losses | **firing, but its target deficit no longer exists** — the volume leak went to zero in the Task-25 games and has stayed there. Its *mechanism* is consistent with the high realised price, but its **marginal value cannot be argued from the current leaks and must be re-measured on fresh seeds**; the last measurement (+416/+390, t = 5.06/5.91) predates this field. |

So: no layer is inert (all three still issue orders), but **the strawberry layer's target quantity has
vanished** and its case now rests on a stale duel. That is the plain statement the human asked for.

## 4. Largest reachable next gain, and its family

**Largest *market-side* candidate: a late-window WHEAT liquidation layer** (the same outermost forward
mechanism, `forward_items=["WHEAT"]` inside a day-13+ window, drain-capped, plus the existing
`forward_min_price` guard). Rationale: wheat is the only item negative in every outcome class, and in
close games we sell 23 % fewer wheat units than the opponent (577.9 vs 749.1).
**Estimated size: +150…+400 coins/game (+0.15…0.4 % ≈ +22…+58 rating points), not measured.**
**Risk, measured previously:** wheat is the feed input; the forward family measured **negative** on
every non-wool item we tried (milk −290/−345, carrot −279/−469), and in these very games our losses
already show **milk −284 loss-minus-win** — selling feed wheat to chase the wheat line is exactly the
trade that can cost the milk line. This is a market-side family, but with a real cannibalisation risk.

**Largest *diagnosed* leak: the wheat→milk feed-conversion path.** In losses, wheat is −683 *and* milk
is only +30, while in wins milk is +315 — i.e. the wheat we withhold from the market is not converting
into milk at the opponents' rate. That is an **economy-simulation** problem (`_ca_*`/`_cs_*`-style
yield/feed modelling, `_hd2_*`-style demand handling), the family we have repeatedly failed to
reimplement, and where the whole-foreign-composite edges of +778…+4,407 live.

**Pre-registered go/no-go for the wheat variant** (build it, then judge it only on this):
```
.venv/bin/python scripts/build_composite_layers.py --variant comp_wheat_late   # to be added
# IS  seeds 9500-9529 (60 games)   vs data/composite/comp_straw/main.py
# OOS seeds 9600-9629 (60 games)   vs data/composite/comp_straw/main.py
GO  iff  delta > 0 AND t >= 3 on BOTH panels AND delta >= +300
        (i.e. >= +0.3 % of wallet, enough to be worth a submission slot)
NO-GO otherwise.  Control: the same source with the item gate off must give delta exactly 0.
```
Both seed panels are unused in every earlier round, so this is a clean test of both the mechanism and
the field change.

## 5. Tier arithmetic, honestly

* Next tier (top 1 %, rank 98) = **2,769.5**; we are at **2,661.6** → **+107.9 points**.
* On the ruler **≈ 145 points per +1 % of local wallet** (anchored once: ref 56409622 at 1,877.8 vs
  56409633 at 2,487.7, same submission minute, +4.2 % local paired wallet gap → 609.9/4.2), that is
  **+0.74 % of local wallet ≈ +740 coins/game**.
* **Upper bound on everything we have diagnosed:** perfectly eliminating *every* remaining close-game
  deficit (all 22 losses + 18 near-losses, i.e. giving each a matching surplus) is **+24,030 coins over
  99 games = +243 coins/game = +0.24 % of wallet ≈ +35 rating points**. Even that perfect, physically
  implausible fix covers **about a third of the next tier**.
* **Confounds, plainly:** the ruler is a single anchor with no replication; the two anchored refs faced
  different opponent pools (mean 1,897 vs 2,283); the displayed score is the tracked submission's live
  rating, needs hours to converge and has wobbled ±5 % in our own measurements; and the cutoffs
  themselves move (top-5 % fell 28.7 points in a day while our score rose 175). Treat 145 pts/% as an
  order-of-magnitude ruler, not a conversion.

**Therefore:** the current replays say the remaining *market-side* headroom on this line is small
(a few hundred coins/game, of which we have already banked the strawberry part) and the next tier is
gated by the **economy-simulation families**, not by another market-order layer. Recommendation: build
and pre-register the wheat-late variant as above (cheap, one builder entry), but do not expect it to
close a 108-point tier on its own; the honest next-tier play is a deliberate attempt at the
feed→milk/yield simulation family, which is a larger project than a single round.

## 6. Artifacts

| file | content |
|---|---|
| `data/episodes-56447790-raw.json` | 117 current episodes |
| `data/replay-manifest-t26.json` | 99-game selection (all losses + near ≤ 500 + matched win control) |
| `data/replays-t26/*.json` | 99 replays |
| `data/replay-attr-straw-t26.json` | attribution: day gaps, exact item execution, verbs, layer signature (99/99 gated) |
| `scripts/replay_compare_t25.py` (`T26_ONLY=comp_straw`) | the three-window comparison table |
| `log/compare-t26.log` | full comparison output |
