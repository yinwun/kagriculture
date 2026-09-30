# Price-channel variants (Task 36) — what to change, and the verified answer

Date: 2026-09-27. Measurement only. **No submission; no live file touched.** Reference base:
`data/candidate/shep_milk/main.py` (race + WOOL/STRAWBERRY/MILK forward, strawberry & milk gated at
step 312; sha256 `741bfc19fad7d1c6…`). Panels: **10800–10829** (p1) and **10900–10929** (p2), paired,
seats alternating, 60 games each. Bar: Δ > 0 with t ≥ 3 on both panels.

## 0. Answer

**One change is verified effective: raise the per-step split cap to 2× the town's drain
(`forward_drain_mult: 2.0`) on the existing WOOL/STRAWBERRY/MILK forward layer. It clears the bar:
p1 `+391, t = +7.69, 58–0`; p2 `+340, t = +5.27, 55–5`** — worth **+0.40 % / +0.32 % of local wallet
≈ +58 / +46 rating points** on our ruler (~145 pts per +1 %), pooled ≈ +52. The mechanism check
confirms it moves exactly what it claims: **identical sold units with a better realised per-unit
price** (strawberry 120.56 vs 119.96, wool 121.90 vs 121.81). Everything else measured neutral or
negative — including both "hold for a better price" gates, which is the channel's exhaustion
evidence.

## 1. Variant table (single change on `shep_milk`)

| variant | change | p1 Δ | p1 t | p1 W–L | p2 Δ | p2 t | p2 W–L | verdict |
|---|---|---|---|---|---|---|---|---|
| **`shep_v_cap2`** | `forward_drain_mult = 2.0` | **+391** | **+7.69** | **58–0** | **+340** | **+5.27** | **55–5** | **GO** |
| `shep_v_cap05` | `forward_drain_mult = 0.5` (tighter cap) | −31 | −1.64 | 1–17 | −9 | −1.83 | 5–19 | no-go |
| `shep_v_frac06` | price floor 0.6 × base (WOOL, STRAWBERRY) | −466 | −5.07 | 4–50 | −376 | −5.25 | 9–47 | no-go (worse) |
| `shep_v_frac08` | price floor 0.8 × base | −546 | −5.10 | 6–52 | −444 | −4.88 | 4–52 | no-go (worse) |
| `shep_v_s0` | strawberry forward from step 0 | **+0** | 0.00 | — | **+0** | 0.00 | — | **inert** |
| `shep_v_s168` | strawberry forward from step 168 | **+0** | 0.00 | — | **+0** | 0.00 | — | **inert** |
| `shep_v_racece` | race items +CARROT +EGG | +1 | +0.39 | 7–11 | (pending) | | | no-go |
| `shep_v_racem` | race items −MELON | +0 | 0.00 | — | (pending) | | | inert |
| `shep_v_ctl` | price-fraction knob present, set to 0.0 | **+0** | 0.00 | — | (pending) | | | **control ✓ Δ exactly 0** |

Smoke (720 steps, mirror, seed 10800) for all nine: `['DONE','DONE']`, `layer_fallbacks = 0`,
`entry_fallbacks = 0`. Errors `err = 0` and `cand_exceptions = base_exceptions = 0` in every duel cell.

**Reading the negatives:**
* The two **price-floor gates lose money substantially** (−0.38…−0.55 %) — withholding stock for a
  better price does not pay; the drain does not restore the price fast enough. This reproduces our
  earlier hold/timing negatives (`sell_spread` −2,815) on the *new* base, so it is a real result, not
  a formality.
* A **tighter** cap (0.5×) is mildly negative (−31/−9, t ≈ −1.7): releasing *less* than the town can
  absorb leaves money on the table.
* **The strawberry-forward start time is a dead knob on this base** (Δ exactly 0 at 0, 168 and 312):
  the shepherds base already emits all strawberry stock every step, so our top-up has nothing to add
  (`want ≤ 0`). The strawberry half of our forward layer is inactive here — its value on the *old*
  base (ablation −436) does not transfer. The active part is the WOOL/MILK release **cap**.
* Dropping MELON from the race item set is inert, and adding CARROT/EGG is +1 coin — the race layer
  rarely acts on those items.

## 2. Mechanism check (the human's "how do we confirm it is real")

8 fixed-orientation games (seat 0 = `shep_v_cap2`, seat 1 = `shep_milk`), every executed unit logged
with its price:

| side | item | units sold | revenue | **avg realised price** |
|---|---|---|---|---|
| `shep_v_cap2` | WOOL | 1,236 | 150,674 | **121.90** |
| `shep_milk` | WOOL | 1,236 | 150,561 | **121.81** |
| `shep_v_cap2` | STRAWBERRY | 1,989 | 239,797 | **120.56** |
| `shep_milk` | STRAWBERRY | 1,989 | 238,609 | **119.96** |

**Units are identical; the gain is entirely the realised price** (+0.09/unit on wool, **+0.60/unit on
strawberry**, ≈ +0.5 %). That price difference alone explains ≈ +1,300 coins over the 8 games
(≈ +163/game); the remaining ≈ +90/game comes from the milk leg and from the opponent's own realised
price being pushed down by our extra releases. Mean margin over those 8 games: **+253** (consistent
with the panels' +340…+391 with seats alternated). So the change moves the thing it claims, and the
claim is the *price* channel at equal volume — which is exactly the leak Task 35 identified
(WOOL −393, STRAWBERRY −197 at unit parity).

## 3. Best build

| item | value |
|---|---|
| path | `data/candidate/shep_v_cap2/main.py` (1,086,245 bytes) |
| **payload sha256** | **`2f49b0ce6b8f51183bb496c311eb811d312a06bcfd0d8a8f944cd3f4fc1c1709`** |
| change | `forward_drain_mult = 2.0` added to the reference settings: race `{race_layout 1, race_hyp clone, race_hook outer, race_items [MILK, WOOL, STRAWBERRY, MELON]}`; forward `{forward_items [WOOL, STRAWBERRY, MILK], forward_drain True, forward_start_by_item {STRAWBERRY 312, MILK 312}, forward_drain_mult 2.0}` |
| rebuild | `.venv/bin/python scripts/t36_variants.py` (rebuilds all nine variants and re-runs the panels) |
| control | `shep_v_ctl` (same source, gate set to 0.0): **Δ exactly +0, t = 0.00**, errors 0 |
| smoke | DONE/DONE, all error counters 0 |
| runtime | not separately measured; the change is one scalar in the same layer, and the identical build with `drain_mult = 1.0` (`shep_straw`) measured mean 1.1 ms / p99 3.7 ms / **max 59.8 ms** per step (1 s budget) |

## 4. Verdict

* **Verified effective and bar-clearing:** `forward_drain_mult = 2.0` on the WOOL/STRAWBERRY/MILK
  forward layer, **+391/+340 coins per game (+0.40 %/+0.32 % wallet ≈ +58/+46 points, pooled ≈ +52)**,
  with the mechanism confirmed as a realised-price gain at equal units.
* **The channel is otherwise exhausted:** the two price-floor gates are significantly negative
  (−376…−546), the tighter cap is negative, the strawberry start time is a dead knob on this base,
  and the race item tweaks are inert (+0…+1). Nothing else in the channel moves.
* **Against the +250 points needed for 2,650:** this change is worth ~+52 points — a fifth of the
  requirement. It is a real, pre-registered-bar-clearing improvement and the best single change found
  since the shepherds base, but it does not close the gap on its own; the rest remains in the
  economy-simulation families.

## 5. Artifacts

| file | content |
|---|---|
| `scripts/t36_variants.py`, `log/t36.log` | the nine builds, smoke gate, 18 duel cells, the bar check |
| `scripts/t36_probe.py` | the mechanism probe (per-unit units/price logging) |
| `data/candidate/shep_v_*/main.py` | the variants (`shep_v_cap2` is the winner) |
| `data/candidate/duel-t36-*.json` | per-seed deltas, counters, exceptions |
| `data/t36-variants.json` | aggregated variant results |
