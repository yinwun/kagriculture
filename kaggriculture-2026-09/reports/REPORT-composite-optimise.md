# Optimising the public composite (Task 22) — ladder mining + layer test, nothing submitted

Date: 2026-09-21. Question asked: can the composite we now run under our own name
(ref **56409633**, `data/cand/the-metav4-farm-submission-v13-extracted-main.py`, sha256
`9d63494603f88219857a3101d7dc19cc750ded04e5886732ee428580326967d9`) be optimised, and **does
adding layers improve it?** Answered by mining its 78 ladder games first and then by a paired
duel campaign with our two market layers applied as outermost wrappers. **No submission was made;
no live file was modified.**

## 0. Headline

1. **Its losses are not clustered on an archetype — they are near-ties against the strongest band
   it actually plays.** 78 games, 63/13/2 = **80.8 %** win, mean margin +8,585 but **median +1,406**
   (the mean is dominated by blowouts against weak teams). 10 of the 13 losses are against
   2400–2700-rated opponents — the band that supplies 37 of its 78 games — and the loss margin
   median is **+129** (min +50, max +14,713). **8 of 13 losses are games in which we scored at or
   above our own median reward**: it is being out-scored in close games, not collapsing. Zero losses
   below 1800 rating, zero in the 2700+ band, and **no opponent appears twice among its losses**.
2. **Our own line is much weaker against a much weaker field.** Ref 56409622: 77 games, 43/34/0 =
   55.8 %; 43 of its 78 opponents were 1800–2100 and it wins only 51.2 % of those, 16.7 % in
   2400–2700 and 0 % above 2700. The matchmaker gives the composite harder opponents *and* the
   composite beats them (67.6 % in 2400–2700); the win-rate comparison understates the gap.
3. **Adding our layers helps, but by hundreds, not thousands: +324 IS / +448 OOS / +590 on a third
   panel (pooled +454, t = +7.05 over 90 towns, 80/90 seeds positive).** That is +0.32 % / +0.45 %
   of wallet. The race layer's marginal value **collapses** on this base (+112/+64, from +597/+676
   on our own champion) because the composite already runs its own lockstep sell-layout search; the
   wool-forward layer **keeps** its value (+264/+397 vs +358/+493 on our base).
4. **By the pre-registered rule (Δ > 0 and t ≥ 3 per panel) no variant is a clean winner**:
   `comp_race` fails OOS (t = 2.75), `comp_fwd` fails IS (t = 2.43), and `comp_both` — the best —
   fails IS by 0.07 (t = 2.93) while passing OOS (4.31) and the *post-hoc* third panel (5.00).
5. Two real bugs were caught by the new build-time collision guard, not by the wallet: the composite
   defines its **own global `_RACE_PARENT`**, so our hook's `_RACE_PARENT = agent` recursed infinitely
   (wallet frozen at the 3,000 start, **`err=0`**, episode still `DONE`). `ab_duel.py` now counts
   per-seat agent exceptions; without that the whole round could have been read as "layers do nothing".

## 1. Ladder mining (step 1)

Method: `scripts/track_submission.py` / `data/episodes-<ref>-raw.json` (raw
`competition_list_episodes`), analysed by `scripts/mine_ladder.py` → `data/ladder-mine.json`.
Win = my reward > opponent reward; the opponent's rating is the team's score in
`data/leaderboard.json` (snapshot 2026-09-20 17:10). Bands are opponent rating.

| | **56409633 composite** | **56409622 our line (control)** |
|---|---|---|
| games | 78 | 77 |
| W/L/T | **63/13/2** | 43/34/0 |
| win rate | **80.8 %** | 55.8 % |
| margin mean / median | +8,585 / +1,406 | +5,520 / +142 |
| margin deciles p10 / p50 / p90 | −114 / +1,406 / +35,156 | −2,570 / +142 / +29,428 |

Win rate and margin by opponent-rating band:

| opponent band | composite n | W-L-T | win % | margin mean | our line n | W-L-T | win % | margin mean |
|---|---|---|---|---|---|---|---|---|
| 0–1500 | 11 | 11-0-0 | 100 % | **+49,289** | 10 | 10-0-0 | 100 % | +36,192 |
| 1500–1800 | 3 | 3-0-0 | 100 % | +4,623 | 5 | 5-0-0 | 100 % | +15,525 |
| 1800–2100 | 8 | 7-1-0 | 87.5 % | +7,071 | **43** | 22-21-0 | **51.2 %** | +289 |
| 2100–2400 | 14 | 12-2-0 | 85.7 % | +2,090 | 11 | 5-6-0 | 45.5 % | −206 |
| **2400–2700** | **37** | 25-10-2 | **67.6 %** | +634 | 6 | 1-5-0 | 16.7 % | −1,968 |
| 2700+ | 5 | 5-0-0 | 100 % | +867 | 2 | 0-2-0 | 0 % | −6,443 |

**Where the 13 losses are:**

| axis | finding |
|---|---|
| opponent rating | 10/13 in **2400–2700**, 2 in 2100–2400, 1 in 1800–2100; none below 1800, none at 2700+ |
| loss margin | mean +1,831, **median +129**, min **+50**, max +14,713 (worst: ansheng jhang 145,356 vs 160,069) |
| our reward on losses | mean 103,347 vs our median reward 99,510 → **5/13 collapses, 8/13 out-scored** |
| repeated opponents | **none** — every loss is to a different team |
| exact +50 margins | **3 of 13** losses were by exactly 50 coins (darasty, Sophinator, Toru59er) — a pattern we do not have an explanation for |
| time trend | chunk 1 (00:54–02:04) 18-1, +31,277 → chunk 2 15-4, +2,917 → chunk 3 13-5, +256 → chunk 4 17-3, +720 (early games were against weak teams while its rating converged upward) |

Cross-ref: one opponent beat **all three** of our lines (`xxxzzz123312123321`, rating 2446.5); every
other repeated winner beat two of them (Omar Althobaiti, kyosan, Pjchauhan, Grim Reaper, Rasmus
Hulthe…). So there is a real "hard field" but **no single nemesis archetype**.

Read for the layer work: the composite loses by ~50–1,400 coins in close games against the top
field, which is exactly the size range our layers operate in — a few hundred coins per town. The
hypothesis was worth testing; §5 gives the answer.

## 2. What the composite already implements (why the test is informative)

It shares our tape blob (`54fe156ea7206e38`) and the same `_IMPL`/`Chassis`/`_View` lineage, but it
contains **none** of our layer code (`_race_hypotheses`, `_race_apply`, `_race_layout`, `_race_outer`,
`forward_*`: all 0 occurrences) and instead carries its own equivalents:

| its machinery | what it duplicates |
|---|---|
| `_v44y_lockstep`, `_v44y_factor_margin`, `race_clone_turns`/`race_horizon_turns`/`race_lost_races` (28,560 clone turns per 60 games) | **our race layer** (lockstep sell-layout search) |
| `_cs_rewrites`/`_cs_credit`/`_cs_sold` | our `clamp_sells` sell rewriting |
| `_v92_p_*` (8 refs) | sale-forecast library |
| `_hd2_*` (18 refs) | shop-demand rewriter |
| `_ca_yield`, `_cs_` (yield simulation) | crop/yield simulation |

So "add our race layer" is genuinely a test of a **duplicate** mechanism, and "add our forward layer"
a test of one it does *not* have. That is what the measurements in §5 show.

## 3. Build design, and the two bugs the guard caught

New builder `scripts/build_composite_layers.py` (the composite is never modified) + a backwards-
compatible `base_path`/`outer_prefix` generalisation of `scripts/build_race.py`
(`build_race.outer_block(prefix)`). Both hooks are applied **outermost**, after the composite's own
~88-def chain:

| variant | content | sha256 (main.py) |
|---|---|---|
| `comp_control` | both blocks present, **all knobs off** | `c9d506c5f4fc8db78808301bf9ce56ec15529b5a545445c662a5b404ce74bc73` |
| `comp_race` | + our race layer, outer hook, clone hypothesis, premium items | `58f041f08be78d8eff2f8b35c300de46dc4eab4a245f62afc0e267e3bd86294a` |
| `comp_fwd` | + our wool forward layer (`forward_items=["WOOL"]`, `forward_drain=True`) | `a7dcff2350c851621d8213f7f7294684c75eb7f67dff34763dda22c9d2f81256` |
| `comp_both` | both | `0a7a2070a25e0cb6afe769e8836d0b6192fb5ac9cff21267f5776dbcac2a864d` |

**Bug 1 — `_RACE_PARENT` collision (silent, catastrophic).** The composite defines its own
module-level `_RACE_PARENT`, which its internal agent chain calls (line ~6788). Appending our
outer block rebound that name to the composite's outermost agent → `RecursionError` on every step →
the engine substituted PASS, the episode still ended `DONE`, `err=0`, and the variant scored exactly
its **3,000 starting coins**. The control duel is what exposed it (Δ = −160,775, idle share 100 %).
Fix: `outer_block("_clr")` renames the hook's three globals; **and** a new build-time AST guard
(`check_collisions`) fails the build if appended code redefines any module-level name of the base.

**Bug 2 — `SHOPS` false-positive (also silent).** My duplicate-suppression check used the loose
string `"SHOPS = {"`, which also matches the composite's `_OR2_SHOPS = {`, so our shop table was
skipped and the forward layer raised `NameError: SHOPS` on every step (counted: `forward_errors`
19,410; Δ = 0). Fix: match our block's own comment (`"Town shop table, from the engine"`).

**Instrument hardening.** `scripts/ab_duel.py` now wraps both seats and counts agent exceptions per
seat (`cand_exceptions`/`base_exceptions`, printed as `AGENT EXCEPTIONS`). This closes the blind spot
that made Bug 1 invisible (`status=DONE`, `err=0`). Neutrality re-verified after the change: the
pre-existing pairing (`wool_drain1_outerprem` vs `race/outer_prem`, seeds 9000–9029) reproduces
`data/forward/duel-stack-vs-outerprem-IS.json` **exactly** — scalars, all 30 per-seed deltas and all
action counters identical (`data/composite/harness-neutral2.json`). The builder edit was likewise
proven output-neutral by rebuilding three champion variants with the old and new code in one process
(byte-identical).

## 4. Controls and liveness / parameter sensitivity (step 3, institutionalised)

| check | result |
|---|---|
| **Control** `comp_control` vs plain composite, 9000–9009 | **Δ = +0 exactly**, wallets identical (89,190 vs 89,190), **every action counter identical** (+0), our counters absent → the injected code is provably inert when off |
| Parameter sensitivity — race off → on | counters appear: `race_tried` 37,858, `race_eval` 38,581, `race_considered` 723, `race_reorders` 185, `race_gain` 20,158 (60 games) |
| Parameter sensitivity — forward off → on | `forward_orders` 4,640, `forward_units` 4,640; off = absent |
| `layer_fallbacks` / `entry_fallbacks` / `race_errors` | **0 / 0 / 0** on both seats of all 7 duels (the hook records only non-zero keys; none appeared) |
| agent exceptions | **0 / 0** in every duel |
| episodes not `DONE` (`err`) | 0 in every duel |
| builder self-check | 720-step smoke on all four variants: real action (farmer+hands+market) returned, no exception |

## 5. Results — our layers on the composite (step 2/3)

All pairings: candidate vs the **plain composite**, paired, seats alternating, 30 seeds = 60 games
per panel. Per-seed Δ is the mean over the two seat assignments; t is over the 30 per-seed deltas.
The third panel (9200–9229) was run **after** seeing the first two panels, so it is confirmatory,
not pre-registered.

| variant | panel | Δ wallet | Δ % | t | W–L (of 60) | cand wallet | base wallet | err | exceptions |
|---|---|---|---|---|---|---|---|---|---|
| `comp_race` | IS 9000–9029 | +112 | +0.11 % | +3.12 | 44–4 | 100,114 | 100,003 | 0 | 0 |
| `comp_race` | OOS 9100–9129 | +64 | +0.07 % | **+2.75** ✗ | 40–4 | 94,868 | 94,804 | 0 | 0 |
| `comp_fwd` | IS 9000–9029 | +264 | +0.26 % | **+2.43** ✗ | 43–17 | 99,948 | 99,684 | 0 | 0 |
| `comp_fwd` | OOS 9100–9129 | +397 | +0.42 % | +3.62 | 51–9 | 94,778 | 94,381 | 0 | 0 |
| **`comp_both`** | IS 9000–9029 | **+324** | +0.32 % | **+2.93** ✗ | 45–15 | 99,975 | 99,651 | 0 | 0 |
| **`comp_both`** | OOS 9100–9129 | **+448** | +0.47 % | **+4.31** | 53–7 | 94,798 | 94,350 | 0 | 0 |
| **`comp_both`** | 3rd panel 9200–9229 | **+590** | +0.58 % | **+5.00** | 54–6 | 102,286 | 101,696 | 0 | 0 |

Per-seed and pooled:

| variant | per-seed min / median / max (IS) | per-seed min / median / max (OOS) | positive seeds | **pooled Δ** | **pooled t** |
|---|---|---|---|---|---|
| `comp_race` | +0 / +48 / +889 | −1 / +38 / +685 | 42/60 | +88 | +4.10 |
| `comp_fwd` | −770 / +47 / +1,577 | −496 / +86 / +2,233 | 50/60 | +330 | +4.29 |
| **`comp_both`** | −770 / +104 / +1,763 | −128 / +172 / +2,233 | **80/90** | **+454** | **+7.05** |

Interpretation:
* **The race layer's marginal value collapses on this base** (+112/+64 pooled +88) versus
  **+597 (t = 9.87) / +676 (t = 10.70)** when the same layer was added to our own champion. The
  composite already spends ~28,560 clone turns per 60 games on its own layout search, so there is
  little left for ours to take. The two rewriters do **not** fight (the delta is positive), they
  overlap.
* **The forward layer keeps almost all of its value** on the foreign base (+264/+397) versus
  +358 (t = 2.57) / +493 (t = 3.74) on our champion — the composite does not sell wool stock as it
  appears, so that mechanism is still uncontested.
* Combined is the best of the three on every panel, and the sign is stable (80/90 seeds positive);
  but the effect is **0.3–0.6 % of wallet**, i.e. ~1/10 of the ±5 % wobble our own measurements have
  recorded in the ladder's displayed score.

Action mix is unchanged outside the two hooks (identical idle share, e.g. 7.79 % vs 7.79 %, and
identical counters for every non-market verb); the layers only rewrite the market list.

## 6. Runtime (step 3) — the 1 s per-step budget

The engine configuration is `actTimeout: 1` (s) per step, `runTimeout: 1200` s per episode. Measured
by `scripts/composite_timing.py` (one 720-step game with both seats running the same build, timing
every `agent()` call; 1,438 calls per game):

| agent | mean | p95 | p99 | max | >250 ms | >500 ms | >1 s | game wall |
|---|---|---|---|---|---|---|---|---|
| plain composite | 0.6 ms | 1.2 ms | 2.3 ms | 46.0 ms | 0 | 0 | 0 | 3.0 s |
| `comp_race` | 0.8 ms | 1.5 ms | 2.9 ms | **67.1 ms** | 0 | 0 | 0 | 3.5 s |
| `comp_fwd` | 0.6 ms | 1.3 ms | 2.5 ms | 41.5 ms | 0 | 0 | 0 | 3.2 s |
| `comp_both` | 0.7 ms | 1.4 ms | 2.9 ms | 48.1 ms | 0 | 0 | 0 | 3.3 s |

The heaviest variant's worst step is **67 ms against a 1,000 ms budget (~15× headroom)** and its mean
is ~1.2× the plain composite's. Runtime is not a constraint (this machine; the ratio is the part
that transfers).

## 7. Best build and the decision (step 4)

**No variant clears the pre-registered bar** (Δ > 0 and t ≥ 3 on each panel). `comp_both` is the only
defensible candidate: it is the best on all three panels, is a **strict improvement on the same base**
(the control proves the added code is inert when off), and its pooled margin over 90 towns is
+454 with t = +7.05.

Rebuild command (exact; the composite file must exist at the path below):

```bash
.venv/bin/python scripts/build_composite_layers.py --variant comp_both
# -> data/composite/comp_both/main.py
```

Package (single-`main.py` tar.gz, project convention):

```bash
tar czf data/submits/submission-composite-both.tar.gz -C data/composite/comp_both main.py
```

| artifact | sha256 |
|---|---|
| payload `data/composite/comp_both/main.py` (= `main.py` inside the tarball) | `0a7a2070a25e0cb6afe769e8836d0b6192fb5ac9cff21267f5776dbcac2a864d` |
| `data/submits/submission-composite-both.tar.gz` | `a9f6951816d12d059777c4d769975fcff4791911804091a14ce90fd57c3e93ae` |

**Should it replace 56409633 as the displayed line?** My measured judgement: **not on this
evidence, and if you want to spend a submission, spend it on `comp_both` rather than re-posting the
plain composite.**
* For: measured, paired, 90 towns, 80/90 seeds positive, +0.32…+0.58 % of wallet, and the wrapped
  build is byte-identical to the composite outside two outermost market hooks.
* Against: the expected gain (~+450 coins/town) is about a tenth of the ±5 % wobble we have measured
  in displayed ladder scores, and **no local-wallet → ladder-rating map has ever been measured**
  (same caveat as Task 21). Replacing the tracked submission also restarts the multi-hour
  convergence/age cycle for a line that is currently our best-measured ladder performer (80.8 % win
  rate against the 2400–2700 field). Trading a measured, well-playing line for a +0.45 % local edge
  with unknown ladder translation is not supported by measurement.

If the goal is instead "our own contribution on the stronger base", `comp_both` is that build and it
is ready to submit; the decision is the parent's (I have not submitted anything).

## 8. Step 5 — does adding layers improve the score? What are our layer families worth?

**Yes, adding layers improves this base, but marginally, and our remaining reachable families are
worth hundreds per town, not thousands.** The evidence, all paired duels, Δ per town vs the base each
layer was added to:

| family | on which base | measured Δ | t | verdict |
|---|---|---|---|---|
| race layout search (`outer_prem`) | our champion | **+597 / +676** (IS/OOS) | +9.87 / +10.70 | strong on our base |
| race layout search | **the composite** | **+112 / +64** | +3.12 / +2.75 | mostly already implemented there |
| wool forward (stock-as-it-appears) | our champion / outer_prem | **+358 / +493**, +276 / +469 | 2.57 / 3.74 | reproducible |
| wool forward | **the composite** | **+264 / +397** | +2.43 / +3.62 | holds up on the foreign base |
| room_guard + clamp_sells | V42 baseline | **+463** (1,500 games) | +10.2 | strong |
| **both ours** | **the composite** | **+324 / +448 / +590** | 2.93 / 4.31 / 5.00 | +0.3–0.6 %, pooled t = 7.05 |

Everything else we can build today measured **≤ 0**: herd composition swaps (−982, −5,087, −38,995),
herd/turn plan edits (−3,374), sell-spread deferral (−2,815), tape re-selection (best +24, others
−3,083…−9,749), rival-layout prediction (−265/−274), rival belief variants (−177…−181), forward items
beyond WOOL (milk −290/−345, carrot −279/−469), robust-layout rules (≤ 4 coins).

The modelling-heavy families we have **not** been able to reimplement (the `_hd2_*` shop-demand
rewriter, `_ca_*`/`_cs_*` yield simulation, `_v92_p_*` sale-forecast library, i.e. the families that
simulate the economy rather than post-process one action) are where the thousands live — but the
honest evidence for that is **whole foreign composites**, not single layers: against our champion,
the-2945-farm-96 is **+4,407** (t = 6.04), demand-preserving-turn-sale-timing +2,468,
melon-threshold-squeeze +1,715, game-theoretic-master +1,073, and this composite itself
**+4,458/+4,772/+4,913** (Task 21). We cannot yet attribute any of those to one family, and our own
attempts at the adjacent families were all negative.

**Conclusion:** layers help, our execution-side families are still worth a few hundred coins each on
any base (and the wool-forward one transfers to a foreign base), but there is no evidence that any
family we can currently build is worth thousands — the thousands live in the economy-simulation
families, which remain the frontier's edge and our gap.

## 9. Artifacts

| file | content |
|---|---|
| `scripts/mine_ladder.py`, `data/ladder-mine.json`, `data/track-composite.csv`, `data/track-line_ours.csv` | ladder mining / loss clustering |
| `data/episodes-{56409633,56409622,56349751,56307879,56307906}-raw.json` | raw public episodes |
| `scripts/build_composite_layers.py`, `scripts/build_race.py` (`base_path`, `outer_prefix`) | builders |
| `data/composite/comp_{control,race,fwd,both}/main.py` | the four builds |
| `data/composite/duel-control.json`, `duel-sens-{race,fwd}.json` | control + parameter sensitivity |
| `data/composite/duel-comp_{race,fwd,both}-{is,oos}.json`, `duel-comp_both-p3.json` | the campaign (per-seed deltas, counters, exceptions) |
| `data/composite/harness-neutral2.json` | instrument-neutrality proof |
| `data/composite/timing.json` | per-step runtime |
| `data/submits/submission-composite-both.tar.gz` | packaged best build (not submitted) |
