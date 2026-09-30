# One more layer? (Task 35) — fresh attribution on the new base + frontier sweep

Date: 2026-09-26/27. Measurement only. **No submission; no live file touched.** Target: lift the
current best (ref **56533839** = `the-shepherds-ledger-herd-safe-sovereign` + our three market layers,
277 games, equilibrium ≈ 2,400–2,500) to a **2,650-level** line, which needs **+1.5–2 % of local
wallet ≈ +250 rating points** on our ruler (~145 pts per +1 %).

## 0. Hard verdict

**No. 2,650 is not reachable on this base with anything we can build.** The reachable market-side
channel (realised price on wool + strawberry) is worth at most **≈ +0.6 % wallet ≈ +85 points at a
perfect-fix bound** and ~0 in practice; every other channel in the attribution is input- or
production-side (our own measurements: wheat −516/−762, fertilizer −299/−315, milk −290/−345,
carrot −279/−469); and the public frontier sweep returned **zero winners on two fresh panels** — all
five runnable candidates lose to `shep_straw`, the best of them being the *base without our layers*
(−662/−592, which simply re-measures our layers' contribution).

## 1. Per-item attribution on the current base (ref 56533839)

Method: the last 59 games of 56533839 (`--since 2026-09-26T10:52:56Z`), 57 replays fetched and
**57/57 bank-reproduction gated at shift = 1**; 24 losses, 10 near-losses, 23 wins. Values are net of
that item's purchases (`rev − spend`, me − opponent), mean per game.

| item | loss net | near net | win net | **loss − win** | u_me / u_opp | p_me / p_opp | volume effect | **price effect** |
|---|---|---|---|---|---|---|---|---|
| **MILK** | **−688** | +17 | +326 | **−1,014** | 209.9 / 213.6 | 91.6 / 92.1 | −338 | −106 |
| **WOOL** | **−587** | −118 | +237 | **−823** | 164.1 / 163.6 | 104.2 / 106.6 | +53 | **−393** |
| **WHEAT** | **−874** | −88 | −170 | **−704** | 609.2 / 655.0 | 38.6 / 38.6 | −1,768 | +38 |
| **STRAWBERRY** | **−304** | +52 | +153 | **−457** | 247.8 / 247.8 | 105.7 / 106.5 | **0** | **−197** |
| TOMATO | −403 | 0 | −138 | −265 | 7.1 / 10.5 | 16.0 / 18.4 | −60 | −21 |
| CARROT | −238 | +8 | +79 | −318 | 124.5 / 126.5 | 44.9 / 45.1 | −90 | −25 |
| EGG | −72 | +16 | −353 | +281 | 75.4 / 75.6 | 38.5 / 38.6 | −7 | −7 |
| FERTILIZER | +88 | −39 | +52 | +36 | 339.2 / 368.9 | 44.6 / 44.7 | −1,326 | −18 |
| MELON | +181 | 0 | +176 | +5 | 72.0 / 71.6 | 198.8 / 198.0 | +70 | +61 |

**Reachable / non-reachable split** (the only mechanism we have is the outermost market layer:
sell timing, lot layout, late-window forwarding — never selling an input we depend on):

* **REACHABLE (price channel):** **WOOL −393** (unit parity 164.1 vs 163.6, pure price) and
  **STRAWBERRY −197** (unit parity exactly 247.8 vs 247.8, pure price). Together **≈ −590/game in
  losses**, i.e. a perfect-fix bound of **+0.6 % wallet ≈ +85 points**. Both are already targeted by
  the race + forward layers that are *in this build*, so the practically reachable increment is the
  measured marginal value of those layers (**+57…64** for race, from the Task-29 ablation), not +85.
* **NOT REACHABLE — inputs:** WHEAT (−874; volume 609 vs 655 units, but the purchase channel offsets
  most of it) and FERTILIZER (volume −1,326 gross yet net **+88** because we buy less). We measured
  what happens when we try to monetise them: wheat **−516/−762**, fertilizer **−299/−315**.
* **NOT REACHABLE — production/economy:** MILK (−688; volume −338 — a feed→milk conversion issue),
  TOMATO/CARROT (small volume gaps; tomato 7.1 vs 10.5 units).
* Nothing here is "hundreds of coins per game in a reachable channel": the reachable channel totals
  ≈ 590 gross, ~0–60 net of what our layers already capture.

## 2. Public frontier sweep (same day)

Newest 40 notebooks pulled; the 16 newest hashed and extracted offline. Provenance: 3 expose our blob
`54fe156ea7206e38` (tetsutani demand-preserving, haideptry shepherds-ledger, haideptry 2965); 1 exposes
the different `5df1c84699004845` payload (the `{base, patches}` action-tape format, routes 0 /
actions 0 — not a route table); the rest expose no payload. Runnable after the 720-step smoke gate:
five candidates.

Duels vs **`data/candidate/shep_straw/main.py`** on fresh panels, paired, seats alternating,
60 games/panel: **IS 10400–10429, OOS 10500–10529**.

| candidate | IS Δ | IS t | OOS Δ | OOS t | exc/err | verdict |
|---|---|---|---|---|---|---|
| guruprasaathas111/kaggriculture-top-2-master-engine-v4 | −1,116 | −4.42 | −1,158 | −10.86 | 0/0 | no-go |
| tetsutani/demand-preserving-turn-sale-timing | −1,189 | −11.88 | −1,064 | −10.84 | 0/0 | no-go |
| **haideptry/the-2965-master-hybrid-engine** | −746 | −2.91 | −649 | −3.63 | 0/0 | no-go |
| **haideptry/the-shepherds-ledger-herd-safe-sovereign (the base alone)** | **−662** | −5.84 | **−592** | −6.41 | 0/0 | no-go (this *is* our layers' value: ~+600) |
| kunaldesale2408/kaggriculture-2026-v1 (the action-tape build) | −5,255 | −8.30 | −5,826 | −10.96 | 0/0 | no-go |

**Bar (Δ > 0 with t ≥ 3 on both panels): no candidate clears it; every candidate is significantly
worse.** No stack was built (the bar was not met), so step 3 of the brief is vacuous.

## 3. Best candidate for "one more layer", and what it is worth

| candidate | coins/game | rating points | clears the bar? |
|---|---|---|---|
| Wool/strawberry **price-channel** layer on this base (the only reachable nomination) | ≤ +590 gross, realistically **0…+60** (the race ablation's +57…+64) | **≈ +85 at the perfect-fix bound; ≈ 0…+9 in practice** | **no** (Task-29 sweep: wool-off already prunes at −248…−282; adding more of the same channel measured ≤ 0) |
| Wheat / fertilizer liquidation | measured **−516/−762**, −299/−315 | negative | no |
| Milk / carrot / tomato / egg late-window variants | measured −44…+110 (all below bar) | ≈ 0 | no |
| Frontier base + our layers | best public base this round is **−592…−662 vs our current stack** | negative | no |

**Needed for 2,650: +1.5–2 % wallet ≈ +250 points. Largest reachable identified: ≈ +85 points at an
ideal bound, ~0–60 in practice — i.e. roughly a third of the requirement at best, and the measured
increments of every concrete variant are ≤ 0.** Three numbers prove it: (i) the reachable
price-channel total in the losses is 590 coins/game gross (wool 393 + strawberry 197) with unit parity
on both items — there is no volume left to move in a channel we can reach; (ii) every input-monetising
variant measured significantly negative (wheat −516/−762, fertilizer −299/−315); (iii) the frontier
sweep's best candidate is our own base minus our layers (−592/−662), i.e. no public build beat us on
two fresh panels.

## 4. What would actually be needed

A +250-point jump needs a channel with **hundreds of coins per game in a reachable mechanism**, and
the attribution says the only large flows left are (a) milk volume (feed→milk conversion) and (b) wheat
and fertilizer allocation — all **economy-simulation** problems (`_ca_*`/`_cs_*` yield/feed modelling,
`_hd2_*`-style demand handling), where the foreign composites measure +778…+4,407 but every attempt of
ours has measured ≤ 0. **That is an S3-scale build, not "one more layer".**

## 5. Artifacts

| file | content |
|---|---|
| `data/replays-t35/`, `data/replay-attr-shep-t35.json` | 57 bank-gated replays of 56533839 and their attribution |
| `data/replay-manifest-t35.json` | selection (last 60 games, all losses + near ≤300 + matched wins) |
| `data/notebooks-t35.csv`, `data/provenance-guard-t35.json` | the frontier list and blob hashes |
| `scripts/t35_frontier.py`, `log/t35-frontier.log` | extraction, smoke gate, duels and the bar check |
| `data/candidate/duel-t35-*.json` | the ten duel cells (per-seed deltas, counters, exceptions) |
| `scripts/t34_equilibrium.py`, `REPORT-closed-period.md` | the equilibrium/window evidence this verdict builds on |
