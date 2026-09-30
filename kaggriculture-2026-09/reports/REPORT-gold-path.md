# Gold path (Task 27) — can we reach ~2,900, and where would the +240 points come from?

Date: 2026-09-22/23. Analysis and measurement only. **No submission was made; no live file was
touched.** The question: we are at 2,661.6 (rank 296/9,838, top 3.0 %), top-1 % is 2,769.5, and the
target ~2,900 is **+240 points ≈ +1.6 % of local wallet ≈ +1,600 coins/game**.

## 0. Answer in one paragraph

**No identified route delivers the +240 points.** A stronger public base — the one route with the
right order of magnitude — **measured neutral-to-negative**: the three newly-pulled high-claim
composites that can be extracted offline are statistically tied with, or clearly worse than, our
current line on two unused panels, and all of them carry **our exact route tape and opening**, i.e.
they are "same data + more layers". Our own market layers have a **measured ceiling of ~+35 points**
for perfect elimination of every remaining close-game deficit (and ~+60–70 points for the single best
new layer we have found). The only family whose measured foreign value is in the hundreds-to-thousands
is the **economy-simulation family** (`_hd2_*`, `_ca_*`/`_cs_*`, `_v92_p_*`), which every attempt we
have made to reimplement measured ≤ 0. So the honest statement is: **~2,900 is not reachable by us
from any route we can currently build; the +240 lives in the economy-simulation family, at a cost we
have not yet been able to pay.**

## 1. Fresh public-notebook list (new since Task 20)

`kaggle kernels list --competition kaggriculture --sort-by dateRun --page-size 60` → 60 notebooks, of
which ~50 are new since Task 20 (the field turned over almost completely in two days). Those claiming
a peak at or near ≥ 2,900:

| notebook | claim | extraction result |
|---|---|---|
| `haideptry/the-2965-master-hybrid-engine` | 2965 | **runnable** (base64+gzip, declared sha256 `93831c18a43c4931` **verified**) |
| `haideptry/the-2950-peak-farm` | 2950 | **runnable** (`%%writefile main.py` cells) |
| `guruprasaathas111/kaggriculture-top-2-master-engine-v4` | "TOP 2" | **runnable** (base64+gzip+tar, declared sha256 `a5362d13…` verified) |
| `dmitriigluzdov/kaggriculture-7-turn-rescue-historical-lb-2800` | LB 2800+ | **runnable** (base64+gzip+tar, declared sha256 `4889137f…` verified) |
| `haideptry/countering-the-big-3-meta`, `demystifying-2900-meta-reflex-engine-and-bot`, `kaggriculture-master-engine-v4`, `kaggriculture-master-engine-v3` | 2900 / meta | not offline-decodable (base85 / `/kaggle/input` dataset path); v3 yields no payload |
| `hakdevelopment/kaggriculture-2887-score-fieldcraft-agent`, `hosen42/…m4a-metav4-sr18-2690-1` | 2887 / 2690 | not offline-decodable (no base64 payload; dataset/attachment path) |
| `prvsiyan/kaggriculture-frontier-the-soil-remembers-rain` (105 votes), `…-the-moon-counts-melons` (94) | "Frontier" | not offline-decodable (b85 payload, dataset path) |
| `fleonafft/kaggriculture-multi-route-farming-agent` | — | `kernels pull` failed |

**Provenance of the four runnable ones is identical to ours and to each other**: every one embeds the
route blob **`54fe156ea7206e38`** — byte-identical to our champion's 41-route / 3,982-action tape —
and the same step-0 opening `[['BUY_PRODUCT','WHEAT',13],['BUY_PRODUCT','WHEAT',30],['SELL','WHEAT',30]]`.
Sizes: 2965-engine 1,040,663 chars; 7-turn-rescue 1,033,759; top-2-v4 1,016,747; 2950-peak 1,010,931;
our comp_straw base line is 1,051,003. So the frontier is still **the same tape plus a different
number of layer characters** — no candidate brings new data.

## 2. Duels vs our current line (`data/composite/comp_straw/main.py`)

Paired, seats alternating, 60 games per panel, unused seeds (IS 9500–9529, OOS 9600–9629).

| candidate | panel | Δ wallet | Δ % | t | W–L | cand / base wallet | err |
|---|---|---|---|---|---|---|---|
| **the-2965-master-hybrid-engine** | IS | **+37** | +0.04 % | **+0.17** | 23–37 | 94,345 / 94,308 | 0 |
| | OOS | **−82** | −0.09 % | **−0.40** | 30–30 | 95,144 / 95,226 | 0 |
| **kaggriculture-top-2-master-engine-v4** | IS | **−517** | −0.55 % | **−3.39** | 11–47 | 94,133 / 94,650 | 0 |
| | OOS | **−698** | −0.73 % | **−6.75** | 6–54 | 94,802 / 95,500 | 0 |
| **kaggriculture-7-turn-rescue-lb-2800** | IS | **−345** | −0.36 % | **−2.36** | 19–41 | 94,118 / 94,462 | 0 |
| | OOS | **−456** | −0.48 % | **−3.65** | 14–46 | 94,973 / 95,429 | 0 |
| `the-2950-peak-farm` | IS | **−545** | −0.58 % | **−3.57** | 9–51 | 94,099 / 94,644 | 0 |
| | OOS | not run — its job was cancelled to free CPU for the Task-28 sweep (the machine was at load 334; the IS result at t = −3.57 is already decisive) | | | | | |

Verdict: **the claimed 2965 build is statistically indistinguishable from our line** (the two panels
disagree in sign, |t| < 0.5), and the "TOP 2" / "LB 2800+" / "2950 peak" builds are **significantly
worse** (−0.55 %, −0.73 %, −0.58 % with |t| = 2.4–6.8). None is a base worth switching to, so **there
is no candidate on which to stack our layers** (step 4 of the brief is vacuous: the stacking increment
was not computed because no candidate beat the base). This is also a clean demonstration of the
ladder-vs-local distinction: *claimed 2,950–2,965* composites are locally no better than our
2,661-rated line, because public peaks are ladder numbers produced by the same tape, more layers, and
the field/age effects we have measured before.

## 3. Where the +240 points are — itemised, with the number attached

| route | measured / estimated size | in rating points (ruler: ~145 per +1 % wallet) | reachable by us? |
|---|---|---|---|
| **(a) our market layers, perfect fix of every remaining close-game deficit** | +243 coins/game = **+0.24 % wallet** (Task 26: 22 losses + 18 near-losses, 99 games) | **≈ +35** | reachable but small; **the ceiling of the whole diagnosis** |
| (a′) our market layers, the single best new layer found (strawberry, day 13+) | +416/+390 (our Task-24 panels) and **+480, t = 7.62, 53/7 on 9300–9329** (parent's measurement) | **≈ +61 … +70** | already in the submitted line (56447790) |
| (a″) per-item extension of the same mechanism (wheat/milk/carrot/tomato/egg/fertilizer) and pruning of the components | under measurement in Task 28 (per-item sweep + ablations on 9500–9529 / 9600–9629) | to be added by Task 28 | reachable; this is the only remaining *market-side* search |
| **(b) economy-simulation families** (`_hd2_*` demand rewriting, `_ca_*`/`_cs_*` yield/feed simulation, `_v92_p_*` sale forecasting) | the Task-26 diagnosis puts the dominant loss-side leak here (wheat→milk feed conversion: wheat −683 in losses while milk is only +30, vs milk +315 in wins); foreign whole-build edges of **+778 … +4,407 coins/game** live in this family | **hundreds to thousands, unmeasured for us** | **not reachable with anything we have built**: every adjacent attempt measured ≤ 0 (milk −290/−345, carrot −279/−469, herd −982…−38,995, wheat flow ≈ −2.5 % of the gap) |
| **(c) a stronger public base** | **measured −698 … +37** vs our line; three of four candidates carry our exact tape | **≈ 0 (negative to neutral)** | reachable but worthless — measured this round |
| (d) the close-game deficits (already counted in (a)) | +35 | +35 | reachable, negligible |

**Bottom line.** The +240 needed for ~2,900 is **~7× the entire measured ceiling of our market-side
diagnosis** (+35) and **~3.4× the best single layer we have ever found** (+70, already shipped). It is
**not** in the public frontier (measured ≤ 0), and it is **not** in the close-game deficits. The only
container with the right order of magnitude is the economy-simulation family — and that is precisely
the family we have failed to reimplement across Tasks 4–19 (all negative), while the foreign
composites that do contain it measure +778…+4,407 against our builds.

**Cost statement.** The market-side routes are cheap (one builder entry, ~2 duels ≈ 10–20 min each) and
are being swept in Task 28. The economy-simulation route is a different kind of project: it requires
modelling feed→milk conversion, per-crop yield timing and demand-side shop behaviour *from scratch*,
with a fidelity gate before any duel; the S1/S2 line (Tasks 11–18) showed that our explicit-plan
representation cannot carry this economy, and the closing verdict there was that a closed-loop planner
would be S3-scale. **Recommendation: keep the current line running (it is inside the top 5 % and
climbing), finish the cheap market-side sweep (Task 28), and treat ~2,900 as out of reach without
committing to an S3-scale modelling effort — do not spend a submission slot on any of these public
bases.**

## 4. Artifacts

| file | content |
|---|---|
| `data/notebooks-t27.csv` | the fresh `kernels list --sort-by dateRun` (60 notebooks) |
| `scripts/notebook_to_main.py` | offline extraction from `%%writefile main.py` cells |
| `scripts/notebook_b64_extract.py` | offline extraction from base64 / gzip / tar payloads (verifies declared sha256) |
| `data/cand/*-extracted-main.py` | the four runnable public bases (+ their provenance printed at extraction) |
| `data/composite/duel-t27-*.json` | the duels vs `comp_straw` (IS 9500–9529 / OOS 9600–9629) |
