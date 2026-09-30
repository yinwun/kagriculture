# Upside: the −50/tie anomaly, the late-game strawberry layer, and the gap estimate (Task 24)

Date: 2026-09-21. Three items: the exact-−50 / tie anomaly (first half), the late-game strawberry
liquidation layer (built and duelled), and the rating-per-percent estimate. **Nothing was submitted;
no live file was modified.**

## 0. Headline

1. **The 12 anomaly games are mirror matches against other teams running the same public tape — and
   there is no tie-break rule to win.** Reward is `money` only (`s.reward = farms[p]["money"]`, engine
   line 963), so an exact tie is a true money tie. In all 12 games the two seats played **identical
   farmer/hands actions on 719–720 of 720 steps** and identical market lists on **716–720 of 720**
   steps (the six exact ties are perfect 720/720 mirrors with zero ledger difference; the six −50
   games differ on exactly 4 market steps), against **12 different opponent teams**.
2. **The −50 is a one-unit wheat divergence fixed in the first steps by the lockstep seat-order
   asymmetry — not an end-game effect.** Over the 12 games the complete ledger difference is
   `SELL WHEAT −186` (−31 each), `BUY_PRODUCT WHEAT −174` (−29 each), `BUY_SEED WHEAT +60` (+10 each)
   = exactly −50 per game; the divergence is visible at **step 1** (one seat buys an extra WHEAT seed)
   and persists. **The final day's net cash flow is identical for both seats** (+9,114/+9,114 and
   +9,809/+9,809 and +9,016/+9,016 in the games inspected), so **a 50-coin last-step adjustment cannot
   flip them** — the human's cheapest-win hypothesis fails on the mechanism, not the arithmetic.
3. Arithmetic if they were flipped (composite population): **+9.6 pp win rate** (66.9 % → 76.5 %,
   91/119) and **+5 coins** mean margin. On a wallet ruler that is ~0; it matters only if the ladder
   rating is win/loss-driven — which we have not measured.
4. **The strawberry layer works: +416 (t = +5.06, 51/9) IS and +390 (t = +5.91, 51/9) OOS**, pooled
   +403 (t = +7.70, 53/60 seeds positive), i.e. **+0.42 % of wallet** on top of `comp_both`. Adding
   milk inside the same window *reduces* the gain (+375/+319), consistent with the earlier negative
   milk evidence — `comp_straw` (WOOL + STRAWBERRY from day 13) is the recommendation.
5. **Identified leaks cover roughly a third to a half of the ~165–175 point gap** on the only ruler we
   have (~145 rating points per +1 % local wallet, single anchor, heavily confounded): ≈ +60 points
   from the measured strawberry layer, ≈ +35 more if the live line's six ≤60-coin mirror losses were
   won. **The rest needs the economy-simulation families we cannot reimplement.**

## 1. The exact-−50 / tie anomaly (priority item)

**Taxonomy.** 56409633: 119 games, 79 W / 33 L / 6 T; the 12 anomaly games (6 × 0, 6 × −50) are
**10.1 %** of its population. Seat split: ties 4 in seat 0 / 2 in seat 1; −50 4 in seat 0 / 2 in
seat 1 — so it is not "the second seat always loses". The new line (56422944) has **no** exact 0 or
−50 in 82 games.

**What they are.** Every anomaly game is a *mirror*: the two seats' recorded farmer/hands actions are
identical on **719–720 of 720** steps and their market lists identical on **716–720 of 720** steps
(the six ties are perfect 720/720 mirrors with an empty ledger difference; the six −50 games differ on
exactly 4 market steps). The 12 opponents
are 12 distinct teams (`Toru59er`, `Sophinator`, `darasty`, `Pelican`, `tanadai`, `xxxzzz…`, …). Since
the composite's route blob is a public artifact (Task 20: the same `54fe156ea7206e38` blob ships in
≥ 5 public notebooks), these are **other teams running the identical tape** — 10 % of the composite's
ladder games are near-exact mirrors, and the outcome is decided by a ±50-coin asymmetry.

**The mechanism (measured ledger, `scripts/anomaly_50.py`).** Rebuilding each game with the recorded
actions (shift = 1, all 12 pass the bank-reproduction gate) and logging every money-moving event per
seat gives an identical aggregate difference in all six −50 games:

| ledger line | per game (me − opp) | why |
|---|---|---|
| `MKT:SELL:WHEAT` | **−31** | one contested wheat unit lands on the other side |
| `MKT:BUY_PRODUCT:WHEAT` | **−29** | wheat bought back marginally dearer |
| `MKT:BUY_SEED:WHEAT` | **+10** | we bought one wheat seed fewer |
| **net** | **−50** | exactly the reward margin |

The divergence starts at **step 1**: in episode 111566191 (seat 0, vs Pelican) the two seats differ on
only 4 market steps, the first being step 1 where seat 1 requests `BUY_SEED WHEAT 1` and seat 0 does
not; the wheat sell quantities then differ by one unit (step 58: 2 vs 0; step 80: 3 vs 2; step 81: 0 vs
1). That is the **lockstep seat-order asymmetry** we documented in Task 1: both seats are quoted the
same pre-commit price, but seat 0 commits first, so the last contested unit of the turn is cleared on
different sides (and $1 sales add no supply, so the walk differs). One unit at step 1 propagates to a
50-coin difference 718 steps later while the daily cash flows stay identical.

**Verdict on the three sub-questions.** (i) Tie-break rule: **none** — reward is money; a tie needs
+1 coin. (ii) Decided by a specific last-step action: **no** — the final day is symmetric; the 50 coins
are lost at the start. (iii) Quantified impact if flipped: +9.6 pp win rate, +5 coins mean margin on
the composite; for the live line, flipping its six ≤60-coin losses (its ≤60-coin band is currently
**3 W / 6 L**) would give 68/82 = 82.9 % (+6.5 pp) and ≈ +240 coins ≈ +0.24 % wallet.

**Actionable direction (not measured this round).** Because the deficit is a single wheat unit decided
by commit order, the exploitable change is a **wheat round-trip correction in mirror-like states** — do
not take the marginal wheat seed purchase when budget/shed is on the edge, and make sure we are the
side that sells the contested final unit (the trick our forward layer already performs for WOOL,
applied to WHEAT only when the opponent's stream looks identical). An end-game patch is ruled out by
the measurement above; this is an early-game unit-level edge.

## 2. The late-game strawberry liquidation layer (built, measured)

Implementation: the outermost forward layer already on the composite, extended with a **per-item start
gate** (`forward_start_by_item`) so that `STRAWBERRY` is topped up to the town's drain cap only from
**day 13 (step 312)** while `WOOL` behaviour is byte-for-byte unchanged. Variants built from the
composite + race base by `scripts/build_composite_layers.py`:

| variant | content | sha256 (main.py) |
|---|---|---|
| `comp_both` (base) | composite + race + WOOL forward | `0a7a2070a25e0cb6afe769e8836d0b6192fb5ac9cff21267f5776dbcac2a864d` |
| **`comp_straw`** | + STRAWBERRY from day 13 | **`ad2ddf2d60df5670478f653e912c4f67be80f3c7084388f03760f2497f8befd8`** |
| `comp_straw_milk` | + STRAWBERRY and MILK from day 13 | `a9c06630aa83854743b6a21c4139d3291f81e808d0d5289cd7e3bb9040c25fd9` |
| `comp_both_ctl` | same source, no per-item gate (control) | `beda4297018f82894946f887225be16b39c32cc909b614d2faf28fa8d5ca2b48` |

All duels vs **`comp_both`**, paired, seats alternating, 60 games per panel:

| candidate | panel | Δ wallet | Δ % | t | W–L | cand wallet | base wallet | positive seeds |
|---|---|---|---|---|---|---|---|---|
| **comp_straw** | IS 9000–9029 | **+416** | +0.42 % | **+5.06** | **51–9** | 99,608 | 99,193 | 26/30 |
| **comp_straw** | OOS 9100–9129 | **+390** | +0.41 % | **+5.91** | **51–9** | 94,484 | 94,094 | 27/30 |
| **comp_straw** | **pooled** | **+403** | +0.42 % | **+7.70** | 102–18 | — | — | **53/60** |
| comp_straw_milk | IS | +375 | +0.38 % | +4.21 | 46–14 | 99,412 | 99,037 | 24/30 |
| comp_straw_milk | OOS | +319 | +0.34 % | +3.74 | 49–11 | 94,134 | 93,814 | 25/30 |

**Both panels clear the pre-registered bar (Δ > 0, t ≥ 3)** — this is the first build this session to do
so against a composite base. Per-seed spread (comp_straw IS): min −781, median +364, max +1,313.

**Did the layer fire?** Yes, and only on the market side: `forward_orders` 9,394 (cand) vs 4,027 (base)
over the 60 IS games = **+5,367 ≈ +89 orders/game** of strawberry top-ups (`forward_units` 9,808 vs
4,027). Worker-verb action mix is identical; idle share 7.81 % vs 7.81 %.

**Counters and runtime.** `layer_fallbacks = entry_fallbacks = race_errors = 0` on both seats of all
four duels; **0 agent exceptions**; 0 non-`DONE` episodes. Per-step (1,438 calls/game, `actTimeout = 1 s`):
mean 0.7 ms, p95 1.5 ms, p99 2.8 ms, **max 49.3 ms**, zero steps over 250 ms — 1.02× the mean of
`comp_both`, ~20× headroom at the worst step.

**Control.** `comp_both_ctl` (same layer source with the per-item gate absent) vs `comp_both`: **Δ
exactly +0** on 20 games with identical wallets, and the only textual difference between the two files
is the three added gate lines. One honest wrinkle: two diagnostics counters came out 2 apart
(`race_tried` 7,415 vs 7,417 over 20 games) while every game outcome was identical to the coin — a
counter bookkeeping asymmetry, not a behavioural difference.

**Cumulative local position.** vs the plain composite (IS): `comp_both` +324 (Task 22) + `comp_straw`
marginal +416 = **+740 ≈ +0.74 % of wallet**.

Package (not submitted): `data/submits/submission-composite-straw.tar.gz`, payload sha256
`ad2ddf2d…` (identical to `data/composite/comp_straw/main.py`), tarball sha256 `b74a8eab61ed890e…`.
Rebuild: `.venv/bin/python scripts/build_composite_layers.py --variant comp_straw`.

## 3. The estimate the human asked for

**Anchor (single, same cohort).** Ref **56409622** (our stack) displayed **1,877.8**; ref **56409633**
(the plain composite) displayed **2,487.7**; both submitted in the same minute (their first ladder
games are 00:54:56Z and 00:57:35Z); the local paired wallet gap between them is **+4.2 %** (Task 21:
+4,119 = +4.17 % of the base wallet, 60 towns, t ≈ +6).

**Ruler.** 609.9 rating points / 4.2 % of wallet = **≈ 145 rating points per +1 % of local wallet**
(≈ 1.45 points per 0.01 %). Second ruler from the same anchor's win rates (66.9 % vs 55.8 %,
+11.1 pp ↔ 609.9) = **≈ 55 points per pp of win rate**.

**Confounds (plainly).** This is **n = 1** with no replication; the two refs faced **different
opponent pools** (mean opponent rating 2,283 vs 1,897) and the displayed score is the *currently
tracked* submission's live rating, which needs hours to converge and has wobbled ±5 % in our own
measurements; the two lines differ in far more than wallet; and the two ratings were read at different
ages. Treat both rulers as order-of-magnitude, not as conversions. **No monotone local-wallet →
ladder-rating map has ever been measured.**

**Coverage of the gap** (bronze line ≈ 2,650 vs our 2,474.3 = **175.7 points**; vs 2,487.7 = 162.3):

| item | wallet effect (measured) | rating on the 145 pts/% ruler | share of 175.7 |
|---|---|---|---|
| late-game strawberry liquidation (`comp_straw`, **measured**) | **+0.42 %** | **≈ +61** | **≈ 35 %** |
| winning the live line's six ≤60-coin mirror losses | +0.24 % | ≈ +35 | ≈ 20 % |
| the −50/tie anomaly on the composite's population | +5 coins/game (≈ +0.005 %) | ≈ +1 (but +9.6 pp win rate, which the *other* ruler would price at ≈ +530 — implausibly large, so I do not claim it) | ≈ 0 |
| milk / broader premium liquidation (tested this round) | **negative** (+375/+319 < +416/+390) | — | — |
| market layout/timing on milk+wool | already inside the live line (+324…+590 shipped) | already counted | — |
| **total identified and reachable** | **≈ +0.66 %** | **≈ +95** | **≈ 55 %** |

**Answer.** The identified leaks cover **roughly a third to a half of the ~165–175 point gap** — about
**+60 points measured and shipped-able today** (the strawberry layer, t = +5.06/+5.91 on two independent
panels) and up to **+95 points** if the mirror unit-level wheat correction also lands. **The remainder
needs the economy-simulation families we cannot reimplement** (`_hd2_*` shop-demand rewriting,
`_ca_*`/`_cs_*` yield simulation, `_v92_p_*` sale forecasting): our own reachable layer families
measure at hundreds of coins per town, while whole foreign composites measure at +778…+4,407 against
our builds — and every attempt we have made at those modelling-heavy families measured ≤ 0.

## 4. Artifacts

| file | content |
|---|---|
| `scripts/anomaly_50.py`, `data/anomaly-50.json` | per-game ledgers, mirror detection, differing market steps |
| `scripts/build_composite_layers.py` | per-item start gate; `comp_straw`, `comp_straw_milk`, `comp_both_ctl` |
| `data/composite/duel-straw-{is,oos}.json`, `duel-strawmilk-{is,oos}.json`, `duel-t24-control.json` | the duels (per-seed deltas, counters, exceptions) |
| `data/composite/timing-t24.json` | per-step runtime |
| `data/submits/submission-composite-straw.tar.gz` | packaged `comp_straw` (not submitted) |
