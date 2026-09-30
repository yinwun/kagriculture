# Closed-period forecast (Task 34) — equilibrium, field trend, basins vs convergence

Date: 2026-09-26. Measurement only. **No submission; no live file touched.** Deadline 2026-09-30,
then games run to ~2026-10-15 with the leaderboard final at the end of that closed period, so the
displayed score today is a transient.

## 0. Bottom line

1. **Our equilibrium estimate is ≈ 2,300–2,400 for the older lines and ≈ 2,600–2,700 for the best one
   (`56533839`)** — measured as the opponent-score band where our win rate crosses 50 %, with wide
   Wilson intervals. Today's display: **2,489.1, rank 338/10,025**.
2. **The field's cutoffs are still decaying ~30–46 points/day** (09-21→09-23: top1 2,811→2,736, top5
   2,617→2,527, top10 2,417→2,340, i.e. −29…−46/day) — a continuation that would put the converged
   top-5 % line far below today's 2,414.8. Our equilibrium sits *above* that projection, so the
   closed period should settle us inside the top 5 % — **if** the decay continues and our equilibrium
   estimate holds.
3. **The evidence favours "one equilibrium plus slow convergence" over "different persistent
   basins"**: every one of our instances shows its win rate decaying monotonically toward ~50 % as the
   matchmaker raises its opponent band (81 %→55 %, 77 %→58 %, 77 %→66 %, 100 %→43/46 %), and the
   same payload seen at 2,276 and 2,642 is consistent with two *phases* of convergence rather than two
   stable levels. The decisive test (two simultaneous instances of the identical payload tracked for
   days) is not available to us and is what remains unmeasured.
4. **Decision implication:** if convergence dominates, the closed period washes out the landing
   lottery and strength dominates — so submitting the strongest measured build at T-3 is the right
   play, and the exact landing matters less than its strength. The 16-day closed period is long
   relative to the convergence timescales we observe (hours-to-days).

## 1. Our side: per-band win rate, Wilson 95 % intervals, equilibrium crossing

Opponent score = the opponent team's current leaderboard score. Ref 56565204 had 0 public episodes at
pull time (+1 during it), so it is not usable yet.

| ref | games | win % | band 0–1500 | 1500–1800 | 1800–2100 | 2100–2400 | 2400–2700 | 2700+ | **crossing** |
|---|---|---|---|---|---|---|---|---|---|
| **56533839** | 172 | 55.8 % | 84.6 % (13) | 100 % (2) | 58.3 % (12) | **59.2 % (49)** | **50.5 % (93)** | 0 % (3) | **≈ 2,600–2,700** |
| 56523821 | 216 | 65.3 % | 88.9 % (18) | 77.6 % (58) | 64.4 % (73) | **53.2 % (47)** | 41.2 % (17) | 33.3 % (3) | **≈ 2,300–2,400** |
| 56496301 | 199 | 57.8 % | 75.0 % (16) | 80.0 % (15) | 61.8 % (68) | **52.2 % (67)** | 43.8 % (32) | 0 % (1) | **≈ 2,300–2,400** |
| 56496292 | 160 | 51.2 % | 80.0 % (15) | 63.0 % (54) | **32.6 % (43)** | 54.5 % (33) | 33.3 % (12) | 0 % (3) | **≈ 1,900–2,100** |

Wilson intervals at the crossing band are wide (e.g. 56533839 at 2400–2700: 50.5 %, CI 40.6–60.5 %;
56523821 at 2100–2400: 53.2 %, CI 39.2–66.7 %), so the crossing point is an estimate with roughly
±150–250 points of uncertainty, not a precise level. Median margins at the crossing band are +12
(56533839), +15 (56523821), +80 (56496301) — knife-edge, exactly what an equilibrium looks like.

**Repeat beaters** (≥ 2 games, negative total margin): DSM (3,033; 2 games, mean **−21,130**), fuxi
(2,740; −9,456), Satoshi Nguyen (2,565; −3,014), hana87hana (2,092; −2,897), Linda Liu (1,747;
−2,542), otouhu (2,568; −2,396), Michał Łapiński (2,390; −2,033), datnt114 (2,563; −1,884). Mostly
higher-rated than us, with two lower-rated exceptions — a small list, so there is no single nemesis.

## 2. Field census and trend

Across every episode file we hold: **1,392 distinct opponent teams, 1,810 distinct opponent
submissions** (≈1.3 submissions per team — the field churns builds continuously), 1,364 with a
current leaderboard score:

| percentile | p10 | p25 | median | p75 | p90 | max |
|---|---|---|---|---|---|---|
| opponent score | 1,447 | 1,684 | 2,020 | 2,335 | 2,501 | 3,033 |

**Only 147 of 1,364 (11 %) of our opponents are currently rated above us** — we are matched mostly
below our own display, which is the mechanism that will pull us up if our equilibrium is above it.

Cutoff trend from our own tracker history (`data/cmp-track.csv`, last sample per day):

| day | teams | our score | our rank | top 1 % | top 5 % | top 10 % | day-over-day |
|---|---|---|---|---|---|---|---|
| 09-21 | 9,732 | 2,480.1 | 842 | 2,811 | 2,617 | 2,417 | — |
| 09-22 | 9,873 | 2,658.7 | 276 | 2,765 | 2,573 | 2,385 | −46 / −44 / −32 |
| 09-23 | 9,897 | 2,423.8 | 807 | 2,736 | 2,527 | 2,340 | −29 / −46 / −45 |
| 09-26 (fresh pull) | 10,025 | 2,489.1 | 338 | 2,649.2 | 2,414.8 | 2,220.3 | further down |

So the field as a whole is **still converging downward** (top-1 % has fallen 2,811 → 2,649, ≈ −54/day
over five days; top-5 % 2,617 → 2,414.8, ≈ −67/day), while team count grows slowly (+293, ≈3 %).
This is consistent with rating deflation as the ladder matures rather than with a field whose *top*
is strengthening.

## 3. Closed-period forecast per line (assumptions stated, no false precision)

Assumptions: (a) the equilibrium estimate from (1) is the score band where the line's win rate is
50 %; (b) the field's cutoff decay continues at ~30–60/day into the closed period, at least for the
first week, then flattens; (c) our lines' opponent pools keep rising as their displayed scores rise
(the matchmaker behaviour we have measured repeatedly); (d) no new submissions after 09-30.

| line (ref) | equilibrium estimate | vs today's cutoffs | projection at convergence |
|---|---|---|---|
| **56533839** (best-measured) | **2,600–2,700** | above top-5 % (2,414.8); near top-1 % (2,649.2) | settles at/above the top-1 % line if the decay continues |
| 56523821 | 2,300–2,400 | at/just below today's top-5 % | comfortably inside top 5 %, below top 1 % |
| 56496301 | 2,300–2,400 | as above | as above |
| 56496292 | 1,900–2,100 | below today's top-5 %, above today's top-10 % (2,220.3 is above this band) | top-10 % zone |
| `shep_straw` (not submitted; Task 33) | 56533839-class + ~+115 pts local (stack +0.8 % wallet) | — | would be our strongest candidate for the closed period |

**Uncertainty, plainly stated:** the equilibrium crossings rest on 12–93 games per band with Wilson
intervals ±10–20 points of win rate, i.e. ±150–250 rating points; the decay rate rests on three daily
observations and may flatten or reverse as the field converges; and the local-wallet → rating ruler
(~145 points per +1 %) remains a single confounded anchor. Treat the table as ordering, not prediction.

## 4. Basins vs convergence (the decision-relevant question)

Evidence from our own tracker history, win rate and opponent-mean trajectory per instance:

| ref (payload family) | samples | win % first → last | opponent mean first → last |
|---|---|---|---|
| 56307879 (V42 baseline) | 18 | 100 % → 43 % | 496 → 2,067 |
| 56307906 (V42+RG+CS) | 18 | 100 % → 46 % | 650 → 2,163 |
| 56409633 (plain composite) | 4 | 81 % → 55 % | 2,187 → 2,293 |
| 56422944 (comp_both) | 4 | 77 % → 58 % | 2,243 → 2,378 |
| 56447790 (comp_straw) | 2 | 66 % → 61 % | 2,405 → 2,434 |
| 56523821 | 2 | 77 % → 66 % | 1,820 → 1,948 |

**Every instance converges the same way: as its displayed score rises, the matchmaker raises its
opponent band, and its win rate decays monotonically toward ~50 %.** That is the signature of **one
equilibrium per strength level plus slow convergence** — the level is set by the build's strength, and
the landing point only determines how long the transient lasts. I find **no instance of a persistent
divergence**: two instances of the same payload at 2,276 and 2,642 (the human's observation) is what
the convergence picture predicts at different phases, and nothing in the data shows a line stuck at
one band with a permanently different win rate.

**What is unmeasured:** the per-submission score series needed to watch two identical payloads
simultaneously (the two-tracked-submission rule mostly prevents this), and the closed period's own
dynamics (opponent pools may shrink as fewer submissions are active, which could *freeze* a landing
rather than wash it out — an effect we cannot measure today). So the verdict is: **data favour
washing-out (convergence), with the caveat that a thin closed-period pool could freeze a landing;
submit the strongest build at T-3 rather than optimising for a landing.**

## 5. Artifacts

| file | content |
|---|---|
| `scripts/t34_equilibrium.py` | per-band win rates + Wilson intervals, crossing points, repeat beaters, field census, cutoff trend, basin check |
| `data/episodes-{56565204,56533839,56523821,56496301,56496292}-raw.json` | the refs' game lists |
| `data/leaderboard.json` | the fresh leaderboard (10,025 teams) |
| `data/cmp-track.csv` | our cutoff history |
| `data/submission_track.json` | per-ref tracker samples (win rate and opponent mean over time) |
