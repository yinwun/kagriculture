# Herd swap (geese → sheep/cows keyed on the town's shop draw) — REFUTED

Date: 2026-09-19. Parent task: test causally whether the goose→sheep swap is the
public frontier's real edge, and turn it into our own layer if it is.
Baseline/champion: `data/tapeopt/rgcs/main.py`. Instrument: `scripts/ab_duel.py`
(paired, seats alternating; delta = mean per-seed candidate − champion wallet).
Comparison target: `data/cand/the-2945-farm-96-vs-the-top-10-public-bots/main.py`
(+4,407, t=+6.04, 58/2 over seeds 9000–9029).

**Bottom line: the herd swap is not the mechanism. Forcing it on our champion makes it
worse in both directions — geese→sheep −982 (t=−1.06) and geese→cows −5,087 (t=−5.54) on
the 23 YARN_STORE seeds — it accounts for 0% of the frontier's +4,407, and stacking it on
our market-side winner destroys that win (+632 → −129 on the same 23 seeds).**

## 1. The crude causal test (done first, as instructed)

Route taken: **tape-level rewrite**, not a dynamic layer (`scripts/build_herd.py` →
`data/herd/<variant>/main.py`, champion file untouched, nothing vendored).

Our champion's animals are bought, built and placed by the frozen route tapes, so the
cheapest honest intervention is to rewrite the animal *kind* inside those tapes at import
time: `BUY_ANIMAL GOOSE|COW → SHEEP|COW`, `BUILD_COOP → BUILD_PASTURE`, and the matching
`PICKUP`/`PLACE` verbs. A pasture hosts a sheep where a coop hosted a goose, every animal
eats WHEAT, and `FEED`/`CARE` are animal-agnostic, so the pen layout, feed budget and care
route survive the substitution. The patch mutates the chassis' route actions in place
(the chassis shallow-copies the route lists, so in-place mutation is visible to it and to
the wrapper agents that read `_IMPL.chassis.routes`).

One bug worth recording: the first version spent its conversion budget **globally across
all 41 routes** instead of per route. Only one route is replayed per game, so the budget
was consumed by tapes the game never uses and the lever became a silent no-op (identical
scores for every setting — exactly the "byte-identical across parameters" signature).
It is fixed; the report uses the per-route version, and the `c2s` control below proves the
intervention is now live and detectable.

| variant | seeds | games | delta | t | W/L | wallet |
|---|---|---|---|---|---|---|
| `control` (all levers off) | 23 yarn | 46 | **+0** | +0.00 | 3/3 (40 ties) | 103,732 vs 103,732 |
| `g2s` geese→sheep (2/route) | 23 yarn | 46 | −982 | −1.06 | 12/22 | 101,295 vs 102,278 |
| `g2s` | 7 no-yarn | 14 | −4,602 | −4.36 | 1/13 | 97,564 vs 102,166 |
| `g2c` geese→cows (2/route) | 23 yarn | 46 | −5,087 | −5.54 | 2/32 | 99,937 vs 105,024 |
| `g2c` | 7 no-yarn | 14 | −9,062 | −15.07 | 0/14 | 94,989 vs 104,051 |
| `g2c_partial` (1 goose→cow) | 23 yarn | 46 | −5,082 | −5.55 | 2/32 | 99,942 vs 105,024 |
| `c2s` cows→sheep (positive control) | 23 yarn | 46 | −38,995 | −9.76 | 0/46 | 69,502 vs 108,497 |

Read: the instrument is live (`c2s` moves the wallet by −39k, t=−9.8) and every herd
intervention we can make is **negative**. The YARN_STORE seeds — where the correlation was
strongest — show a null-to-negative response to forcing more sheep, which is precisely the
outcome that kills the hypothesis.

Full-panel and out-of-sample confirmation for the herd swap alone (`g2s`):

| panel | games | delta | t | W/L | wallet |
|---|---|---|---|---|---|
| in-sample, all 30 towns (9000–9029) | 60 | −1,827 | −2.30 | 13/35 | 100,425 vs 102,251 |
| out-of-sample, fresh towns (9100–9129) | 60 | −2,347 | −4.68 | 7/33 | 93,379 vs 95,726 |

`layer_fallbacks == 0` and `entry_fallbacks == 0` in every variant; `control` reproduces
the champion exactly (delta 0, identical action counters).

## 2. Why the correlation table (corr = −0.68 with geese, +0.52 with sheep) misled us

The census split is not what it looked like in the aggregate:

| seed group | n | mean delta | share of the +132,196 total |
|---|---|---|---|
| final census DIFFERS | 13 | +7,180 | 71% |
| final census IDENTICAL | 17 | +2,286 | 29% |
| has YARN_STORE in the day-8 shops | 23 | +5,336 | 93% |
| no YARN_STORE | 7 | +1,353 | 7% |

* Where the census differs, the frontier usually has **fewer geese but MORE COWS**
  (9010: 11 vs 9 cows; 9015 and 9016: 12 vs 9 cows and 0 vs 3 geese) — i.e. the public
  layer swaps geese→**cows** there, not geese→sheep. Forcing geese→cows on our champion is
  −5,087.
* 17 of 30 seeds have a byte-identical final animal census and still show a mean +2,286
  (e.g. seed 9009: both 11 sheep, 0 geese, 6 cows, delta +5,607).
* Both directions of the forced swap are negative, so the census difference is a
  **symptom** of the frontier running a different plan, not the cause of its revenue.

The champion is not short of sheep anyway: it already ends with 16 sheep and 6 cows at seed
9005 (the tape buys 4 sheep + 6 cows + 2 geese; the wrappers add 6 more sheep), and it
already ships an own shop-keyed layer (`_V231`) that converts the tape's **sheep program
into cows** when no YARN_STORE is drawn and milk shops dominate. Its animal mix is the same
family of decision the frontier makes.

## 3. The stacking test (parent request): the gains do NOT add

Same 23 YARN_STORE seeds, same instrument:

| candidate | delta | t | W/L | wallet |
|---|---|---|---|---|
| `outer_prem` (market-side winner, herd off) | **+632** | **+9.26** | **46/0** | 104,004 vs 103,372 |
| `outer_prem` + `g2s` herd patch (`data/herd/stack_g2s_outer_prem/main.py`) | −129 | −0.14 | 28/18 | 101,656 vs 101,785 |

The herd component costs ≈ 760 on the yarn seeds and removes the market-side win entirely.
`race_errors == 0`, `layer_fallbacks == 0` on the stack. There is no positive herd variant
to stack; the "additivity" question is therefore answered in the negative.

## 4. What the frontier's remaining advantage actually is (residual diagnosis)

For seeds where the farm is provably the same, the gap is on the **revenue** side, and it is
a **sell-timing** effect on the same shared market, not a quantity or inventory effect:

| seed | delta | frontier revenue | champion revenue | executed units (cand/base) |
|---|---|---|---|---|
| 9009 | +5,607 | 114,926 | 108,664 | 1,582 / 1,580 |
| 9005 | +12,873 | 140,085 | 126,968 | 1,718 / 1,654 |

Per item, with the per-unit price walk replayed by our own validated replica
(`scripts/lockstep.py`):

* **WOOL, seed 9009**: frontier 236 units at average **113.4**, champion 243 units at
  **95.4** — the frontier earns +3,578 on *fewer* units. Price buckets: frontier 104 units
  ≥$150 vs 92, and 41 units <$10 vs 72.
* **WOOL, seed 9005**: frontier 393 units at 168.7 vs 353 at 161.7 (+9,228).
* **WHEAT, both seeds**: +52 / +78 units at the *same* average price (40.6 vs 40.3,
  41.5 vs 40.9) — worth +2,215 / +3,426. Here the frontier simply has more wheat.

The wool effect is the frontier selling out of the day-24 price collapse (seed 9005, wool
units per day):

| window | end-of-day wool price | frontier | champion |
|---|---|---|---|
| days 0–23 | $161 – $243 | **266** | **216** |
| days 24–29 | $1 – $66 | 127 | 137 |

≈50 wool units are moved from a ~$10 window into a ~$200 window ≈ +9,500, which is the
whole +9,228 wool-revenue gap. That is **front-loading** (sell the shed as soon as it
exists, while the price is high), i.e. the opposite direction of our already-refuted
`sell_spread` deferral (−2,815, t=−6.65), and a different mechanism from the within-turn
slot layout (measured at +597, `REPORT-race-mechanism.md` §4).

Two structural facts support "a different plan of the same lineage" rather than a single
switch:

* the two files' route tables are disjoint: **0 of 41** route tapes are byte-identical
  (hash of the full 719-step action list), while every non-market action count differs by
  only ~1–3% — the same lineage, a newer tape snapshot;
* forcing our champion onto each of our own 41 routes in turn (screen, 3 highest-delta
  seeds = 6 games each) finds no better tape: best is r6 +1,196 at **t=+0.14**, and 30 of
  41 routes are negative. The champion's shop→route lookup is not obviously mis-selecting;
  the frontier's advantage is inside its tapes/layers, not in ours.

## 5. Quantification, honestly

* Herd swap: **0%** of the frontier's +4,407 (causally −982 on the yarn seeds; −5,087 for
  the geese→cow direction; nothing positive anywhere).
* YARN_STORE seeds carry 93% of the gap, but the cause is *not* wool demand driving a
  herd change (that is refuted); the YARN_STORE flag mostly separates which shop-tuple /
  route family each agent plays, and the frontier plays a better one.
* Unexplained: essentially all of it. The two measured components are sell **timing**
  (front-loading out of the collapse; ~+9.2k of the +12.9k at seed 9005) and small farm
  logistics (wheat availability; +2.2k/+3.4k). We have not built or measured a layer for
  either.

## 6. Recommended next step

1. **Do not build the herd swap.** It is refuted in both directions with a live instrument.
2. Build a **sell-forward (front-load) layer**: at each step, offer the shed stock that the
   tape plans to sell later, gated by a *simulated* price comparison — the price is a pure
   function of the market inventory (`scripts/lockstep.py` has the exact model, already
   validated to 0 mismatches on 2,872 real player-steps), so the layer can compare today's
   price with the price it would get at the tape's planned step after the town drain
   (`step % 4 == 0`). Target: the ~50 wool units per game that the champion currently sells
   into the day-24 collapse.
3. Keep `outer_prem` (market-side, +597 in-sample / +676 out-of-sample) separate: it is
   orthogonal, and it must be re-measured on top of any sell-forward change, since both act
   on the same market list.
4. Nothing has been submitted to Kaggle.

## 7. Artifacts

* `scripts/build_herd.py` → `data/herd/{control,g2s,g2s_partial,c2s,c2s_partial,g2s_c2s,g2c,g2c_partial,g2c_c2s}/main.py`,
  `data/herd/variants.json`.
* `scripts/build_stack.py` → `data/herd/stack_g2s_outer_prem/main.py`.
* `scripts/build_route.py` → `data/route/r0..r40/main.py`.
* Evidence: `data/herd/sweep-crude.txt`, `data/herd/sweep-g2c.txt`, `data/herd/sweep-stack.txt`,
  `data/herd/duel-*.json`, `data/route/sweep.txt`, `data/route/duel-r*.json`,
  `data/race/herd-diag.json` (the correlation table that motivated the test).

### Exact rebuild commands

```bash
python scripts/build_herd.py                       # all herd variants (levers off by default)
python scripts/build_herd.py --name g2s_partial    # one variant
python scripts/build_stack.py --base outer_prem --herd g2s
python scripts/build_route.py --route 6
# decision instrument, e.g. the crude test on the yarn seeds
python scripts/ab_duel.py --cand data/herd/g2s/main.py --base data/tapeopt/rgcs/main.py \
    --seeds 9000,9002,9003,9004,9005,9006,9007,9009,9010,9012,9015,9016,9017,9018,9020,9021,9022,9023,9025,9026,9027,9028,9029 \
    --procs 10 --label g2s --out data/herd/duel-g2s-yarn.json
# market-side winner for reference
python scripts/ab_duel.py --cand data/race/outer_prem/main.py --base data/tapeopt/rgcs/main.py \
    --seeds 9000-9029 --procs 10 --label outer_prem --out data/race/duel-outer_prem.json
```
