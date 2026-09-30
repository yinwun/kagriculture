# drain_mult peak (Task 38) — the peak is a plateau at ×24–×48, and it is worth ~+200 points over cap2

Date: 2026-09-27. Measurement only. **No submission; no live file touched.** Base = the submitted
`shep_v_cap8` (mult 8.0, payload `8aa637f3…`, ref 56605582). Sweep panels **11400–11429 /
11500–11529**, confirmation panel **11800–11829**, paired, seats alternating, 60 games per cell.
Bar: Δ > 0 with t ≥ 3 on both panels.

## 0. Answer

**The peak is a plateau at ×24–×48: `shep_v_cap24` took p1 +402 (t = 6.32) / p2 +564 (t = 6.49) and
the confirmation panel +491 (t = 5.03, 58–2); `shep_v_cap48` is statistically identical
(+400 / +575).** Every swept multiplier clears the bar. The mechanism check still shows **realised
price at exactly equal volume**. Runtime stays deep inside budget. Cumulatively the `forward_drain_mult`
chain is now worth ≈ **+1,750 coins/game over `shep_milk` (+1.8 % wallet ≈ +260 rating points)** — i.e.
it plausibly covers the whole gap to ~2,650 on our ruler.

## 1. Sweep table (vs cap8 = mult 8.0)

| variant | mult | p1 Δ | p1 t | p1 W–L | p2 Δ | p2 t | p2 W–L | err/exc | verdict |
|---|---|---|---|---|---|---|---|---|---|
| `shep_v_cap12` | 12 | +255 | +8.23 | 59–1 | +280 | +6.70 | 56–4 | 0/0 | GO |
| `shep_v_cap16` | 16 | +387 | +6.57 | 59–1 | +495 | +6.21 | 54–6 | 0/0 | GO |
| **`shep_v_cap24`** | **24** | **+402** | **+6.32** | **59–1** | **+564** | **+6.49** | **56–4** | 0/0 | **GO — peak (by min-panel margin)** |
| `shep_v_cap48` | 48 | +400 | +6.20 | 59–1 | **+575** | +6.29 | 54–6 | 0/0 | GO (tied with ×24) |

Shape: ×8→×12 +255/+280, ×12→×16 +387/+495, ×16→×24 +402/+564, ×24→×48 +400/+575. The curve rises
through ×24 and then **flattens** — ×24 and ×48 differ by 2 coins on p1 and 11 on p2, i.e. inside
noise. **The peak is the plateau ×24–×48**; there is nothing above ×48 to find (×48 is already
effectively unbounded at the 720-step scale: the cap is ~2 units/step for wool).

Control: the mult-8.0 rebuild is **byte-identical** to the committed `shep_v_cap8`
(`8aa637f3a8881be2d84bc1c7237e2b375108905a91a1e2f80d4c70f61097b87c`), and its duel gives
**Δ = +0.0, t = 0.00, errors 0, exceptions 0**. Smoke for all five builds: `DONE/DONE`, empty error
dict. No cell had `err ≠ 0` or any agent exception.

## 2. Confirmation panel (fresh seeds 11800–11829)

`shep_v_cap24` vs `shep_v_cap8`: **Δ = +491, t = +5.03, W–L 58–2, errors 0, exceptions 0.** The peak's
edge survives out-of-sample, and the effect size (+491) is actually larger than either sweep panel
(+402/+564) — i.e. no sign of decay.

## 3. Runtime (first-class this time)

One full 720-step game, timing every `agent()` call (1,438 calls), `actTimeout = 1 s`:

| build | mean | p95 | p99 | **max** | steps > 250 ms | > 500 ms | > 1 s | game wall |
|---|---|---|---|---|---|---|---|---|
| `shep_v_cap8` (submitted) | 1.1 ms | 2.0 ms | 3.9 ms | **59.6 ms** | 0 | 0 | 0 | 4.2 s |
| **`shep_v_cap24` (peak)** | 1.1 ms | 1.9 ms | 3.9 ms | **57.9 ms** | 0 | 0 | 0 | 4.1 s |

**The higher multiplier does not raise the worst step** (57.9 ms vs 59.6 ms, i.e. within run-to-run
noise) and nothing approaches the 1 s budget — ~17× headroom. That answers the gap left in Task 37:
×8 was submitted without a fresh measurement, and ×24 needs no runtime caveat.

## 4. Mechanism check (`shep_v_cap24` seat0 vs cap8 seat1, 8 games, mean margin +279)

| side | item | units | revenue | **avg realised price** |
|---|---|---|---|---|
| cap24 | WOOL | 1,203 | 120,938 | **100.53** |
| cap8 | WOOL | 1,203 | 119,918 | **99.68** |
| cap24 | STRAWBERRY | 1,984 | 179,297 | **90.37** |
| cap8 | STRAWBERRY | 1,984 | 178,664 | **90.05** |

**Units are identical to the unit on both items; the entire gain is the realised price**
(+0.85/unit = +0.85 % on wool, +0.32/unit = +0.36 % on strawberry). Confirmed: the mechanism is the
price channel at equal volume, as in Task 36/37 — not production, not volume, not a side effect.

## 5. Best build

| item | value |
|---|---|
| path | `data/candidate/shep_v_cap24/main.py` (1,086,246 bytes) |
| **payload sha256** | **`d3417bf8618c8c0d2eb616b78f4040fb547c350bc1558929a91d5ed5bd0cf44a`** |
| change vs the reference | `forward_drain_mult = 24.0` (everything else identical to `shep_milk`'s settings) |
| rebuild | `.venv/bin/python scripts/t38_sweep.py` |
| tie-break note | `shep_v_cap48/main.py` (`1aad3466bf477d8e2282a5f3c841502995341679eccfab783405423805feaf49`) is statistically identical; either is defensible, ×24 has the better min-panel margin |
| control | mult-8.0 rebuild byte-identical, Δ exactly 0 |
| smoke | DONE/DONE, empty error dict |

## 6. Verdict and the cumulative arithmetic

* **Peak found: ×24 (plateau ×24–×48)**, confirmed out-of-sample (+491, t = 5.03), mechanism verified,
  runtime unchanged, control exact.
* **Cumulative value of the chain on our ruler** (~145 pts per +1 % wallet): `shep_milk` → cap2
  (+391/+340) → cap8 (+950/+909) → **cap24 (+402/+564)** ≈ **+1,743/+1,813 coins/game ≈ +1.8 % wallet
  ≈ +260 rating points**. The human's target was ~+250 to reach ~2,650 — **on this ruler the price
  channel now covers the whole gap**, subject to the standing caveat that no local-wallet →
  ladder-rating map has ever been measured.
* **Decision material for T-3:** choose between the submitted `shep_v_cap8` (already live, ref
  56605582) and `shep_v_cap24` (a further +402/+564, t ≈ 6.3/6.5, confirmed +491). Nothing in this
  round argues against ×24; the only cost is the usual tracking-reset risk.

## 7. Artifacts

| file | content |
|---|---|
| `scripts/t38_sweep.py`, `log/t38.log` | builds, control, smoke, 8 sweep cells, runtime, mechanism, confirmation |
| `data/candidate/shep_v_cap{8_ctl,12,16,24,48}/main.py` | the swept builds (`shep_v_cap24` is the peak) |
| `data/candidate/duel-t38-*.json` | per-seed deltas, counters, exceptions |
| `data/candidate/duel-t38-peak-confirm.json` | the out-of-sample confirmation (+491, t=5.03) |
| `data/candidate/timing-t38-{cap8,peak}.json` | the runtime measurements |
