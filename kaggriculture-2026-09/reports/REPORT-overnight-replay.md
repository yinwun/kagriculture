# Overnight re-validation (Task 25) — does the Task-23/24 diagnosis still hold?

Date: 2026-09-21/22. Re-validated on the games that arrived after the Task-23 snapshot, with the same
instruments and the same discipline (bank-reproduction gate, shift = 1). **Nothing was submitted; no
live file was modified.**

## 0. Headline

1. **Fresh ladder: our row is 2,486.5, rank 852 / 9,786** — i.e. ref 56422944 has **not passed
   56409633's 2,487.7**; it is **1.2 points short** (it climbed +12.2 from 2,474.3). We are ~50 points
   *inside* the top-10 % cutoff and ~123 points short of top-5 %.
2. **The late-game framing survives, but the item attribution changed.** In the new line's new losses,
   **92 % of the final deficit still accrues after day 13** (−70 at day 13 → −933 at day 29), and losses
   remain indistinguishable from wins until ~day 10. What changed is *which item* carries it: the
   **strawberry volume leak has closed** (246.0 units sold vs the opponent's 246.0 — the volume effect
   is exactly 0, all that is left is a ~1 coin/unit price gap), and the leading loss-specific item is
   now **WHEAT** (−593), where we sell **478.8 units vs the opponent's 729.1** in close games.
3. **The mirror share grew, as predicted.** Among the selected games, mirrors went from 18.7 % to
   **25.0 %** for the composite and 0 % to 2.7 % for the new line; population-wide, exact ties went
   from 6/119 (5.0 %) to **12/164 (7.3 %)** and |margin| ≤ 60 from 10.9 % to **15.9 %**. The new line
   recorded its first exact −50.
4. **`comp_straw` still targets a real but shrunken leak.** Its target quantity (the strawberry volume
   deficit) is now ≈ 0 in the new games, so the +416/+390 (t ≥ 5) measured on last night's seeds
   should be treated as an **upper bound on a shrinking edge**, not a live expectation. The new
   dominant leak (bulk-crop volume: wheat, carrot, tomato) is **not** touched by it.
5. **Go/no-go: NO-GO on submitting `comp_straw` now** — the measured edge (~+0.4 % wallet ≈ +60 rating
   points on the only ruler we have) does not cross the next cutoff, its targeted leak has shrunk on
   the fresh games, and submitting would drop the 2,487.7 line out of tracking and reset our display
   floor for hours. Condition that would flip it: a fresh-seed re-measure of `comp_straw` (and of a
   bulk-crop-volume variant) still ≥ +300 with t ≥ 3.

## 1. Fresh ladder state

Leaderboard pull 2026-09-21/22, 9,786 teams (was 9,734).

| ref | content | games | W/L/T | win % | margin mean / median | opp mean rating |
|---|---|---|---|---|---|---|
| **56422944** | comp_both (tracked, displayed) | 118 | **85/33/0** | **72.0 %** | +4,194 / +399 | **2,322** |
| 56409633 | plain composite | 163 | 93/58/12 | 57.1 % | +3,927 / +353 | 2,325 |
| 56409622 | our own stack | 88 | 48/40/0 | 54.5 % | +4,860 / +126 | 1,916 |

Task-23 comparison: new line 76.5 % → **72.0 %**, composite 66.9 % → **57.1 %**; opponent mean rating
2,243 → **2,322** and 2,283 → **2,325** (the field inflated ~+50–80 points, which is what moved the
medal line), while the composite's tie count doubled (6 → 12).

Cutoffs from the same pull (rank: score): top 1 % = rank 97: **2,793.0**; top 5 % = rank 489:
**2,609.6**; **top 10 % = rank 978: 2,436.9**; top 20 % = rank 1,957: 1,852.8. Top three: DSM 3,139.9,
Majkel1337 3,082.5, Vadim Vasilenko 3,079.8.

**56422944 vs 2,487.7: not passed — 2,486.5, 1.2 points short** (effectively level). Our position:
**rank 852, comfortably inside the top 10 % (2,436.9) and 123.1 points short of the top-5 % cutoff
(2,609.6)**. Note the quoted "bronze ≈ 2,650" does not match the fresh pull's top-10 % cutoff
(2,436.9); 2,650 sits between our top-5 % (2,609.6) and top-1 % (2,793.0) cutoffs, so if that figure is
the target we are ~163 points short of it, and ~123 points short of top-5 %.

## 2. New games vs the old sample (same instruments, same gate)

New games: composite **45** (after 2026-09-21T13:30:59Z; 164 total), new line **37** (after
13:27:31Z; 119 total). Selection rule unchanged: all losses + near-losses (≤500) + a rating-matched win
control → 44 and 37 replays, **81/81 pass the bank-reproduction gate**.

| window | attributed games (L / near / W) | day the deficit opens | leading loss-specific item | strawberry loss − win | mirror share |
|---|---|---|---|---|---|
| **new line, OLD sample** | 9 / 10 / 42 | day 13→14 (flat +/− until then) | STRAWBERRY **−2,269** | **−2,269** | 0/61 = 0 % |
| **new line, NEW games** | 6 / 8 / 23 | behind from **day 2–3**, 92 % of the deficit after day 13 | **WHEAT −593** | **−554** | 1/37 = **2.7 %** |
| **composite, OLD sample** | 12 / 21 / 42 | day 13→14 | STRAWBERRY/MILK/WHEAT | −762 | 14/75 = 18.7 % |
| **composite, NEW games** | 5 / 20 / 19 | day 13→14 (d13 +791 → d14 −541 → d29 −5,942) | **TOMATO −4,812, CARROT −2,805, MILK −1,052** | **+1,882** (inverted) | 11/44 = **25.0 %** |

**Day trajectories (mean liquid gap, me − opp).** New line, new games: losses `d0 +5, d2 −15, d3 −45,
d7 −42, d10 −55, d13 −70, d14 −135, d19 −126, d24 −506, d29 −933`; wins `d0 +3, d3 −27, d7 −22, d10 −51,
d13 +192, d19 −77, d24 +504, d29 +930`. So (i) losses and wins are still indistinguishable until
~day 10 (both ≈ −50), (ii) the new losses are *also* mildly behind from day 2–3 — the old sample's
losses were *ahead* until day 13 — but (iii) **~92 % of the new-loss deficit still accrues after day
13**, and the composite's new losses still show the clean d13→14 turn. The late-game conclusion is
therefore intact; the *early* part is new.

**Item attribution, new line, new games** (net of buys, mean per game):

| item | loss | near | win | loss − win | volume / price split (losses+near) |
|---|---|---|---|---|---|
| **WHEAT** | −583 | +47 | +10 | **−593** | u 478.8 vs 729.1 → gross volume **−9,674**, price −242 |
| STRAWBERRY | −319 | −268 | +234 | −554 | u 246.0 vs 246.0 → volume **0**, price **−274** |
| WOOL | −75 | −19 | +218 | −293 | u 130.9 vs 130.8 → volume +7, price −35 |
| MILK | −56 | +33 | +222 | −278 | u 200 vs 198 → volume +141, price −168 |
| CARROT | −96 | +14 | +144 | −240 | — |

So the strawberry leak has changed *shape*: it was **volume-led** (−825 vol / −270 price) and is now
**price-only** (0 vol / −274 price) — our strawberry unit count is now exactly the opponent's. The
dominant new leak is a **bulk-crop volume shortfall**: we sell ~250 fewer wheat units (and fewer
carrots, and in the composite's new losses far fewer tomatoes: 9.6 vs 21.2 units) than the opponents
we lose to, while our revenue per unit is essentially identical (wheat 38.5 vs 38.9).

**New cause not in the old table:** bulk-crop (wheat/carrot/tomato) *volume* shortfall. The old table
had strawberry (volume), wheat (feed-vs-sell), milk (price) and layout/timing; the tomato/carrot
volume gap in the composite's new losses (n = 5, so read it as a lead, not a finding) and the wheat
volume gap for both lines are new entries.

**Opponent field / mirror change (quantified).** Composite: mirrors 18.7 % → **25.0 %** of selected
games, exact ties 5.0 % → **7.3 %** of the population, |margin| ≤ 60 10.9 % → **15.9 %**. New line:
mirrors 0 % → **2.7 %**, its first exact −50 loss appeared (14 of its 119 games now land within
±60 coins, 11.8 %). Opponent mean rating: +79 (new line) and +42 (composite). This is exactly the
predicted effect of more players running the public blob, and it means the −50/tie anomaly now covers a
*larger* share of games than when Task 24 priced it.

## 3. Does `comp_straw` still cover them?

The layer's target is the late-game **strawberry volume** deficit: it tops up strawberry sales to the
town's drain cap from day 13 (measured last round as +89 extra orders/game, +416 IS / +390 OOS with
t = 5.06 / 5.91 vs `comp_both`). On the fresh games:

* **The target quantity has mostly gone.** In the new close games we sell **246.0** strawberry units
  against the opponent's **246.0** — the volume effect is exactly zero, and the remaining strawberry
  gap is a ~1.1 coin/unit price difference (−274 total). A top-up layer can only add units we still
  hold unsold; with unit parity there is little headroom left in these games.
* **The shape changed from volume to price.** The layer cannot fix a price gap — that is the race
  layer's/sale-timing domain, and our measured price effects there are −175…−270 (Task 23) and its
  own marginal value is +112/+64 (Task 22).
* **The new dominant leak is not targeted at all.** Wheat (and carrot/tomato) volume shortfalls are
  bulk-crop issues; `comp_straw` sells strawberries only.
* **The +89 top-ups/game figure does not transfer as a value claim.** It was measured against last
  night's seeds; it should be re-measured on fresh seeds (e.g. 9300–9329) before it is used to justify
  a submission. The mechanism is not refuted — the drain-capped strawberry sale is still sound — but
  its *coverage of the current losses* is materially smaller.

Cheap follow-up I did not have budget for this round: a wheat/bulk-volume variant (the same outermost
forward mechanism with `forward_items=["WHEAT"]` inside a late window, plus the carrot/tomato case
measured separately) duelled against `comp_both` on fresh seeds.

## 4. Go / no-go on submitting `comp_straw`

**NO-GO now.** Reasons, in order of weight:

1. **The expected gain does not cross a cutoff.** +0.42 % wallet ≈ **+61 rating points** on our only
   (single-anchor, heavily confounded) ruler of ~145 points per +1 %. That would move ~2,486 → ~2,547:
   still below the top-5 % cutoff (2,609.6) and well inside the top-10 % zone we already occupy (rank
   852 vs cutoff 978). It buys margin, not a medal step.
2. **Its targeted leak shrank on the fresh games** (strawberry volume deficit → 0), so the measured
   +416/+390 is an upper bound that the new data does not support extrapolating.
3. **The substitution cost is real and measured.** Only the latest two submissions are tracked and the
   display carries the better live one; submitting `comp_straw` drops **56409633 (2,487.7)** out of
   tracking and replaces our display floor with a fresh line that must climb for hours (our own
   measurement: convergence takes hours and the displayed score wobbles ±5 %). Trading a converged
   2,486.5/2,487.7 pair for one fresh line of unknown convergence, to gain ~60 points that do not cross
   a cutoff, is not supported by the evidence.
4. **The field is inflating faster than our edge** (+42…+79 opponent rating points overnight; the
   composite's win rate fell 66.9 % → 57.1 %). A +0.4 % local edge is smaller than that drift.

**Condition that would flip this to GO:** re-measure `comp_straw` on a fresh, unused seed panel
(9300–9329 IS + 9400–9429 OOS) and find Δ > 0 with **t ≥ 3 on both panels** *and* Δ ≥ ~+300 (i.e. the
edge survived the field change); ideally alongside a bulk-volume (wheat) variant that targets the new
dominant leak. If both land, submit the stronger one — the tracking reset is then buying a real step
rather than a rounding error.

## 5. Artifacts

| file | content |
|---|---|
| `data/episodes-{56409633,56422944}-raw-t23.json` | the frozen Task-23 episode snapshots (old window) |
| `data/replay-manifest-t25.json` (+ per-ref files) | new-games selection (`--since` on endTime) |
| `data/replays-t25/*.json` | 81 new replays (all fetched) |
| `data/replay-attr-{newline,composite}-t25.json` | new-games attribution (37 and 44 games, all bank-gated) |
| `scripts/replay_compare_t25.py`, `data/replay-compare-t25.json`, `log/compare-t25.log` | old-vs-new tables, day trajectories, item splits, mirror shares |
| `scripts/replay_manifest.py` | added the `--since` window filter |
