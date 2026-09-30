# drain_mult sweep (Task 37) — the price channel is still rising at ×8

Date: 2026-09-27. Measurement only. **No submission; no live file touched.** Base = the submitted
`shep_v_cap2` (mult 2.0, payload `2f49b0ce…`, ref 56604670). Panels **11000–11029 / 11100–11129**,
paired, seats alternating, 60 games each. Bar: Δ > 0 with t ≥ 3 on both panels.

## 0. Answer

**No peak found: the channel keeps improving monotonically from ×2 to ×8.** All four multipliers clear
the bar, and the best measured is **`shep_v_cap8` (mult 8.0): p1 `+950, t = +8.83, 59–1`;
p2 `+909, t = +13.38, 60–0`** — **+1.06 % / +0.92 % of local wallet ≈ +154 / +133 rating points**
(~145 pts per +1 %), pooled ≈ **+143 points over the submitted cap2**. The mechanism check still shows
**equal units and a better realised price**, so the gain remains the price channel, not a different
effect. The peak lies at mult > 8 and needs one more sweep round (`12 / 16 / 24 / effectively
unbounded`).

## 1. Sweep table (all cells, vs cap2 = mult 2.0)

| variant | mult | p1 Δ | p1 t | p1 W–L | p1 wallets | p2 Δ | p2 t | p2 W–L | p2 wallets | verdict |
|---|---|---|---|---|---|---|---|---|---|---|
| `shep_v_cap3` | 3.0 | **+402** | +8.21 | 58–2 | 89,554 / 89,152 | **+335** | +9.01 | 59–1 | 99,223 / 98,887 | GO |
| `shep_v_cap4` | 4.0 | **+567** | +9.37 | 59–1 | 89,626 / 89,059 | **+533** | +12.32 | 60–0 | 99,304 / 98,771 | GO |
| `shep_v_cap6` | 6.0 | **+784** | +9.10 | 59–1 | 89,663 / 88,879 | **+800** | +13.91 | 60–0 | 99,412 / 98,612 | GO |
| **`shep_v_cap8`** | **8.0** | **+950** | **+8.83** | **59–1** | 89,721 / 88,771 | **+909** | **+13.38** | **60–0** | 99,421 / 98,512 | **GO — best measured** |

`err = 0` and `cand_exceptions = base_exceptions = 0` in every cell. Smoke (720 steps, mirror, seed
11000) for all five builds: `['DONE','DONE']` with an **empty error dict** (no `*_fallbacks`,
no `*_errors`).

**Control (byte-identity + Δ):** rebuilding mult 2.0 with the same builder reproduces the committed
`shep_v_cap2` **byte-for-byte** (`sha256 2f49b0ce6b8f51183bb496c311eb811d312a06bcfd0d8a8f944cd3f4fc1c1709`
for both), and the control duel gives **Δ = +0.0, t = 0.00, errors 0, exceptions 0**.

**Shape of the curve:** ×1→×2 gave +391/+340 (Task 36), ×2→×3 +402/+335, ×3→×4 +567/+533, ×4→×6
+784/+800, ×6→×8 +950/+909. Increments are still growing in absolute terms (Δ per unit of mult is
flattening but the level has not turned), so **the peak is above 8** — the old-base observation that
the unbounded case was worse has not yet been reached on this base.

## 2. Mechanism check (`shep_v_cap8` vs cap2, 8 games, mean margin +1,571)

| side | item | units | revenue | **avg realised price** |
|---|---|---|---|---|
| `shep_v_cap8` | WOOL | 1,629 | 205,473 | **126.13** |
| cap2 | WOOL | 1,629 | 201,862 | **123.92** |
| `shep_v_cap8` | STRAWBERRY | 1,980 | 148,739 | **75.12** |
| cap2 | STRAWBERRY | 1,969 | 145,610 | **73.95** |

**Units are equal on wool and +0.6 % on strawberry; the gain is the realised price** (+2.21/unit on
wool = +1.8 %, +1.17/unit on strawberry = +1.6 %). Over the 8 games that price difference is
≈ +3,600 + 2,300 ≈ 5,900 coins of the +12,600 total margin (the rest is the milk leg and pushing the
opponent's realised price down). So the change still moves exactly the price channel at equal volume —
consistent with Task 35's diagnosis (WOOL −393 and STRAWBERRY −197 at exact unit parity).

## 3. Best build

| item | value |
|---|---|
| path | `data/candidate/shep_v_cap8/main.py` (1,086,245 bytes) |
| **payload sha256** | **`8aa637f3a8881be2d84bc1c7237e2b375108905a91a1e2f80d4c70f61097b87c`** |
| change vs the reference | `forward_drain_mult = 8.0` (from 2.0); everything else identical to `shep_milk`'s settings |
| rebuild | `.venv/bin/python scripts/t37_sweep.py` (rebuilds 2.0/3/4/6/8, re-runs the panels, re-does the control and the probe) |
| control | mult 2.0 rebuild **byte-identical** to the submitted cap2, duel Δ exactly 0 |
| smoke | DONE/DONE, empty error dict |
| runtime | not re-measured for ×8; the change is one scalar in the same code path. The identical layer at mult 1.0 measured mean 1.1 ms, p95 1.9 ms, p99 3.7 ms, **max 59.8 ms** per step against the 1 s `actTimeout` (zero steps > 250 ms). A higher cap can only add a few orders per step, so the margin is expected to hold — but it should be re-measured before any submission of ×8 |

## 4. Verdict

* **Every swept multiplier clears the bar; the best is ×8 (+950/+909, t = 8.8/13.4).** The gain is
  +143 points over the currently submitted cap2, and the mechanism is confirmed as the realised-price
  channel at equal volume.
* **The peak is not in this set.** The curve is still rising at ×8, so the next round should sweep
  `12 / 16 / 24 / 1e9 (effectively unbounded)` against ×8 on fresh panels before choosing a final
  build — the old-base result that "unbounded is worse" makes the true optimum somewhere above 8
  worth locating, and it is cheap (one more sweep).
* **Against the +250-point target:** cap2 (submitted) was ≈ +52 points over `shep_milk`; cap8 is
  ≈ +143 points over cap2, i.e. **≈ +195 points over `shep_milk` cumulatively** — most of the way to
  the +250 the human wanted, and it may go further above ×8. If the ×8 build holds up on a
  confirmation panel and the runtime check passes, it is the strongest T-3 candidate we have.

## 5. Artifacts

| file | content |
|---|---|
| `scripts/t37_sweep.py`, `log/t37.log` | the five builds, byte-identity control, smoke gate, 8 duel cells, the bar check, the mechanism probe |
| `data/candidate/shep_v_cap{2_ctl,3,4,6,8}/main.py` | the swept builds (`shep_v_cap8` is the best) |
| `data/candidate/duel-t37-*.json` | per-seed deltas, counters, exceptions |
| `data/candidate/duel-t37-ctl.json` | the control duel (Δ exactly 0) |
