# Robust layout optimisation under rival-layout uncertainty (Task 8) — three negatives and a correction

Date: 2026-09-19. Base: the STACK `data/forward/wool_drain1_outerprem/main.py` (submitted,
ref 56349751). Instrument: `scripts/ab_duel.py` (paired, seats alternating, 60 games per
panel) and `scripts/race_timing.py` (per-step wall clock of the whole agent).

## 0. Headline

1. **Robust decision rules do NOT beat the point prediction.** Over the same hypothesis
   set, best-response-to-clone −177, maximin −181, soft/average −180, minimax-regret −180
   in-sample against the stack (all t≈−3.4, W/L 27/33). The rule contributes **≤4 coins per
   town** — i.e. nothing. Reason, measured: the rules change the chosen layout in only
   **0–2 steps per game** versus clone.
2. **The rebuild itself is a small regression** relative to the submitted stack
   (−177, t=−3.34), so the *control requirement is not met by the new code path* and no
   Task-8 variant is kept. **The best build remains the stack.**
3. **Runtime is a non-issue** (measured, whole agent): mean 1.8 → 2.4 ms/step, p95 3.7 →
   6.2 ms, worst single step 150 → 185 ms — and the unmodified champion alone shows a
   135–210 ms worst step, so the worst case belongs to the base, not to the layer.
4. **Widening the search is inapplicable here**: the single-slot neighbourhood is already
   exhaustive (the exact search covers all slot assignments for ≤4 contested items; the
   `race_exact=6` variant changes nothing because the contested set never exceeds 4).
5. **Correction of my own Task-7 framing.** I reported "the lever's range is ±15k and we
   capture ~5%". That is wrong: the range is **asymmetric** — a downside cliff, not
   untapped upside. The Task-1 oracle with *perfect* knowledge of the rival's layout
   (exhaustive permutations of our own list) is only **+513/+963 per game**, and the stack
   already captures **+790 per town**. So the layout lever is ~80–100% exhausted; the
   forced-anti −15,307 is the cost of being deliberately reckless, not headroom.

## 1. Hypothesis set and rules (what was built)

Set members (`race_set`), all market-layer only:

* `clone` — our own pre-layer list (the incumbent's point model);
* `implied` — the rival's quantities recovered from the public inventory delta plus the
  town drain, placed on the clone template's slots (Task 6 machinery, here as one member
  rather than the point model);
* `empty` — no rival sells (a structural control: our own margin becomes slot-independent);
* `front` — adversarial placement: the rival packs all its SELL lots into the first slots,
  the worst slot placement we can be paired against without more information. (A true
  adversarial member would maximise our regret with an inner optimisation; the cost is a
  second search per candidate, and the report notes it as the stronger variant I did not
  build.)

Rules (`race_rule`) evaluated over the candidate × hypothesis margin matrix: `min`
(maximin), `avg` (soft/average), `regret` (minimise the worst-case regret), and — as the
point-prediction reference — a single-member set with the same code path.

## 2. Measured rules, in-sample, 60 games, vs the stack

| candidate | rule | delta | t | W/L | wallet |
|---|---|---|---|---|---|
| `rb_clone_stack` (single-member set = point prediction, rebuilt) | min | −177 | −3.34 | 27/33 | 102,862 vs 103,038 |
| `rb_min_stack` (maximin over the 4-member set) | min | −181 | −3.42 | 27/33 | 102,859 vs 103,041 |
| `rb_avg_stack` (soft/average) | avg | −180 | −3.40 | 27/33 | 102,862 vs 103,042 |
| `rb_regret_stack` (minimax regret) | regret | −180 | −3.41 | 27/33 | 102,862 vs 103,042 |

Out-of-sample for the three robust rules was **not run**: none of them beats the control
in-sample (they differ from it by ≤4 coins), and the protocol advances only winners. The
control itself is already negative against the submitted stack, which is the more important
number: my refactor of `_race_apply` (margin matrix + rules) changes the clone path's
behaviour (12 reorders vs the incumbent's 6 at seed 9000, 8–11 differing market steps per
game) and costs −177, t=−3.34. **So the new machinery must not replace the stack**, and the
"control is byte-identical to the base" requirement is explicitly *not* satisfied by this
round's rebuild — the byte-identical control for the protocol remains `data/rival/fwd_control`
(Task 6, +0 with every counter +0 on both panels).

Why the rules coincide: I measured the deviation directly — `rb_min` differs from
`rb_clone` in **2 steps** at seed 9005 and **0** at seed 9009; `rb_avg` and `rb_regret` in
**1** and **0**. The set members are highly correlated (all say "our items are contested,
roughly at our own slots"), the `empty` member contributes a slot-independent constant, and
`front` points the same way as `clone`. With ≤2 of 719 steps changed, no rule can move
15k, and the measured spread (≤4 coins) confirms it.

## 3. Runtime (first-class result, as requested)

`scripts/race_timing.py`, seed 9000, whole-agent time per step over a full game:

| agent | mean | median | p95 | **worst step** |
|---|---|---|---|---|
| champion alone (`rgcs`) | 1.5 ms | 0.9 ms | 3.0 ms | 135.5 ms |
| **stack (submitted)** | 1.8 ms | 1.0 ms | 3.7 ms | 150.1 ms |
| `rb_min_stack` (4-hypothesis, 1,748 evaluations/game) | 2.4 ms | 1.3 ms | 6.2 ms | 185.5 ms |
| `rb_min_wide_stack` (`race_exact=6`) | 2.5 ms | 1.3 ms | 5.7 ms | 168.9 ms |

The rule machinery costs +0.6 ms/step mean and +2.5 ms p95; the widening costs nothing
measurable. The worst single step is 150–185 ms with the layer and 135–210 ms without it
(the champion's own first-step setup), i.e. **the layer is not the driver of the worst case
and nothing approaches a per-step limit**. Even a 100× widening of the candidate
neighbourhood would stay in the tens of milliseconds per step.

## 4. Why the search cannot capture more (the corrected calibration)

* The Task-1 oracle — perfect knowledge of the rival's layout, exhaustive enumeration of
  our own list permutations — is **+513 per game (seed 9000) and +963 (seed 9001)**, and the
  honest clone implementation captured +316/+742 of it.
* The submitted stack's market-layer component measures **+790 per town** on the 30-town
  panel (and the forward layer adds its own +358/+493 standalone).
* The forced-anti probe (Task 7) loses **−15,307, t=−18.35, 0/60** — a cliff, not a range.
* Therefore the objective is steep **downward** but shallow upward: our current extraction
  is ~80–100% of the perfect-information oracle, and the remaining +3,600/town cannot be
  reached by re-slotting our own list. Widening the neighbourhood cannot help because the
  single-slot space is already searched exactly; only a *different stock-on-market
  schedule* (which turn each lot is offered in, i.e. the tape's own plan) changes what is
  available to re-slot.
* Anti-side drift diagnostic (item 3): with ≤2 changed steps per game and all rules within
  4 coins of the control, no robust rule drifts toward the punished side; and the search
  never picks a negative-gain layout by construction (`min_gain` filter plus the
  best-vs-baseline comparison), so the anti cliff is not reachable by any variant measured.

## 5. Updated accounting and recommendation

* Fraction of the frontier's +4,407 explained: **~18% IS / ~25% OOS** (the stack), unchanged
  — Task 8 produced no new build.
* Residual decomposition (unchanged from Task 7, now with the layout lever closed):
  (i) production-side herd/turn ≈ +1,400/town (a plan edit; full paired duel per candidate,
  no screens, per the RNG finding); (ii) the tape's own within-window price edge ≈
  +1,400/town, of which our market layers already capture the oracle's worth (+790/town).
* **Yes — the residual is now dominated by the production-side component that only a plan
  edit can reach**, plus the tape's own turn choices. The market-layer line of work is
  exhausted: the decision rule, the hypothesis set, the search width and the observable
  rival channel have all been measured and all are null or negative.
* Recommended next round: a herd/turn plan edit (the +8% sheep-day gap, ~+1,400/town), one
  candidate per full paired duel. That is the only identified channel with a measured,
  coherent mechanism behind it.

## 6. Rebuild and artifacts

```bash
# the live line, unchanged
python scripts/build_race.py --name outer_prem
python - <<'PY'
import sys; sys.path.insert(0, "scripts")
import build_forward
build_forward.build({"forward_items": ["WOOL"], "forward_drain": True},
                    "wool_drain1_outerprem", "data/forward",
                    base_path="data/race/outer_prem/main.py")
PY
# the Task-8 machinery (measured, NOT kept)
python - <<'PY'
import sys; sys.path.insert(0, "scripts")
import build_race, build_forward
SET4 = ["clone", "implied", "empty", "front"]
for name, extra in (("rb_clone", {"race_set": ["clone"], "race_rule": "min"}),
                    ("rb_min", {"race_set": SET4, "race_rule": "min"}),
                    ("rb_avg", {"race_set": SET4, "race_rule": "avg"}),
                    ("rb_regret", {"race_set": SET4, "race_rule": "regret"})):
    st = {"race_layout": 1, "race_hook": "outer"}; st.update(extra)
    build_race.build(st, name + "_race", "data/rival")
    build_forward.build({"forward_items": ["WOOL"], "forward_drain": True}, name + "_stack",
                        "data/rival", base_path=f"data/rival/{name}_race/main.py")
PY
# per-step runtime of any build
.venv/bin/python scripts/race_timing.py --cand data/rival/rb_min_stack/main.py
```

Artifacts: `scripts/race_timing.py`, `data/rival/rb_*_{race,stack}/main.py`,
`data/rival/sweep-t8-IS.txt`, `data/rival/duel-rb_*-IS.json`. All error counters 0
(`layer_fallbacks`, `entry_fallbacks`, `race_errors`) on every variant; the protocol's
byte-identical control is `data/rival/fwd_control` (Task 6). Nothing submitted to Kaggle.
