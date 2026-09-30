# Direct contrast (Task 39) — the transitive +1.85 % does NOT survive; the direct effect is +0.64 %

Date: 2026-09-27. Measurement only. **No submission; no live file touched.** Direct end-to-end duels of
`shep_v_cap24` and `shep_v_cap8` against the ×1 baseline `data/candidate/shep_straw/main.py`, on fresh
panels **12000–12029 / 12100–12129** (60 towns each), paired, seats alternating. This is the exact
contrast the matched live pair (ARM A = ×1, ARM B = ×24) will test.

## 0. Answer

**The direct measurement contradicts the transitive +1.85 %.** Measured end-to-end on the same panels,
`cap24` beats `shep_straw` by **+623 (p1) / +638 (p2), pooled +630 coins/game over 60 towns, t = +6.55,
95 % CI [+442, +819] = +0.64 % of wallet ≈ +95 rating points [CI +67…+123]**, with 50/60 towns positive.
The transitive chain (cap2 → cap8 → cap24 increments summed on *different* panels against *different*
bases) predicted ≈ +1.8 % ≈ +260 points; the honest end-to-end figure is **+0.64 % ≈ +95 points**, so the
transitive arithmetic **overstated the effect by ~2.8×**. `cap8` is close behind and statistically
similar: **+496/+634, pooled +565, t = +6.36, CI [+391, +740] = +0.59 % ≈ +85 points [CI +59…+111]**,
49/60 towns positive.

**Both arms clear the pre-registered bar (Δ > 0, t ≥ 3 on both panels). The mechanism is confirmed:
realised price on WOOL and STRAWBERRY at exactly equal units; MILK contributes nothing.** For the live
pair, **×24 is the marginally better arm, but ×8 is the safer choice for a first experiment** — see §4.

## 1. Direct deltas vs `shep_straw` (×1)

| arm | panel | Δ | Δ % | t | W–L | cand / base wallet | exc | err |
|---|---|---|---|---|---|---|---|---|
| **cap24** | p1 12000–12029 | **+623** | +0.65 % | **+4.20** | 47–13 | 96,931 / 96,308 | 0/0 | 0 |
| **cap24** | p2 12100–12129 | **+638** | +0.64 % | **+5.09** | 50–10 | 100,893 / 100,255 | 0/0 | 0 |
| cap8 | p1 12000–12029 | **+496** | +0.51 % | **+3.60** | 46–14 | 96,953 / 96,457 | 0/0 | 0 |
| cap8 | p2 12100–12129 | **+634** | +0.63 % | **+5.60** | 48–12 | 100,899 / 100,265 | 0/0 | 0 |

Pooled with confidence intervals (towns as the unit):

| arm | pooled Δ | t | 95 % CI (coins) | 95 % CI (rating points) | positive towns |
|---|---|---|---|---|---|
| **cap24** | **+630** | **+6.55** | [+442, +819] | **[+67, +123]** | 50/60 |
| cap8 | +565 | +6.36 | [+391, +740] | [+59, +111] | 49/60 |

**Corrected local ranking (with CIs):** `cap24 ≈ cap8` — the difference between them (+65 coins,
≈ +10 points) is far inside both intervals; the ×24-vs-×8 contrast is *not* resolved by this round
(earlier it measured +402/+564 in ×24's favour; on these panels the two arms are indistinguishable).
`cap24` and `cap8` are both clearly above ×1 (`shep_straw`) and above `shep_milk`, by **+0.6 %** class
effects, not +1.8 %.

## 2. Mechanism table (8 games, seat 0 = arm, seat 1 = ×1)

**cap24** (mean margin +1,202):

| side | item | units | revenue | avg realised price |
|---|---|---|---|---|
| cap24 | WOOL | 1,656 | 258,814 | **156.29** |
| ×1 | WOOL | 1,656 | 253,177 | **152.88** |
| cap24 | STRAWBERRY | 1,984 | 182,308 | **91.89** |
| ×1 | STRAWBERRY | 1,984 | 178,153 | **89.79** |
| cap24 | MILK | 1,548 | 133,270 | 86.09 |
| ×1 | MILK | 1,548 | 133,498 | 86.24 |

**Units are identical to the unit on all three items** (WOOL 1,656; STRAWBERRY 1,984; MILK 1,548). The
revenue differences are +5,637 (wool) + 4,155 (strawberry) − 228 (milk) = **+9,564 over 8 games =
+1,196/game**, which matches the probe's mean margin (+1,202) — i.e. the whole effect is explained by the
**realised price on wool (+2.2 %) and strawberry (+2.3 %)**, with milk neutral. **cap8** (mean margin +824): WOOL units 1,652 identical, price **156.25 vs 154.12** (+2.13);
STRAWBERRY units 1,984 identical, price **91.59 vs 90.03** (+1.56); MILK units 1,552 identical, price
85.88 vs 85.97 (neutral). Same channel, same equal-volume/price-only signature.

## 3. Why the transitive figure was wrong (and what it means)

The chain estimate added three *incremental* duels, each measured on **different panels** against
**different bases** (`shep_milk` → cap2 → cap8 → cap24). Increments measured that way do not compose:
each later duel re-measures part of the same price effect on a different town sample, and the panels'
base wallets differ (89k…99k), so the percentages are not additive. The **end-to-end contrast on one
panel set is the only valid arithmetic**, and it gives **+0.64 %**, i.e. the drain-mult + milk-forward
change is worth **≈ +95 rating points (CI +67…+123)**, not +260.

**Consequence for the target:** +95 points covers roughly **38 % of the +250** the human wanted for
~2,650, not all of it. The remaining ~155 points still have to come from somewhere else (the
economy-simulation families), on the evidence of Tasks 23–35.

## 4. Where the two arms actually differ, and the recommendation

The file diff vs `shep_straw` shows the arms differ by **three** things, not one:
1. `forward_drain_mult` (24.0 or 8.0);
2. **`MILK` added to `forward_items` with `forward_start_by_item` (step 312)**;
3. the inert fraction-gate code lines (empty dict ⇒ no behavioural effect).

So the direct contrast measures *the whole arm*, which is exactly what the live matched pair tests —
good for the experiment, but it is **not** a single-knob measurement of the multiplier. The mechanism
probe shows the milk leg is price-neutral (86.09 vs 86.24), so the gain is the multiplier acting on
wool and strawberry.

**Recommendation for the live pair:** run the experiment as scheduled with **×24 vs ×1**, because
×24 is the better point estimate on every panel set measured (+630 vs +565 pooled here; +402/+564 vs
the ×8 baseline in Task 38) and its runtime is unchanged (mean 1.1 ms, p99 3.9 ms, max 57.9 ms against
the 1 s budget) with a byte-identical control. Choose **×8 over ×24 only if** the aim is a *minimal*
departure from the submitted line: ×8 is already live (ref 56605582) and is statistically
indistinguishable from ×24 on these panels (+565 vs +630, overlapping CIs), so if a submission slot is
scarce, ×8 is the safer arm that still carries the full ~+85…+95-point mechanism; if the slot is
available, ×24 has the marginally better point estimate and the same risk profile.

## 5. Artifacts

| file | content |
|---|---|
| `scripts/t39_direct.py`, `log/t39.log` | the file-diff control, 4 direct duel cells, pooled CIs, mechanism probes |
| `data/candidate/duel-t39-{cap24,cap8}-vs-x1-{p1,p2}.json` | per-seed deltas, counters, exceptions |
| `data/t39-direct.json` | aggregated direct results |
