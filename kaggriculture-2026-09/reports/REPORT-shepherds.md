# Shepherds-ledger validation (Task 33) — the candidate clears, and our layers stack on it

Date: 2026-09-25. Measurement only. **No submission; no live file touched.**
Target: `the-shepherds-ledger-herd-safe-sovereign` (extracted offline, our tape blob
`54fe156ea7206e38`, declared sha256 `ae44d83b…` verified) vs our current best
`data/composite/comp_straw/main.py`.

## 0. Verdict

**The candidate clears the pre-registered bar, and our market layers stack on it additively.**
Four panels, 180 towns: the candidate beats `comp_straw` by **+363 pooled (t = +4.84), 115/180 towns
positive (63.9 %)**, with the two new high-power panels at **+409 (t = 3.26)** and **+379
(t = 3.44)**. Stacking our race + wool + late-strawberry layers on it as the outermost wrapper gives
**+792 (t = 10.32, 115–5)** and **+857 (t = 13.43, 119–1)** on the same two panels — the largest
measured improvement of this project — and the our-layers contribution (+383…+478) is **nearly
exactly additive** with the candidate's own gain, so the two are not redundant despite acting in the
same channel family.

## 1. Two new high-power panels (step 1)

`ab_duel.py`, paired, seats alternating; N towns → 2N games.

| panel | seeds | towns | games | Δ wallet | Δ % | t | W–L | cand / base wallet | exc | err |
|---|---|---|---|---|---|---|---|---|---|---|
| p3 | 10200–10259 | 60 | 120 | **+409** | +0.39 % | **+3.26** | 81–39 | 104,325 / 103,916 | 0/0 | 0 |
| p4 | 10300–10359 | 60 | 120 | **+379** | +0.38 % | **+3.44** | 75–45 | 99,651 / 99,272 | 0/0 | 0 |

**Bar (Δ > 0 with t ≥ 3 on BOTH panels): CLEARED.**

## 2. Pooled four-panel estimate (step 2)

| panel | towns | Δ | t | positive towns |
|---|---|---|---|---|
| p1 9900–9929 | 30 | +360 | +1.38 | 20/30 |
| p2 10100–10129 | 30 | +239 | +1.48 | 17/30 |
| p3 10200–10259 | 60 | +409 | +3.26 | 41/60 |
| p4 10300–10359 | 60 | +379 | +3.44 | 37/60 |
| **pooled** | **180** | **+363** | **+4.84** | **115/180 = 63.9 %** |

Median +264, min −3,468, max +4,937. The per-panel t values rise with panel size while the effect size
stays flat (+0.25…+0.39 %), which is what a real small edge looks like; the pooled t = +4.84 on a
63.9 % positive-town fraction is the strongest evidence we have that a public build beats ours.

## 3. Stack: candidate + our market layers (step 3, only because the bar cleared)

Built with the usual outermost mechanism on top of the candidate source (our race layer via
`build_race` with `base_path=` the candidate and `outer_prefix="_clr"`, then the drain-capped forward
layer with `forward_items=["WOOL","STRAWBERRY"]`, `forward_start_by_item={"STRAWBERRY": 312}`), all
collision-guarded:

```bash
.venv/bin/python scripts/t33_stack.py          # -> data/candidate/shep_straw/main.py
```

| item | value |
|---|---|
| payload path | `data/candidate/shep_straw/main.py` (1,085,862 bytes) |
| **payload sha256** | **`e1bb61d1caea1783d588076c9ef9dd998504434e841cbc7ec3e38216a650631f`** |
| race-only intermediate | `data/candidate/shep_straw_raceonly/main.py` (`b7aa3185d6d6…`) |
| knobs-off control | `data/candidate/shep_straw_ctl/main.py` (`800a55622cfc…`) |

**Smoke (720 steps, mirror):** `['DONE', 'DONE']`, rewards 151,291 / 151,291, and **every error
counter 0** (`layer_fallbacks`, `entry_fallbacks`, `terminal_rescue_errors`, `v28_entry_errors`,
`production_errors`, `v31_entry_errors`), with our layers demonstrably active (`race_tried` 510,
`race_considered` 18, `forward_orders` 58).

**Control:** knobs-off build vs race-only build → **Δ = +0, t = 0.00, errors 0, exceptions 0** (the
added code is provably inert when off).

**Duels of the stack vs `comp_straw` on the same two unused panels:**

| panel | Δ | Δ % | t | W–L | cand / base wallet | exc | err |
|---|---|---|---|---|---|---|---|
| p3 10200–10259 | **+792** | +0.77 % | **+10.32** | 115–5 | 104,307 / 103,515 | 0/0 | 0 |
| p4 10300–10359 | **+857** | +0.87 % | **+13.43** | 119–1 | 99,573 / 98,716 | 0/0 | 0 |

**Runtime** (`scripts/composite_timing.py`, 1,438 calls/game, `actTimeout = 1 s`): mean 1.1 ms,
p95 1.9 ms, p99 3.7 ms, **max 59.8 ms**, zero steps > 250 ms, 4.1 s per game — ~17× headroom at the
worst step.

## 4. What its layers do, and additive or overlapping? (step 4)

Action-mix diff (candidate − `comp_straw`, p4): **`MKT_SELL` −5,808**, `PASS` −1,826, `DROP` +140,
`FERTILIZE` −342, `MOVE` +986, `WATER` +302. So the candidate's distinguishing behaviour is **far
fewer SELL market orders for the same volume** — consolidated selling — i.e. it acts on the
**sell-timing / order-layout channel**, the same family as our race and forward layers. Its own
counters confirm it runs its own lockstep-style machinery (`RACE_race_clone_turns` 52,420,
`RACE_cs_rewrites` 92) and it does **not** contain our code (`race_tried`/`forward_orders` absent from
its diagnostics).

Yet the measured gains are **additive, not overlapping**: candidate alone +409 (p3) / +379 (p4); the
stack +792 / +857, so our layers contribute ≈ **+383 / +478** on top of it — very close to the
+324…+590 they contribute on our own base. Reading: the candidate changes *how many* sell orders it
emits (consolidating lots), while ours changes *which slot* each lot takes (race) and *when stock is
released* (forward) — different sub-mechanisms inside one channel, which is why they compose.

## 5. One-line verdict

**Adopt it — and adopt the stack, not the candidate alone.** `the-shepherds-ledger-herd-safe-sovereign`
is the first public build that beats our line on a pre-registered, two-panel, t ≥ 3 test (pooled
+363, t = +4.84, 63.9 % of towns), and `shep_straw` (that build + our three market layers, outermost)
is strictly better on both new panels (+792/+857, t = 10.3/13.4) with a clean smoke, a Δ = 0 control,
zero errors and 60 ms worst-step runtime. **At T-3, submit `data/candidate/shep_straw/main.py`**
(sha256 `e1bb61d1caea1783d588076c9ef9dd998504434e841cbc7ec3e38216a650631f`) rather than re-posting
`comp_straw`; the usual caveat stands that no local-wallet → ladder-rating map has ever been measured.

## 6. Artifacts

| file | content |
|---|---|
| `scripts/t33_validate.py`, `log/t33.log` | the four-panel validation and pooling |
| `scripts/t33_stack.py`, `log/t33-stack.log` | stack build, collision guard, smoke, control, duels, runtime |
| `data/candidate/shep_straw/main.py` | **the stacked build** (sha256 above) |
| `data/candidate/shep_straw_ctl/main.py`, `shep_straw_raceonly/main.py` | control and intermediate |
| `data/composite/duel-t33-shepherds-{p3,p4}.json` | candidate-alone panels |
| `data/candidate/duel-t33-stack-{p3,p4}.json`, `duel-t33-ctl.json` | stack panels and control |
| `data/candidate/timing-t33.json` | per-step runtime |
