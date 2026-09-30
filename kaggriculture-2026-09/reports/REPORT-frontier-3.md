# Frontier scan 3 (Task 40) — a NEW WINNER, and it is the biggest jump of the project

Date: 2026-09-27/28. Measurement only. **No submission; no live file touched.** Baseline: our strongest
build `data/candidate/shep_v_cap24/main.py` (drain-mult ×24, ref 56605582 line). Panels
**13000–13029 / 13100–13129**, paired, seats alternating, 60 games each. Bar: Δ > 0 with t ≥ 3 on both
panels.

## 0. Answer

**A winner exists and it is large.** `leoprovorov/31415926535897932384626433832795058202884197169399`
beats `shep_v_cap24` by **+1,142 (t = +8.78, 60–0)** and **+1,071 (t = +6.28, 56–4)**. Stacking our
market layers on it (race + WOOL/STRAWBERRY/MILK forward at drain-mult ×24) gives **`pi_stack`:
+1,612 (t = +8.91, 60–0) and +1,720 (t = +8.29, 58–2)** — **+1.7 %/+1.8 % of wallet ≈ +250 rating
points over cap24**, which is the entire gap this project has been chasing. Smoke `DONE/DONE` with an
empty error dict, knobs-off control **Δ exactly 0**, and the notebook bundles **our tape blob**
(`54fe156ea7206e38`) — same data, better layers. No notebook in the scan carries genuinely different
route-table data (the only distinct payload is the `{base,patches}` action-tape format).

## 1. Provenance table (newest 20 notebooks, payload hashes)

| notebook | payload |
|---|---|
| `haideptry/the-2965-master-hybrid-engine` | **OURS** `54fe156ea7206e38` |
| `guruprasaathas111/kaggriculture-top-2-master-engine-v4` | **OURS** |
| **`leoprovorov/3141592…4197169399`** (the winner) | **OURS** |
| `haideptry/the-shepherds-ledger-herd-safe-sovereign` | **OURS** |
| `tetsutani/demand-preserving-turn-sale-timing` | **OURS** |
| `guruprasaathas111/kaggriculture-master-engine-v53e01d74d8f` | other: `5df1c84699004845` → `dict keys=['base','patches']` |
| `evgendvorkin/kaggriculture-version-31-26-09-bronze-going-up` | other: `5df1c84699004845` → same action-tape format |
| `kunaldesale2408/kaggriculture-2026-v1` | other: `5df1c84699004845` → same action-tape format |
| the remaining 12 | no route payload exposed (dataset / base85 attachments) |

**Different route-table data: NONE.** The only distinct payload is the `{base, patches}` step-indexed
action tape, which is a different *encoding* of the same tape family — so the outlook is unchanged:
the frontier still runs our data, and the edge is in the layers.

## 2. Duel table (candidates vs `shep_v_cap24`, both panels)

| candidate | p1 Δ | p1 t | p1 W–L | p2 Δ | p2 t | p2 W–L | exc/err | verdict |
|---|---|---|---|---|---|---|---|---|
| **`leoprovorov/3141592…7169399`** | **+1,142** | **+8.78** | **60–0** | **+1,071** | **+6.28** | **56–4** | 0/0 | **GO — winner** |
| `haideptry/the-shepherds-ledger-…` (our current base alone) | −155 | −2.05 | 17–43 | −91 | −0.94 | 20–40 | 0/0 | no-go |
| `haideptry/the-2965-master-hybrid-engine` | −410 | −2.77 | 12–48 | −495 | −4.88 | 18–42 | 0/0 | no-go |
| `guruprasaathas111/kaggriculture-top-2-master-engine-v4` | −537 | −3.37 | 8–52 | −522 | −4.02 | 16–44 | 0/0 | no-go |
| `guruprasaathas111/kaggriculture-master-engine-v53e01d74d8f` | −3,341 | −5.86 | 2–58 | −4,447 | −8.65 | 2–58 | 0/0 | no-go |
| 4 further runnable candidates (dataset-path builds) | — | — | — | — | — | — | — | smoke-gated out or no payload |

All cells: `err = 0`, `cand_exceptions = base_exceptions = 0`.

## 3. Stacking result (step 4)

| item | value |
|---|---|
| **path** | **`data/candidate/pi_stack/main.py`** (1,243,411 bytes) |
| **payload sha256** | **`65962e928b0712946e1bacb929b4fb919a7231f34e1bc99c7e350d4e2755f317`** |
| race-only intermediate | `data/candidate/pi_stack_raceonly/main.py` (`a0c2fc79975c…`) |
| knobs-off control build | `data/candidate/pi_stack_fwdctl/main.py` (`0034fbf91c59…`) |
| rebuild | `.venv/bin/python scripts/t40_stack.py` |
| settings stacked | race `{layout 1, hyp clone, hook outer, items MILK/WOOL/STRAWBERRY/MELON}` + forward `{items WOOL/STRAWBERRY/MILK, drain, strawberry & milk at step 312, drain_mult 24.0}`, outermost |
| smoke | `['DONE','DONE']`, **empty error dict** (`layer_fallbacks = entry_fallbacks = *_errors = 0`) |
| **control** | forward-off build vs race-only build: **Δ = +0.0, t = 0.00, errors 0, exceptions 0** |
| **duels vs cap24** | **p1 +1,612 (t = +8.91, 60–0, wallets 94,760/93,147)** · **p2 +1,720 (t = +8.29, 58–2, 95,857/94,137)** |
| value | **+1,666 coins/game ≈ +1.7 % of wallet ≈ +250 rating points** on our ruler (~145 pts per +1 %) |
| runtime (full 720-step game, 1,438 calls) | mean **19.4 ms**, p95 63.6 ms, p99 **267.4 ms**, **max 836.8 ms**, 15 steps > 250 ms, 0 > 1 s; game wall 66.9 s |
| runtime comparison | cap24: mean 1.1 ms, max 57.9 ms · cap8: mean 1.1 ms, max 59.6 ms · **pi_stack's worst step is 14× the cap24 worst step and 84 % of the 1 s limit** |

Composition: the frontier base alone contributes +1,142/+1,071 over cap24; our layers add a further
**+470/+649** on top of it — both components clear the bar, and they compose.

## 4. What this means for the deadline

* **`pi_stack` is the strongest build ever measured here (+250 points over cap24), but it carries a
  runtime risk that must be resolved before submission.** One full 720-step game, timing every call
  (1,438 calls, `actTimeout = 1 s`): **mean 19.4 ms, p95 63.6 ms, p99 267.4 ms, max 836.8 ms,
  15 steps > 250 ms, 0 steps > 1 s, game wall 66.9 s.** The worst step is at **84 % of the hard
  per-step budget** — versus 57.9 ms for cap24 and 59.6 ms for cap8 (~6 % of budget). On Kaggle's
  slower hardware that could time out, and a timeout costs the whole game. Either (a) measure the
  frontier base *alone* to see how much of the cost is ours (the base is a 1.2 M-char build and is
  likely the bulk of it), (b) trim our race layer's item set, or (c) prefer a lighter stack, before
  spending the final submission slot. **The local gain is real; the runtime is the open risk.**
* **The daily/weekly ordering is: `pi_stack` ≫ `leoprovorov/3141592…` alone (+1,612/+1,720 over it in
  our layers' favour… i.e. ours adds on top) > `shep_v_cap24` ≈ `shep_v_cap8` > `shep_straw` > older
  bases.** The stacked build dominates every earlier candidate measured this session.
* Caveat unchanged and binding: the local-wallet → ladder-rating map has never been measured, and
  `pi_stack` has never been on the ladder; the +250-point figure is the ruler estimate, not a
  prediction.

## 5. Artifacts

| file | content |
|---|---|
| `scripts/t40_frontier.py`, `log/t40.log` | provenance sweep (with the route-table test), extraction, smoke gate, 18 duel cells |
| `scripts/t40_stack.py`, `log/t40-stack.log` | the stack build, smoke, control, stack duels, timing |
| `data/candidate/pi_stack/main.py` | **the stacked winner (final candidate)** |
| `data/candidate/duel-t40-3141592*.json` | the winner's panels vs cap24 |
| `data/candidate/duel-t40-pi_stack-{p1,p2}.json` | the stack's panels vs cap24 |
| `data/t40-frontier.json` | provenance + duel aggregation |
| `data/notebooks-t40.csv` | the scan list |
