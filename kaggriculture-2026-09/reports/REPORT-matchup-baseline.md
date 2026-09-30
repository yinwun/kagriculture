# Matchup vs the V42 baseline (Task 21) — measurement only, nothing submitted

Date: 2026-09-20. Question asked: how does the strongest public build we hold compare, on our own
instrument, with the version that scored highest on the ladder for us (the V42 baseline restore,
Kaggle ref `56307879`, best-ever displayed **2,681.9**)? Three pairings were requested and run;
two supplementary pairings were added because they cost ~50 s each and bound the gap from both
sides. **No submission was made.**

## 0. Headline

| # | Candidate | Base | Seeds | Δ wallet | Δ as % of base | t | W–L | candidate wallet | base wallet | errors |
|---|---|---|---|---|---|---|---|---|---|---|
| **1** | **meta-v4-v13** | **V42 baseline (2,681.9 line)** | 9000–9029 IS | **+4,772** | **+4.84 %** | **+7.20** | **58–2** | 103,448 | 98,677 | 0 |
| **2** | **meta-v4-v13** | **V42 baseline (2,681.9 line)** | 9100–9129 OOS | **+4,913** | **+5.31 %** | **+9.58** | **60–0** | 97,520 | 92,607 | 0 |
| 3 | meta-v4-v13 | live line `wool_drain1_outerprem` (56349751) | 9000–9029 IS | +4,119 | +4.17 % | +6.12 | 56–4 | 102,914 | 98,796 | 0 |
| 4 *(suppl)* | meta-v4-v13 | local champion `rgcs` (56307906) | 9000–9029 IS | +4,458 | +4.51 % | +6.46 | 58–2 | 103,336 | 98,879 | 0 |
| 5 *(suppl)* | live line `wool_drain1_outerprem` | V42 baseline | 9000–9029 IS | +1,226 | +1.20 % | +9.12 | 55–5 | 103,673 | 102,447 | 0 |

Per-seed deltas (mean of the two seat assignments; the town is the unit of analysis) are positive
on **30/30** seeds in rows 1, 2 and 4, and **29/30** in rows 3 and 5. Distribution for the headline
pairing: min **+928**, p25 +2,324, median **+3,599**, p75 +5,306, max **+12,473** (IS);
min **+986**, p25 +2,477, median **+4,248**, p75 +7,170, max **+11,168** (OOS).

Read as a measurement: on 60 identical towns, the public composite ends the 720-step game with a
**4.8 % (IS) / 5.3 % (OOS)** larger wallet than the build that produced our best ladder number, and
it repeats that margin against the line we are currently running (+4,119, 29/30 seeds) and against
our locally strongest build (+4,458). The gap is therefore ~4.1–4.9 k coins *whatever* of our builds
it is measured against; it is not an artefact of picking the weakest base.

## 1. Exactly which files were measured

| Role | Path | sha256 | Kaggle ref / ladder |
|---|---|---|---|
| Candidate | `data/cand/the-metav4-farm-submission-v13-extracted-main.py` | `9d63494603f88219857a3101d7dc19cc750ded04e5886732ee428580326967d9` | public composite, 1,004,288 B |
| **Base (headline)** | `data/league/ahmedberatozer_kaggriculture-v42-production-that-fits-the-marke/main.py` | `728fdfb4405ba313f8b14ffb3e0f8eceaddcaa0de49e4835928d89aaf71467e9` | **56307879**; the same build family reached **2,681.9** |
| Base (scale) | `data/forward/wool_drain1_outerprem/main.py` | `df762731da84a3a80584da7d782eb4ccaaa4126fe743ee7d1135c6bcdb305c0e` | current live line, **56349751** |
| Base (suppl.) | `data/tapeopt/rgcs/main.py` | (unchanged champion) | 56307906, ladder 2,147.5 |

**Provenance of the V42 baseline, as recorded in our own artifacts.** `REPORT-night-3-result.md`
records ref `56307879` = `data/league/ahmedberatozer_.../main.py`, sha `728fdfb4405b`, 305,622 B,
packaged as `data/submits/submission-night-A-v42baseline.tar.gz`. I re-extracted the tarballs and
confirmed the payload sha256 byte-for-byte; the *same bytes* are also the payload of
`data/submits/submission-v42-restore.tar.gz`, which is the 2026-09-15 15:57 "restore V42 baseline"
submission, ref **56258384**. The submission that actually reached 2,681.9 is ref **56233887**
(2026-09-14 15:08, "V42 baseline, 41-route gen"); that one predates our tarball archive, so I
**cannot byte-verify** it — it is the same build lineage by our ledger, not by hash.

The candidate is the 20 Sep decoded artifact from Task 20. It **loads and runs standalone**
(`__name__`-isolated `exec`, no `/kaggle/input` dependency): 720 steps vs itself, both seats
`status=DONE`, reward 110,239 / 110,239 (mirror-symmetric). No build step was needed.

## 2. Instrument and protocol

`scripts/ab_duel.py`, paired: each seed is played twice with the seats swapped, so the engine's
documented seat-0 advantage cancels; the reported Δ is the mean over the two seat assignments and
`t` is the t-statistic over the 30 per-seed deltas. Configuration `episodeSteps=720`, seed set as
specified; the same seed is the same town. Every run reported here shows `errors=0` (no seat left
`DONE`). 60 games ≈ 45 s, 10 processes.

Per standing instrument discipline:
- `layer_fallbacks = 0`, `entry_fallbacks = 0`, `race_errors = 0` on **both** seats of **all five**
  pairings. The hook records only non-zero counters; no pairing produced a non-zero key for any of
  the three. (`data/matchup-*.json` → `cand_diag` / `base_diag`.)
- **Control 1 — self-duel.** live line vs itself, seeds 9000–9003: Δ = **+0**, t = 0.00, 0/0,
  wallets 91,013 vs 91,013, and **every** action counter came out identical (+0), idle share
  7.30 % vs 7.30 % (`data/matchup-control-selflive.json`).
- **Control 2 — harness neutrality.** The counter hook added to `ab_duel.py` is purely additive, and
  that is *measured*, not asserted: re-running a pre-existing duel
  (`wool_drain1_outerprem` vs `data/race/outer_prem/main.py`, seeds 9000–9029) reproduced
  `data/forward/duel-stack-vs-outerprem-IS.json` **exactly** — identical Δ/t/W/L/wallets/errors,
  identical action-mix counters, and all 30 per-seed deltas equal to 6 decimal places
  (`data/matchup-control-harness-neutral.json`).
- Nothing was rebuilt for this task, so no byte-identical-rebuild check was required.
- Plan-level edits are absent by construction: no file was modified except the additive hook, and
  no agent byte was changed.

## 3. What the two builds do differently (observational, not causal)

Action mix over 60 games (candidate minus base, headline IS): `FERTILIZE` **+484**, `PASS` +990,
`BUILD_PASTURE` +76, `HARVEST` +6, `PLANT` ±0; the candidate takes **less** `WATER` (−718),
`COLLECT_FERTILIZER` (−244), `MOVE` (−1,164) and `BUILD_COOP` (−76), and its hands are marginally
less often on `CARE` (−58). Idle share 7.79 % vs 7.54 %. The internal counters show the candidate
is running its race layer continuously (`RACE_race_clone_turns` ≈ 18,724 = ~312 of its 720 steps
per game; `race_errors = 0`) and only occasionally rewriting a sale (`RACE_cs_rewrites = 14`,
`RACE_cs_sold = 14`). So the margin is associated with a **more fertilizer-spending, less mobile**
policy on the same 41-route tape — the tape blob is byte-identical to ours (`54fe156ea7206e38`,
Task 20). I make no claim about which layer causes how much of the +4.8 k; that needs an ablation
inside the composite, which this task did not authorise.

## 4. The ladder context, and the caveat that comes with it

The human's framing was: V42 peaked at **2,681.9** on the ladder, so a large local margin for the
composite would make it a plausible medal candidate. Two things must be said plainly.

1. **No monotone local-wallet → ladder-rating map has ever been measured — by us or, as far as our
   artifacts show, by anyone.** Our duels score a 720-step single-town head-to-head wallet; the
   ladder is a rating that emerges from many ongoing games against other teams, and it is *not* a
   function of that wallet that we have ever calibrated. Every sentence in this report about the
   ladder is therefore conditional, and I am **not** implying a point conversion.
2. Worse, our own history contains a measured **counterexample to the naive ordering**: the locally
   *stronger* build displayed a *lower* score than the locally weaker one. On the same night,
   `V42 + room_guard + clamp_sells` measured **+463 (t=10.2)** over the plain V42 baseline, yet the
   baseline's displayed peak was 2,681.9 while the stronger build displayed 2,468.8 → 2,360.6
   (`REPORT-night-3-result.md`, `REPORT-public-frontier.md`). Local strength did not order the
   ladder readings.

The mechanism behind that, recorded in `REPORT-top5-and-planner.md` §10 from our own leaderboard
pulls: the displayed public score is the **currently tracked submission's** live score — replaced
submissions stop playing and their score disappears — and the rating needs hours of games to
converge, with swings of roughly ±5 % observed on the top of the board. Concretely, the
**byte-identical** V42 baseline was submitted at least twice (56258384 on 09-15, 56307879 on 09-17),
while our displayed score over that same stretch moved 2,681.9 → 2,520 → 2,360.6 → **1,985.1**
(latest local `data/leaderboard.json` pull, 2026-09-20 17:10, our row: `submissionDate`
2026-09-19T05:49:34Z, i.e. the live line 56349751, rank 1,711/9,625). In the same snapshot the top
of the board is 3,277.6 with the top five between 3,057.7 and 3,277.6. So the reading we would be
comparing a new submission against is a moving, age- and tracking-dependent number, and the "2,681.9
baseline" is not a stable level that a new line has to beat.

Conclusion for the decision: **the local margin is large and clean** (60/60 seeds positive on the
headline pairing, two independent seed panels, 29–30/30 against the live and champion bases), and it
is the strongest single piece of evidence we hold that the composite line is better than anything we
have built. **It does not license a ladder or medal prediction**, and any such prediction should be
stated as a hypothesis to be tested by an actual submission and hours of convergence — which is the
parent's call, not this task's.

## 5. Artifacts

| File | Content |
|---|---|
| `data/matchup-meta13-v42-is.json` | headline IS, per-seed deltas + counters |
| `data/matchup-meta13-v42-oos.json` | headline OOS panel (9100–9129) |
| `data/matchup-meta13-live-is.json` | vs live line 56349751 |
| `data/matchup-meta13-champion-is.json` | supplementary vs champion |
| `data/matchup-live-v42-is.json` | supplementary: live line vs V42 baseline |
| `data/matchup-control-selflive.json` | control 1, self-duel (Δ = 0, all counters +0) |
| `data/matchup-control-harness-neutral.json` | control 2, reproduces the pre-existing duel exactly |
| `scripts/ab_duel.py` | instrument; one purely additive diagnostics hook, neutrality measured in control 2 |

Each JSON carries `per_seed` (seed, delta, n), `delta`, `t`, `wins`, `losses`, `cand_wallet`,
`base_wallet`, `errors`, `cand_mech`/`base_mech` (action mix) and `cand_diag`/`base_diag`
(internal counters).
