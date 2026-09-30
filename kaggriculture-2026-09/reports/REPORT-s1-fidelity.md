# S1 fidelity gates — 1a PASS, 1b FAIL (day 4 first negative, day 10 watershed −17,179)

Date: 2026-09-19. Base/instrument: paired games (the only valid instrument),
`scripts/day_gap.py` for the early gate, `scripts/lockstep.py` for the cash check.
Deliverables built in this round: `scripts/trace_ref.py`, `scripts/compile_plan.py`,
`scripts/plan_runtime.py`, `scripts/fidelity.py`, and the assets under `data/trace/` and
`data/plan/`. The live submitted files were not touched.

## 0. Gate summary

| gate | criterion | result |
|---|---|---|
| **1a pipeline lossless** | a trace-replay agent reproduces the actions **and** the observed state step-for-step | **PASS** — 719/719 actions, 719/719 state fingerprints (0 mismatches, 0 missing); 24/24 traced games have lockstep cash drift **0.00** coins |
| **1b early parity** | θ agent, 20 paired towns: first-9-days net-worth delta |t| < 2 **and** no >3,000 deficit jump on day 10 | **FAIL** — first negative on **day 4**, statistically real from day 6, and a **−17,179** day-10 jump (cand 6,284 vs base 23,463) |
| **1c residual localisation** | per action-type × day, what θ cannot reproduce + the missing concept | **delivered** (§3); the residual is entirely market-side and the causal chain is measured |
| **1d total** | delta ≥ −2% vs the champion over 60 paired towns | **not reached** (−157,833 on the gate-1b panel, and −95% on the single seed measured) |

**Verdict: the S1 target agent does not reach parity, and by the brief's own rule the run
stops at 1b with the 1c list as the deliverable.** The reason is narrow and fixable in
principle, but it is not an economic concept — see §4.

## 1. S1.1 traces (gate 1a)

`scripts/trace_ref.py` records, per step, the input side (money, market inventory/prices,
town shops, shed, seeds, per-unit inventories, compact tiles of **both** farms), the output
side (the full action plus the post-application state from replaying the action with the
engine's own `_apply_unit_action`), and the derived per-step executed units and cash.

* Acceptance: with the two-sided lockstep replay (both market lists — replaying our side
  alone over-prices the sales by 2.6–13.9k/game, because paired units raise the inventory
  twice as fast) the recomputed cash equals the engine's money exactly:
  **24/24 games, drift +0.00** (`data/trace/summary-{stack,champion}.json`).
  Two implementation traps worth recording: the rival's action is recorded *after* ours in
  each step, so the replay must run as a post-game pass; and HIRE/BUY_LAND costs need the
  real `hires_today` / quadrant count or the accounting is off by thousands.
* `--seeds 9000-9011` for the live stack and for the champion (24 games).

## 2. S1.2/S1.3 θ and the controller

`scripts/compile_plan.py` reduces a trace to θ; `data/plan/theta-9000.json` is the compiled
plan; every field in the S1.2 table is recoverable, and the recovery counts are:

| field | recovered | | field | recovered |
|---|---|---|---|---|
| `land_days` | 2 days (6, 11) | | `build[day]` | 5 days |
| `plant[day][quadrant]` | 55 day-quadrant cells | | `buy_animal[day]` | 9 days |
| `water_rule` (hours) | 23/24 | | `sell[day][item]` | 126 day-item lots |
| `fert_rule` (hours) | 21/24 | | `buy_feed[day][item]` | 28 day-item cells |
| `harvest_rule` (hours) | 24/24 | | `price_gate[item]` | 8 items |
| `cargo_rule` | 36 drops, max cargo tracked | | `hold_rule` | 11.07 lots/day |
| **added by me, absent from the table** | `hire[day]` **30 days**, `buy_land[day]` 2 days, `buy_seed[day][crop]` **35 cells** | | | |

`scripts/plan_runtime.py` builds two agents: `--mode theta` (priority unit policy + θ
market) and `--mode hybrid` (θ market + the trace's unit actions, used to isolate the
market representation from the routing).

## 3. Gate 1b measurement and 1c residual table

Seed 9000, single game: **hybrid 12,172 vs champion 191,842 (−179,670)**; full θ mode
**128 vs 188,271**. Gate 1b on 4 towns / 8 paired games (`data/plan/daygap-hybrid.json`):

| day | 0 | 3 | 4 | 5 | 6 | 8 | 9 | **10** | final |
|---|---|---|---|---|---|---|---|---|---|
| delta | −18 | +277 | **−6** | −98 | −381 | −1,195 | −1,419 | **−17,179** | −157,833 |
| cand | 319 | 1,021 | 1,352 | 1,431 | 2,241 | 2,564 | 3,626 | **6,284** | 8,763 |
| base | 337 | 743 | 1,359 | 1,529 | 2,622 | 3,759 | 5,045 | **23,463** | 166,596 |

**This is the plan_v0 signature reproduced**: first negative on **day 4**, watershed on
**day 10** with an ~8× jump (−17,179 here vs −16,276 for plan_v0), 0/8 positive days. So the
same failure mode that killed the from-scratch rebuild is reproduced by an agent whose
*unit* actions are lossless and whose θ market schedule is inferred from the champion
itself — which localises the failure to the representation, not the policy.

1c per action-type × day (champion ref vs θ hybrid agent, day groups 0-9 / 10-19 / 20-29):

| action | ref → θ | reading |
|---|---|---|
| MOVE, WATER, HARVEST, PLANT, CARE, FEED, PICKUP, PLACE, DROP, DIG, PASS, BUILD_* | identical in all three groups | the unit side is carried exactly (hybrid mode); in full θ mode these must be regenerated by a routing rule, which θ has **no field for** |
| **MKT_BUY_LAND** | 1/1/0 → **0/0/0** | **the day-10 watershed**: θ never buys land |
| **MKT_BUY_SEED** | 48/71/68 → **7/2/0** | seed orders collapse (units partly survive, which is why planting still happens) |
| **MKT_BUY_PRODUCT** (feed) | 36/24/16 → 10/10/8 | feed buys collapse |
| MKT_HIRE | 55/102/110 → 52/86/92 | hires mostly survive |
| MKT_SELL | 56/88/188 → 43/40/123 | lot merging loses the champion's per-hour split |

## 4. The missing concept: intra-day cash-gated sequencing (not an economic policy)

The causal chain is measured, not hypothesised: θ's market fields are **per-day multisets**
and the controller issues every buy at hour 0, *before* that day's sells have produced the
cash. The champion's plan interleaves sells and buys across the day, and its purchases are
cash-gated — so:

1. `BUY_LAND` (1,000–4,000 coins, the third quadrant) fails at hour 0 → **0 of 2 land
   purchases**, exactly the day-10 watershed (−17,179);
2. `BUY_SEED` falls from 48/71/68 orders to 7/2/0 and `BUY_PRODUCT` (feed) from 36/24/16 to
   10/10/8 — the same cash-before-sells cause;
3. the action-type table shows the unit side is otherwise lossless, so the entire 95%
   collapse is on the market representation, not on the farm policy.

Two further structural gaps, both verified by measurement: the S1.2 table contains **no
HIRE, no BUY_LAND and no BUY_SEED field at all** (dropping these produced a ~400-coin and
then a 0-coin agent — the farm cannot plant, hire or expand), and it contains **no movement
field**, while MOVE is 176,950 of the champion's ~240,000 unit actions per game (the brief
acknowledges this is meant to be a *rule*, but the rule is not in θ and the trace only
yields position sequences).

## 5. Judgement: can the representation reach parity?

**Not as specified.** The compression axis is wrong: θ reduces the plan to per-day counts,
but the plan's value is exactly its **intra-day ordering under a cash constraint** — which
day-level counts destroy. My measurement pins the cost of that specific loss at ~95% of the
champion's score (12,172 vs ~110k for the champion's own level), with the land purchase and
the seed/feed buys as the mechanism.

What would make θ viable, in the order the evidence supports:

1. **Market plan as an ordered, cash-gated sequence**: keep the per-hour order of
   sell/buy ops (or a rule that reproduces it: "sell the day's first lot at hour 1, buy land
   once cash ≥ 4,000, buy seeds every hour while the next hour's planting needs them").
   This is the single change that unlocks the day-10 gate;
2. add the missing op fields (hire, buy_land, buy_seed) — cheap, already compiled;
3. a routing field or a stronger nearest-job rule for MOVE (the largest action class);
4. replace the `price_gate` minimum-price scalar (currently `WOOL: 1`, i.e. no gate) with a
   rule tied to the projected price, which is the part S3 was meant to search.

So the explicit representation *can* carry this economy only if it is allowed to be a
scheduled program with a cash gate — at which point it is much closer to the tape it was
meant to replace, and the honest reading of S1 is: **the representation's compression, not
any missing economic concept, is what fails.** If S2 is authorised, I would start with (1) +
(2) and re-run gate 1b on the same 4 towns, since that is a ~40-minute experiment and the
day-4/day-10 signature is a sharp instrument.

## 6. Artifacts

* `scripts/trace_ref.py`, `data/trace/<agent>-<seed>/{trace.jsonl,summary.json}` (24 games),
  `data/trace/summary-{stack,champion}.json`, `data/trace/summary-all.txt`;
* `scripts/compile_plan.py`, `data/plan/theta-9000.json`;
* `scripts/plan_runtime.py`, `data/plan/agent-{hybrid,theta}-9000.py`;
* `scripts/fidelity.py`, `data/plan/gate1a-9000.json`, `data/plan/gate1c-9000.json`;
* `data/plan/daygap-hybrid.json`.

Nothing submitted to Kaggle; no live file modified.
