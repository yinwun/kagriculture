# Public frontier check — newer notebooks, and what they actually do differently

Date: 2026-09-19.  Question asked: *"查看公共的Notebook是否有更新的版本"*.
Instrument: `scripts/check_stronger.py` (pull → build → **paired duel vs the champion**,
30 town seeds × 2 seats = 60 games per candidate, `scripts/ab_duel.py`).
Champion = tracked line B = `data/tapeopt/rgcs/main.py` (V42 + room_guard + clamp_sells,
Kaggle ref 56307906, ladder 2,147.5).

## 1. Answer: yes — five of the six newest frontier notebooks beat our line

| candidate notebook | delta vs champion | t | W/L | verdict |
|---|---|---|---|---|
| `thomastschinkel/the-2945-farm-96-vs-the-top-10-public-bots` | **+4,407** | +6.04 | 58/2 | strongest |
| `tetsutani/demand-preserving-turn-sale-timing` | +2,468 | +4.77 | 49/11 | stronger |
| `goodpjw2008/kaggriculture-melon-threshold-squeeze-2749` | +1,715 | +8.31 | 57/3 | stronger |
| `guruprasaathas111/game-theoretic-master-discrete-optimization` | +1,073 | +5.02 | 43/17 | stronger |
| `seyitkaangunes/kaggriculture-2820-score` | +778 | +3.45 | 42/18 | stronger |
| `aurax7/kaggriculture-shop-router-reactive-v7` | +142 | +1.06 | 34/26 | tie |
| `ahmedberatozer/kaggriculture-v49-funded-sale-timing-and-worker` | — | — | — | build failed (references `submission_competitive_v49.tar.gz`) |

Champion wallet on these 60 games: 99,203 → the best candidate earns 103,609 (+4.4%).
Earlier sample for contrast (`data/stronger-check.json`): `v48-fast-routes` −25,346,
`kaggriculture-2900` −30,197, `c68-thunder-adaptive` −38,610 — all far weaker.

So the ecosystem did move past V42 after all: the whole top of the public list is now
above our champion, and the margin of the best one is decisive (58-2).

## 2. What the best candidate actually is

`the-2945-farm...` is a **composite of public parents**, not a from-scratch policy: the file
carries the attribution/notice blocks of `yhay81/shop-router-0908/0909/0913`,
`thomastschinkel/kaggriculture-93-8-win-rate-public-state-router`, `ahmedberatozer`
V39–V49, `tetsutani`, `prvsiyan` and `Dmitrii Gluzdov` (Apache-2.0), wraps ~41 `agent()`
definitions, and ends with a tape-router chassis.  Its lineage is *our own* lineage: the
champion's `_ROUTES` come from the same R108 shop-router data (`yhay81`), with the V42
opening grafted on.

## 3. The measured behavioural delta: sell schedule, nothing else

Action-mix over the same 60 paired games (candidate vs champion, per-agent totals):

| action | 2945-farm | champion | delta |
|---|---|---|---|
| **MKT_SELL** | 25,617 | 18,597 | **+7,020 (+37.7%)** |
| FERTILIZE | 7,045 | 6,624 | +421 (+6.4%) |
| WATER | 66,551 | 67,019 | −468 (−0.7%) |
| MKT_BUY_PRODUCT | 4,076 | 4,347 | −271 (−6.2%) |
| PLANT/HARVEST/CARE/FEED/HIRE/MOVE/PASS | — | — | **within ±1%** |

Everything structural is identical within 1%.  The only large difference is that the
candidate issues 37.7% more SELL orders.  A direct probe (`scripts/sell_probe.py`, 4 games)
confirms the shapes differ: champion 323–348 sell orders/game, candidate 467–525.

## 4. Why sell *timing* is worth that much — the engine's market model

From `kaggle_environments/envs/kaggriculture/kaggriculture.py`:

* `market_price(item, inventory)` — the price is a **pure function of the market inventory**;
  no per-turn reversion, no randomness.
* `_town_consume` — town shops consume inventory on the steps where `step % 4 == 0`
  (a single-product shop consumes 2 units, any other 1 unit), plus the town centre every
  24 steps.  This drain is the only force that pushes the price back up.
* The market clears in a **per-slot, per-unit lockstep**: the i-th market order of player 0 is
  cleared against the i-th order of player 1, unit by unit, and *both players are quoted the
  same pre-commit price* for every unit.

Consequences we can exploit, and which we had not:

1. A lot sold as one block walks down its own price curve; the same lot sold over several
   turns is partly sold at prices the drain has restored.
2. Which *slot* an order occupies decides **whose dump you are interleaved with**.  Selling
   next to a rival's big dump shares the price impact; selling alone bears all of it.

## 5. The frontier's mechanism, read from the single-mechanism notebook

`tetsutani/demand-preserving-turn-sale-timing` has the **same chassis as our champion** plus
these extra functions (AST diff of the two files):

```
_v44y_price  _v44y_params  _v44y_lockstep  _v44y_factor_margin  _v44y_reorder
_v44y_clone_gate  v44y_lockstep_agent  _race_snapshot  _race_clone  _race_town
_race_positions_equal  _race_lost  _adv_future  _adv_frontload  ...
```

`_v44y_lockstep(orders_me, orders_opp, inv0, stock_me, stock_opp, params)` **replays the
engine's exact per-slot/per-unit clearing in Python** and returns `(revenue_me, revenue_opp)`;
`_v44y_factor_margin` searches over candidate schedules and maximises the *differential*
`revenue_me − revenue_opp` per item.  In other words the mechanism is not "sell less" or
"sell later" — it is **simulate the shared market exactly and choose the order layout that
maximises our revenue relative to theirs**.

## 6. Our own experiment in that direction (negative, and why it is informative)

We implemented our own layer, `sell_spread` (`scripts/build_spread.py`), which caps each
step's SELL of an item at a multiple of the town's own per-step demand for it
(`SHOPS`/`SHOP_INTERVAL` drain rate), carrying the remainder forward with a deadline, a cash
gate, a shed-occupancy gate and a liquidation day.  Champion file untouched; variants are
copies under `data/spread/`.

Two instrument lessons came out of it, both worth keeping:

* **The first version silently disabled the entire layer stack.**  The layer referenced
  `view.town`, which `_View` never defined, so it raised every step; the chassis' outer
  `try/except` counted it as `layer_fallbacks` and returned the *raw tape* — dropping
  `hand_align`, `sell_lead`, `room_guard`, `clamp_sells` too.  Every variant then scored
  byte-identically (−18,071, wallet 87,634) regardless of its parameters.  *Identical results
  across different parameters are the signature of this failure, not of a dead knob.*
* **An absolute unit floor is item-blind.**  With `floor_units = 4` and wheat lots of ~90 the
  floor became the only binding term, which produced the same false "parameter-independence".

With both fixed (`control` reproduces the champion exactly: delta 0.0, identical action
counts), single-game probes already show the direction is wrong:

| variant (fraction of each lot deferred) | reward vs champion, seed 9000 |
|---|---|
| f50 (defer 50%) | 61,419 vs 68,208 |
| f70 | 62,830 vs 69,037 |
| f85 (defer 15%) | 76,738 vs 78,647 |

Paired duels (30 towns × 2 seats = 60 games each) vs the champion close the question:

| variant | delta | t | W/L |
|---|---|---|---|
| f85h12 (defer 15%, 12-step deadline) | −2,815 | −6.65 | 1/59 |
| f70shed70 (defer 30%, flush when shed ≥70) | −6,624 | −14.75 | 1/59 |
| f70h24 (defer 30%, 24-step deadline) | −11,431 | −12.94 | 1/59 |

Deferring sales does *not* preserve demand here: the deferred stock piles up and is flushed
late, flooding the market (and in a mirror game the champion itself earns 110,917 — so the
spread variant also depresses its opponent's market, i.e. it destroys shared value).  The
best spreading variant is 2.7% worse than the line it was meant to improve, at t = −6.65.

**Conclusion: naive deferral is a dead end; the +4.4% comes from choosing the sell schedule
against a *predicted* rival schedule, which requires the exact lockstep simulator.**

## 7. Where this leaves the submission decision

* Our tracked line (2,147.5, top ~14%) is now measurably behind five public builds.
* The strongest build is a composite of other authors' notebooks (attribution notices intact,
  large parts obfuscated), so submitting it verbatim conflicts with the standing instruction
  not to submit someone else's notebook.
* The mechanism itself, however, is implementable by us from the engine's published rules:
  a lockstep market simulator + a schedule search.  That is the honest route to a stronger
  *own* notebook.

Artifacts: `data/stronger-check.json`, `data/duel-*.json`, `data/sell-probe.json`,
`data/cand/*/main.py`, `data/spread/*/main.py`, `scripts/check_stronger.py`,
`scripts/sell_probe.py`, `scripts/build_spread.py`, `scripts/spread_sweep.sh`,
`log/frontier.log`, `log/sell_probe.log`.

## 8. Chosen route (user decision, 2026-09-19): A — build our own mechanism

The user chose **A**: implement our own lockstep market simulator plus a sell-schedule
search, rather than submitting someone else's notebook (B = refresh the rating clock by
resubmitting our own line, C = submit the frontier build, D = write-up only, were the
alternatives).

Work brief handed off (subagent, tracked in `REPORT-race-mechanism.md` when done):

1. `scripts/lockstep.py` — faithful standalone replica of the engine's per-slot/per-unit
   clearing (`_parse_order` → quoted → commit loop, `market_price`, `steps % 4 == 0` town
   drain), validated against the real engine on generated order pairs.
2. A new market layer (builder `scripts/build_race.py` → `data/race/<variant>/main.py`,
   champion file never modified) which, each step, enumerates candidate layouts of **our own**
   current market orders (as-is, earlier slot, split across two slots, later slot) and picks
   the one maximising simulated `revenue_me − revenue_opp`, using a small set of rival-order
   hypotheses (rival's last observed step, our own tape's next step, empty).

## 11. The "newer snapshot" hypothesis is refuted too — and with it the last cheap lead

`REPORT-snapshot.md` decoded the route blobs (`_R108_DATA`, base85+zlib) out of our champion,
`demand-preserving-turn-sale-timing` and `the-2945-farm-96-vs-the-top-10-public-bots`. **All
three blobs are byte-identical** (sha256 54fe156ea7206e38; 41 routes, 3,982 actions, 94,490
chars), verified by hashing, not by reading the obfuscated source. Diffing the *effective* tapes
after each composite's own post-load edits: the readable build is 100% identical to ours, and the
frontier differs in **41 of 29,479 step-slots — exactly one step per route, always step 0**, with
zero farmer/hands differences:

* ours: `BUY_PRODUCT WHEAT 5, BUY_PRODUCT WHEAT 10, SELL WHEAT 60`
* theirs: `BUY_PRODUCT WHEAT 13, BUY_PRODUCT WHEAT 30, SELL WHEAT 30`

That step-0 edit alone is worth **+632 (t=+3.58, 43/17)** vs the champion — as much as our whole
race layer — but **−166 (t=−1.67, 3/57)** against the live stack: it shifts the early cash/seed
plan (PLANT −120, PASS +113 per 60 games), which is why it interacts with our layers. It is
therefore not an improvement on the submitted line.

Consequence: the frontier's edge is **not newer data and not any single mechanism we could
rebuild** — it lives in its ~120-layer composite. Every mechanism family we could name is now
measured (this file §9–§10 plus `REPORT-race-mechanism.md`, `-herd-swap`, `-sell-forward`,
`-plan-screen`, `-wheat-gap`, `-rival-layout`, `-lot-timing`, `-robust-layout`, `-herd-turn`,
`-snapshot`). Remaining options and their real cost: (a) keep extracting the composite's layer
families one at a time — largely obfuscated, each family so far worth hundreds, not thousands;
(b) a from-scratch 719-step tape re-plan — days to weeks, every candidate needing a full 60-game
paired duel, and a plan edit can flip the day-6 shop draw; (c) keep the current measured,
reproducible, submitted line.

Live submissions from this work: **56348775** (`outer_prem`) and **56349751** (stack), both
`COMPLETE`; 2 of 5 quota used on 2026-09-19.
3. Validation only with `scripts/ab_duel.py` (paired vs the champion, 30 seeds × 2 seats);
   positive only if delta > 0 with t ≥ 3. Control variant must reproduce the champion exactly.
4. Traps to respect: the chassis' outer `try/except` silently falls back to the raw tape on
   any layer exception (check `layer_fallbacks == 0`); byte-identical results across different
   parameter values mean a broken layer, not a dead knob; `_View` does not expose the town
   shop list by default.

## 9. Route A, first result: a real but small win, and a refutation of §3

The delegated work is written up in `REPORT-race-mechanism.md`. Two headline outcomes:

* **`data/race/outer_prem/main.py` beats the champion.** Own replica of the engine's
  per-slot/per-unit clearing (`scripts/lockstep.py`; validated by 12,942 price checks against
  the observation's own `prices`, 400 randomised clearing trials against real envs, and 2,872
  player-steps of real games — all 0 mismatches) driving a search over the *layout* of our own
  sell orders. Paired vs the champion: **+597, t=+9.87, 58/2** (seeds 9000–9029) and
  **+676, t=+10.70, 57/3** out-of-sample (fresh towns 9100–9129). `MKT_SELL` and every other
  action counter are byte-identical — quantities are never touched, only slot order.
  Oracle ceiling with perfect knowledge of the rival's layout is only +513/+963 per game, so
  layout tuning cannot approach the 4,400-point gap.
* **§3 above is refuted.** The frontier's "+37.7% MKT_SELL" is a request-pattern artefact: it
  requests 85,884 units at seed 9000 but only 1,591 execute (the shed caps them), while the
  champion requests 1,597 and executes 1,580 — same sales, same revenue. Its real edge is a
  **farm-side goose→sheep herd swap when the town unlocks a YARN_STORE** (corr(delta, sheep
  census) = +0.52; seeds with a yarn store n=23 mean +5,336 vs +1,353 on the 7 without).

Submitted 2026-09-19 as ref **56348775** (`data/submits/submission-race-outerprem.tar.gz`,
sha256 22920a02d8b16b20, 1 of 5 quota used; packaged build smoke-tested 720 steps with
`layer_fallbacks 0` and all error counters 0). The champion line 56307906 stays tracked as the
second slot. Next: the herd-swap causality test on the yarn-store seeds; if it validates, the
stack (herd + outer_prem) is the submission candidate.

## 10. The herd swap was refuted, and the sell-forward stack was submitted instead

* **Herd swap: causally refuted, 0% of the gap** (`REPORT-herd-swap.md`). Forcing geese→sheep
  on the 23 yarn-store seeds costs −982 (t=−1.06); geese→cows (the direction the frontier
  actually uses) −5,087; a positive control (cows→sheep) −38,995 proves the intervention is
  live. The correlation misled us because the census differs on only 13/30 seeds (17/30 are
  census-identical, mean delta +2,286 there), and where it differs the frontier has *more cows*;
  our champion already ships a shop-keyed sheep→cow layer (`_V231`). Stacking it on `outer_prem`
  turns +632 into −129: the gains do not add.
* **What the frontier's timing gap really is** (`REPORT-sell-forward.md`): at seed 9009, with an
  identical farm, it earns +3,578 on *fewer* wool units — pure within-turn interleaving. At seed
  9005 it additionally has 8,548 sheep-days vs our 7,900, creating ~65 extra wool units that no
  sell layer can manufacture. The collapse-avoidance story is refuted too: with the forward
  layer, wool units and the day-window split are bit-identical (228 units, 163 early / 65 late);
  only the mean price inside the same turns moves (119.9 vs 111.8).
* **Submitted 2026-09-19 as ref 56349751** (`data/submits/submission-race-forward-stack.tar.gz`,
  sha256 df762731da84a3a8, 2 of 5 quota used): `outer_prem` + the wool sell-forward layer.
  Paired vs the champion +790 (t=5.29) in-sample / +1,099 (t=7.84) out-of-sample; paired
  **directly against the previously submitted `outer_prem`**: +276 (t=2.09) in-sample, +469
  (t=3.93) out-of-sample, **pooled over 60 independent towns +372, t=+4.18, 48/60 positive**.
  Smoke-tested 720 steps with `layer_fallbacks 0`, `race_errors 0`, both layers firing
  (`race_reorders 11`, `forward_orders 20`).
* **Gap explained so far: 18% in-sample / 25% out-of-sample.** The remaining 75–82% is the tape
  plan itself (sheep-days, wheat volume, per-turn stock placement); the two files replay
  disjoint route tables (0 of 41 tapes byte-identical). That is Task 4: a properly powered
  per-shop-tuple route screen plus our own plan re-tune for the wool program — the earlier
  41-route screen used only 3 seeds (best t=+0.14), so it was a screen, not a verdict.



