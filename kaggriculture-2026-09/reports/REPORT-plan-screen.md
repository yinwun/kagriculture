# Plan screen — is our router mis-selecting a tape? (Task 4)

Date: 2026-09-19. Incumbent ladder (unchanged by this task):
champion `data/tapeopt/rgcs/main.py`
→ `data/race/outer_prem/main.py` (submitted, ref 56348775; +597 in-sample / +676 OOS)
→ `data/forward/wool_drain1_outerprem/main.py` (stack; +790 in-sample / +1,099 OOS).
Instrument: `scripts/ab_duel.py`, paired, seats alternating.

## 0. Verdict

**No, the router is not mis-selecting.** In the only group with enough towns to test
(the tape that 20 of 60 towns actually play), the router's own choice is never beaten
by more than **+24** (0.02% of the wallet) while every other tape loses 3,000–9,750.
The router's tables are also complete: all 60 observed shop cells are table hits, with
**0 fallbacks** to the default route, so the one structural way it could mis-select
(playing a generic tape for an unknown cell) does not happen.

Task 4 therefore produced **no new build**: the ladder stays
champion → `outer_prem` → `wool_drain1_outerprem`, so the frontier gap explained stays
at **~18% in-sample / ~25% out-of-sample**. What the task did produce is a measured
narrowing of the residual (§4) plus one methodological finding that matters for any
future plan work (§1).

## 1. First finding: the router's cell cannot be captured with a dummy agent

The screen needs to know which cell (day-6 shop tuple) each town belongs to. My first
capture ran a PASS agent to step 144 and read `town.unlocked_shops[:2]`. That mapping
is **wrong**, and the reason is in the engine:

```python
def _end_of_day(state, env, day):
    rng = random.Random((seed * 1_000_003) ^ day)   # one RNG per day
    ...
    _spawn_weeds(farm, board_size, weed_chance, rng)   # consumes one draw per empty tile
    ...
    if len(town["unlocked_shops"]) < MAX_SHOP_INSTANCES:
        town["unlocked_shops"].append(rng.choice(sorted(SHOPS)))   # same stream, later
```

The shop draw consumes the **same per-day RNG stream** as end-of-day weed spawning, so
it depends on how many empty tiles each player leaves — i.e. **on the agents' farm
play**. A dummy agent's draws differ from a real game's, and the resulting cell→route
map disagreed with reality for most towns (it claimed 9002, 9004, 9005 all play route
105; real games play 103, 9, 1).

Consequence for the whole project: **any farm-plan change can flip the shop draw and
therefore the whole tape.** Plan levers have chaotic, non-local effects — a variant that
changes the empty-tile count on a shop-unlock day can jump to a different route — so
plan changes can only ever be judged with the paired duel, never by inspecting the
tape. The valid cell capture is `scripts/route_groups.py`, which records the route the
champion actually plays in a real game.

## 2. Deliverable (a): cells and their occurrence counts

True distribution over the 60 towns (21 distinct routes actually played):

| route | towns | IS / OOS | seeds |
|---|---|---|---|
| 105 | **20** | 9 / 11 | 9000, 9001, 9008, 9015, 9017, 9023, 9026, 9027, 9028, 9100, 9101, 9102, 9104, 9106, 9109, 9114, 9120, 9123, 9124, 9129 |
| 107 | 5 | 2 / 3 | 9014, 9018, 9112, 9115, 9126 |
| 5 | 5 | 0 / 5 | 9103, 9111, 9118, 9127, 9128 |
| 1 | 4 | 1 / 3 | 9005, 9105, 9108, 9116 |
| 104 | 3 | 3 / 0 | 9003, 9013, 9019 |
| 103, 9, 101, 3, 7, 106, 10 | 2 each | — | — |
| 124, 118, 120, 122, 110, 11, 8, 121, 123 | 1 each | — | — |

**The requested per-cell screen at ~30 towns per cell/tape pairing is impossible**: one
group has 20 towns, one has 5, and 15 groups have a single town. A per-cell verdict for
those cells would rest on 2 games (SE in the thousands), so I did not spend the round on
them, as instructed.

## 3. Deliverable (b): the screen on the one adequately populated group (route 105, 20 towns)

Intervention: force one tape for steps **[144, 648)** — the window in which the router's
cell choice is in force (before 144 the router returns route 0; at 648 it switches to
route 2) — and keep the champion's own router everywhere else
(`scripts/build_route.py --route R --from-step 144 --to-step 648` → `data/routewin/wR`).
40 games per row (20 towns × 2 seats):

| forced tape | delta | t | W/L | wallet | verdict |
|---|---|---|---|---|---|
| **105 (the router's own pick — control)** | **+0** | +0.00 | 3/3 | 110,385 vs 110,385 | override is an exact no-op ✔ |
| 107 | +24 | +76.45 | 37/3 | 110,399 vs 110,375 | detectable but 0.02% — negligible |
| 1 | −9,398 | −5.10 | 4/36 | 104,409 vs 113,808 | much worse |
| 9 | −9,749 | −4.91 | 5/35 | 103,544 vs 113,293 | much worse |
| 5 | −9,347 | −5.10 | 4/36 | 104,378 vs 113,725 | much worse |
| 104 | −4,603 | −5.44 | 3/37 | 111,592 vs 116,196 | worse |
| 103 | −3,083 | −3.74 | 12/28 | 112,619 vs 115,702 | worse |
| 101 | −3,018 | −3.57 | 12/28 | 112,810 vs 115,829 | worse |

The `w105` row is the control the parent asked for and it is exact: forcing the tape the
router already plays reproduces the champion byte-for-byte (delta 0, identical wallets,
`layer_fallbacks 0`, `entry_fallbacks 0`). Every alternative tape that is not 105 is
strictly worse on 105's towns, by −3,000 to −9,750. The +24 for tape 107 is real in the
statistical sense (t=+76 — the per-seed delta is essentially constant) but worthless in
money terms, and 107's group is its own 5 towns, so it is not a router error either.

**No router override is justified and none was built.**

## 4. Priority 2 (our own wool/sheep plan): measured, and not worth building

I decomposed the "+8% sheep-days" claim I handed over in `REPORT-sell-forward.md` and
it does not survive as a lever:

* 8,548 vs 7,900 **sheep-steps** = **+648 sheep-steps = +27 sheep-days** over the whole
  game (+8%), not +648 sheep-days. Day-by-day census at seed 9005: identical until day
  11, then +1 sheep for the rest of the game plus a one-off **+7 on day 12** (the
  frontier's bulk purchase lands one day earlier: 10→17 on day 12 vs our 10→16 on day 13).
  +27 sheep-days ≈ +9–18 wool units ≈ a few thousand coins at the observed prices.
* The other candidate explanation for its +40 wool units at seed 9005 — a better care
  regime — is **refuted**: per-animal-day coverage (cared+fed, which is what banks the
  care bonus that the engine pays out on a fed production day) is equal or better on our
  side:

| seed | animal | frontier cared+fed | champion cared+fed |
|---|---|---|---|
| 9005 | SHEEP | 312/349 = 89.4% | 300/322 = **93.2%** |
| 9005 | COW | 94/154 = 61.0% | 98/156 = **62.8%** |
| 9009 | SHEEP | 197/241 = 81.7% | 195/239 = 81.6% |
| 9009 | COW | 121/154 = 78.6% | 122/156 = 78.2% |

So neither the herd mix (Task 2: forced swaps −982 and −5,087), nor sheep-days
(+27 days ≈ +8% of output), nor care/feed coverage (equal to better) explains the
frontier's extra wool and revenue. I did not build a sheep-day layer: the size (~+few
thousand at best, and only if a budget-gated bulk purchase can be moved a day earlier
without losing cash elsewhere) does not justify a round, and my crude herd interventions
in the same area all measured negative.

## 5. The ladder and the gap

| build | in-sample 9000–9029 | out-of-sample 9100–9129 |
|---|---|---|
| champion | — (base) | — |
| `outer_prem` (submitted, 56348775) | +597, t=+9.87, 58/2 | +676, t=+10.70, 57/3 |
| + `wool_drain1` stack | +790, t=+5.29, 53/7 | +1,099, t=+7.84, 57/3 |
| Task 4 | no new candidate (router screen negative) | — |

Fraction of the frontier's +4,407 explained: **~18% in-sample / ~25% out-of-sample**
(the stack), unchanged by this task.

What the residual is *not* (all measured): not the router's tape choice (§3), not the
herd mix (Task 2), not sheep-days or care coverage (§4), not the sell slot layout beyond
+597 (Task 1), not sell-window timing beyond +358/+493 (Task 3). What is left, with
numbers: the frontier sells **+52 / +78 more wheat units per game at identical average
prices** (40.6 vs 40.3 and 41.5 vs 40.9 at seeds 9009/9005, worth +2,215/+3,426) — a
farm/logistics difference in wheat handling — plus the part of its within-turn price edge
that our tape cannot reach because it does not put the same stock on the market in the
same turns. Given §1, chasing either with plan edits is possible but each candidate must
be judged by a full paired duel, because any farm-plan change can flip the shop draw and
therefore the entire route.

## 6. Honest list of what did not work

* Per-cell route screen at the requested power: impossible from this data (21 routes,
  max 20 towns, 15 singletons). Report of occurrence counts instead, and a powered
  screen on the largest group only.
* Router override: rejected (best alternative +24, everything else −3k to −9.8k).
* Dummy-agent cell capture: invalid (RNG sharing, §1) — a false route map that made an
  earlier smoke test look like a broken build (−10,508 when forcing the *same* route).
* Care-bonus hypothesis for the wool gap: refuted by measurement (§4).
* Sheep-day lever: quantified at +27 sheep-days and not built.

## 7. Artifacts and rebuild commands

```bash
# true route groups (must run real games; a dummy agent gives the wrong cells)
.venv/bin/python scripts/route_groups.py --seeds 9000-9029,9100-9129
# a windowed route override, e.g. the group-105 control and one alternative
.venv/bin/python -c "import sys; sys.path.insert(0,'scripts'); import build_route; \
  build_route.build(105, 'data/routewin', 'w105', 144, 648); build_route.build(107, 'data/routewin', 'w107', 144, 648)"
.venv/bin/python scripts/ab_duel.py --cand data/routewin/w107/main.py --base data/tapeopt/rgcs/main.py \
    --seeds 9000,9001,9008,9015,9017,9023,9026,9027,9028,9100,9101,9102,9104,9106,9109,9114,9120,9123,9124,9129 \
    --procs 10 --label w107-on-105group --out data/routewin/duel-w107.json
```

Artifacts: `scripts/route_groups.py`, `data/route/groups.json`, `scripts/build_route.py`,
`data/routewin/w{105,107,116,121,9,103,5,8,10,12,101,104,108,110,111,112,117,118,123,1,3,6,7}/main.py`,
`data/routewin/screen105.txt`, `data/routewin/duel-w*.json`, `/tmp/cells.json`
(the invalid dummy-agent capture, kept only to document §1).
