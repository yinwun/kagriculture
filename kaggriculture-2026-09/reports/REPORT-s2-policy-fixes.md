# S2 policy fixes — both implemented, counters changed, money curve unchanged; the binding defect is a bootstrap deadlock

Date: 2026-09-19. Instrument: `scripts/s14_gate.py` (per-seed day gate), the runtime liveness
audit, and the compiled θ programs. Live submitted files untouched.

## 0. Headline

1. **Both named defects were fixed as specified, and the fix is visible in the counters but
   not in the money.** PICKUP 837 → **442**, DROP 596 → **372**, MOVE 35 → **249** (champion
   scale ~196 / ~43 / ~2,950). PLANT / WATER / HARVEST remain **0**.
2. **The 4-town day curve is unchanged to the coin** (day 10 −18,256, final −156,782; the
   pre-fix run was −18,256 / −156,782). This is **not** the inert/parameter-insensitive
   signature: the counters differ between builds (442/372/249 vs 837/596/35) and the liveness
   audit reports `violations []` on both. The money path is identical because the churn was
   never on the cash path — the farm produces nothing either way.
3. **The binding defect is now identified one level deeper than the two fixes: a mutual
   bootstrap deadlock.** The plan's own cash path is a knife edge — the *champion's* cash is
   **22 coins** at day-1 hour 0 — and it recovers only by selling **fertilizer and wheat that
   its farm produces**. The standalone agent reaches the same 22 coins (the plan's day-0
   spends are faithfully executed) but has **PLACE = 0**, so it has no animals in pens, no
   `COLLECT_FERTILIZER`, no produce, no sales, no cash, no seeds, no plants: the plan assumes
   the champion's production, and the reactive unit policy needs the plan's seeds to produce.
4. Gate 1d was **not run** (day 10 is a deficit). No representational conclusion is drawn.

## 1. What was changed (both fixes, as specified)

**(1) Destination-aware DROP + delivery choreography.** The unit policy now computes
`animal_in_hand()` and `pen_target()`: a carried animal with an empty matching pen (or a
planned build site) has a **destination**, so the `carry and adj → DROP` branch is bypassed and
the unit walks (and PLACEs / BUILDs on arrival); DROP fires only when the animal has no
destination or the cargo is non-animal (seeds/fertiliser/wheat cargo is unaffected, and the
zero-overflow property is preserved because the drop still only happens at a shed-adjacent
tile). Measured effect: the churn roughly halved and MOVE recovered from 35 to 249.

**(2) Cash-aware seed reserve.** `_seed_reserve_for_day(day)` sums the day's **own** BUY_SEED
costs from the program, and every non-seed op is now gated on `cash − reserve ≥ cost`, with
the reserve drawn down as seed ops execute. The plan's seed buys are therefore protected from
the day's hires/animals/land. Measured effect: the reserve is active (the gate drops fewer
seed ops early), but it cannot create cash — see §3.

## 2. Evidence the seeds do not land (first three days of the plan, before/after)

The compiled program's own op sequence for seed 9000, with the champion's cash at each step
(this is what the standalone agent replays, hour by hour, gate and all):

| day | hour | plan cash | ops |
|---|---|---|---|
| 0 | 0 | 3,000 | BUY_PRODUCT WHEAT 5, BUY_PRODUCT WHEAT 10, SELL WHEAT 15 |
| 0 | 1 | 3,000 | SELL WHEAT 0, BUY_PRODUCT WHEAT 5, HIRE ×5, BUY_ANIMAL COW 2, BUY_ANIMAL SHEEP 2 |
| 0 | 6 | 1,052 | **BUY_SEED MELON 2** |
| 0 | 7 | 892 | **BUY_SEED MELON 1** |
| 1 | 0 | **22** | HIRE ×3 |
| 1 | 6 | 18 | SELL FERTILIZER 1, BUY_PRODUCT WHEAT 3 |
| 2 | 0 | 81 | SELL FERTILIZER 1, HIRE ×4 |
| 2 | 2 | 173 | SELL WHEAT 2 |

Read the cash column: **the champion itself is at 22 coins at day-1 hour 0** and rebuilds from
fertilizer and wheat sales. After the two fixes the standalone agent's own money by day is
**22, 18, 40, 87, 21, 51, 1, 1, 1, 0, 0, …** — i.e. it reaches the same knife edge and then
dies, because its `SELL FERTILIZER` / `SELL WHEAT` ops have nothing behind them. Before the
fixes the day-0 seed buys also failed; after the reserve they are *approved by the gate* but
the account is empty by the time the hours arrive, so the seeds still do not land
(`BUY_SEED` executable only if `cash ≥ cost`, and 22 < 160).

## 3. Why the two fixes cannot break the deadlock (the binding constraint)

**The agent never places an animal** — `PLACE = 0`, `COLLECT_FERTILIZER = 0`. The delivery
sequence is inherently *ordered across steps* (walk to the shed → PICKUP → walk to the pen →
PLACE), while my policy is a pure reactive priority on the tile the unit currently occupies:
at a pen tile it emits `PICKUP` (which only works shed-adjacent), and at a shed-adjacent tile
it has no reason to pick an animal up because its highest-priority job there is something
else. So animals are picked up and dropped but never delivered (442/372), no fertilizer or
milk/wool is produced, the day-1-2 sales fail, and the plan's cash path — which the champion
funds from exactly those sales — never materialises. Seeds are 0, PLANT is 0, and the farm is
dead by day 7. **Neither of the two fixes can break this, because it is a control-flow
problem, not a gating problem**: a reactive per-tile policy cannot express a multi-step
delivery plan, and the plan cannot fund itself without the production that delivery creates.

## 4. Day curve before/after (4 towns, 8 paired games each)

| day | before fixes | after fixes | champion-scale reference (Task 13 matched baseline) |
|---|---|---|---|
| 0 | 0 | 0 | +0 |
| 3 | −212 | −200 | +0 |
| 4 | −704 | −692 | +0 |
| 5 | −814 | −795 | +0 |
| 6 | −1,082 | −1,082 | +7 |
| 8 | −1,600 | −1,599 | +7 |
| 9 | −2,938 | −2,938 | +39 |
| **10** | **−18,256** | **−18,256** | **+39** |
| 12 | −20,963 | −20,963 | +39 |
| final | −156,782 | −156,782 | +389 |

Movement/work counters, after the fixes vs the champion scale (per game):

| counter | before | after | champion (~) |
|---|---|---|---|
| PLANT | 0 | **0** | 239 |
| WATER | 0 | **0** | 1,700 |
| HARVEST | 0 | **0** | 484 |
| MOVE | 35 | **249** | 2,950 |
| PICKUP | 837 | **442** | 196 |
| DROP | 596 | **372** | 43 |
| PLACE | 0 | **0** | ~100 |
| COLLECT_FERTILIZER | 0 | **0** | ~375 |

## 5. Runtime, gate 1d, discipline

* Runtime: the 4-town day gate is ~2 minutes; per-step wall clock is unchanged from the
  standalone build measured in Task 14 (sub-millisecond mean, worst step dominated by the
  base champion's own setup). The liveness audit adds no measurable cost.
* Gate 1d: **not run** — the day-10 row is a deficit (−18,256), which is the stated bar.
* Liveness audit on every build: `violations []` for both the pre-fix and post-fix standalone
  agents (`farmer_ops 717`, `units 1105`, `noop_units 2`, `mkt_ops 620`). The parameter-
  sensitivity check is satisfied by the counter differences between builds.

## 6. Epistemic status

| claim | status |
|---|---|
| The market program is faithful and 99.8% realisable | **Causal** (Task 13 controlled replay, bit-identical curves, +389 reproduced) |
| The destination-aware rule works as intended (churn halved, MOVE recovered) | **Verified** (counters 837→442, 596→372, 35→249, audit clean) |
| The seed reserve gates on cash − reserve | **Verified in code and by the gate's behaviour**; its *effect* on production is nil because cash is 22 coins when the seed hours arrive |
| The unchanged money curve is a real measurement, not the inert signature | **Verified by the audit plus differing counters** (a broken build would show unchanged counters too) |
| The binding constraint is the multi-step delivery choreography (PLACE 0 → no fertilizer/produce → sales fail → no cash → no seeds) | **Mechanistic reading of the counters and the measured cash path** (day 0–2 cash 22/18/40), not yet fixed and re-measured — so the *fix* is unmeasured |
| Whether an explicit θ representation can reach parity | **UNMEASURED** — the standalone agent has never yet produced a single crop or placed a single animal |

## 7. What the next round must do (and why it is no longer a two-line fix)

The remaining work is a **sequenced, persistent job scheduler**, not a reactive priority: each
unit needs a standing assignment (e.g. "deliver animal A to pen (x,y): if not carrying and
not at the shed, walk to the shed; if at the shed and not carrying, PICKUP A; if carrying,
walk to (x,y); if at (x,y) and carrying, PLACE") with aging so assignments complete before new
ones are taken. That is the S2 item, and it also happens to be the piece that makes the plan's
cash path realisable, because fertilizer/milk/wool sales are what fund the plan's own knife
edge. Concretely: (1) implement the standing-assignment scheduler; (2) verify PLACE > 0 and
COLLECT_FERTILIZER > 0 on the first 3 days; (3) re-run the 4-town day gate; (4) only then 20
towns, gate 1d, invalidity rate and runtime.

Artifacts: `scripts/plan_runtime.py` (destination-aware cargo + seed reserve + liveness audit),
`data/plan/agents/full-<seed>.py` (post-fix builds), `data/plan/s2-gate-fixed.json`,
`data/plan/s15-matched.json` (the unchanged baseline reference). Nothing submitted; no live
file modified.
