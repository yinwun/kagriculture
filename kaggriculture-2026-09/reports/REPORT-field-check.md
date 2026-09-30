# Field check (Task 32) — did the field change, and do newer/better public versions exist?

Date: 2026-09-24/25. Measurement only. **No submission; no live file touched.**

## 0. Verdicts in two lines

**(A) The collapse is Elo regression to the line's true level, not a stronger field.** The ladder's
cutoffs **fell** over the last three days (top1 −69, top5 −110, top10 −105 points), so the top of the
ladder did not get stronger in absolute terms; the collapsed ref's recent opponents average **2,336**
against our displayed **2,272.5** — i.e. the matchmaker moved it into the band where it loses — and
**15 of its 18 recent losses are to opponents rated above us**.

**(B) No newer/better public version exists on our instrument.** Of 23 new notebooks, only **two**
yield a runnable agent, **both carry our exact tape blob `54fe156ea7206e38`**, and neither beats
`comp_straw` (one positive but t≈1.4, one negative). The highest-claim new notebook
(`statma/kaggriculture-thomas-2944-candidate`, "2944") is not even a runnable agent.

## 1. (A) Field-change test

Fresh ladder: **our displayed score 2,272.5** (down from 2,658.7 on 09-22 and 2,648.9 on 09-23).
Tracker: 56523821 90 games 69/21/0 = **76.7 %** (opp mean 1,820); 56496301 189 games 110/79/0 =
**58.2 %** (opp mean 2,191); 56496292 159 games 82/65/12 = **51.6 %** (opp mean 1,978).

### (i)–(iii) window split of the three refs' own game lists

| ref | window | n | win % | median margin | mean opponent | new-submission share | losses to opponents rated **above us** |
|---|---|---|---|---|---|---|---|
| **56523821** | all | 91 | 75.8 % | +771 | 1,825 | 95.6 % | 5/22 |
| | last 20 | 20 | 75.0 % | +489 | **2,057** | 100 % | 2/5 |
| | earlier | 51 | 80.4 % | +2,619 | 1,664 | 94.1 % | 1/10 |
| **56496301** | all | 190 | 57.9 % | +222 | 2,191 | 96.8 % | 56/80 |
| | **last 20** | 20 | **10.0 %** | **−644** | **2,336** | 100 % | **15/18** |
| | last 40 | 40 | 30.0 % | −322 | 2,340 | 97.5 % | 25/28 |
| | earlier | 150 | 65.3 % | +314 | 2,152 | 96.7 % | 31/52 |
| **56496292** | last 20 | 20 | 35.0 % | −50 | 1,974 | 95 % | 1/12 |
| | last 40 | 40 | 22.5 % | −140 | 2,086 | 97.5 % | 9/28 |
| | earlier | 120 | 60.8 % | +546 | 1,944 | 95.8 % | 14/38 |

"New-submission share" = fraction of opponents whose submission id we had never seen in any earlier
episode snapshot (1,171 previously-seen submissions). It is 95–100 % in every window: the field churns
builds continuously, but that is partly an artefact of snapshot age and is **not** evidence of
*stronger* builds.

### (iv) Cutoff history from our own tracker (`data/cmp-track.csv`)

| day (last sample) | teams | our score | our rank | top 1 % | top 5 % | top 10 % |
|---|---|---|---|---|---|---|
| 2026-09-21 | 9,732 | 2,480.1 | 842 | 2,811 | 2,617 | 2,417 |
| 2026-09-22 | 9,873 | 2,658.7 | 276 | 2,765 | 2,573 | 2,385 |
| 2026-09-23 | 9,897 | 2,423.8 | 807 | 2,736 | 2,527 | 2,340 |
| **Δ over the history** | **+204** | | | **−69** | **−110** | **−105** |

**Reading.** The hypothesis "the field got stronger" predicts rising cutoffs and losses to an
ascending opponent set. What we measure is the opposite on both counts: the cutoffs **fell 69–110
points** while the team count grew by only 204 (≈2 %), and the collapsed ref's opponents sit at
2,336 — **just above our displayed 2,272.5 but far below the 2,658.7 the same line displayed two days
earlier**. Its win rate fell from 65.3 % (earlier 150 games, opponents 2,152) to **10 %** (last 20,
opponents 2,336) with 15 of 18 losses to higher-rated teams: that is the signature of a rating that
overshot and was fed opponents at its true level, i.e. **Elo regression**. The newest ref
(56523821, 76.7 % wins against a 1,820-mean field) shows the same mechanism from the other side: a
lower-rated line farms easy games until it reaches its level. **There is no measurement here that
requires new or stronger opponent algorithms to explain the collapse.**

## 2. (B) New notebooks and provenance

23 notebooks are new since the Task-29 list. The 18 newest were pulled and hashed; 5 further
high-claim ones were pulled directly.

| notebook | provenance |
|---|---|
| `tetsutani/demand-preserving-turn-sale-timing`, `haideptry/the-shepherds-ledger-herd-safe-sovereign`, `haideptry/the-2965-master-hybrid-engine` | **our blob** `54fe156ea7206e38` (same tape + more layers); shepherds-ledger declares sha256 `ae44d83b…` **verified** |
| `hanifnoerrofiq/pioneers-of-kaggle-town-candidate-2` | different payload `43555ecc7debd05c` — **fails our zlib/JSON route-table decode**, i.e. not certified as new route data (like the Task-29 action-tape case) |
| `statma/kaggriculture-herd-safe-sale-window-race-ca25` | **our blob**, sha256 `c4b72e64…` verified |
| `statma/kaggriculture-thomas-2944-candidate` ("2944") | 25,403-char plain source; **not runnable** (tries to write `/kaggle`) |
| `kaggriculture-utils-v1`, `cha22-agent`, `graph-reinforcement-learning` | plain source, **not runnable** (`NameError: WORKDIR`, `KeyError: 'agent'`) |
| `herd-safe-v3-experimental-risk-aware-feed`, `population-robust-economy`, and the rest | no `main.py` cell / dataset path — not offline-runnable |

**Runnable new candidates: exactly two, both carrying our tape.**

## 3. Duels vs our current best (`data/composite/comp_straw/main.py`)

Unused panels, paired, seats alternating, 60 games each: **IS 9900–9929 / OOS 10100–10129**.

| candidate | panel | Δ wallet | t | W–L | wallet cand / base | exceptions | verdict |
|---|---|---|---|---|---|---|---|
| **the-shepherds-ledger-herd-safe-sovereign** | IS | **+360** | +1.38 | 40–20 | 92,358 / 91,999 | 0/0 | positive, **fails t ≥ 3** |
| | OOS | **+239** | +1.48 | 34–26 | 97,122 / 96,883 | 0/0 | positive, **fails t ≥ 3 and Δ ≥ 300** |
| **kaggriculture-herd-safe-sale-window-race-ca25** | IS | −280 | −1.10 | 22–38 | 92,102 / 92,383 | 0/0 | no-go |
| | OOS | −275 | −1.67 | 20–40 | — | 0/0 | no-go |
| utils-v1 / cha22-agent / graph-rl / thomas-2944-candidate | — | — | — | — | — | — | **not runnable** (smoke: wallet stuck at 3,000) |

Errors: `err = 0` and `cand_exceptions = base_exceptions = 0` in all four completed cells; the smoke
gate (720-step mirror, DEAD = wallet frozen at the 3,000 start) rejected the four non-runnable ones
before any duel.

**Bar for "better" (Δ > 0 with t ≥ 3 on both panels): not met by any candidate.** Therefore the
stacking step is vacuous — there is no winner on which to rebuild our layers.

## 4. One-line verdicts

* **Newer/better public versions: none that beat us.** The two runnable new candidates carry our exact
  tape (`54fe156ea7206e38`); one is positive but statistically indistinguishable from us (t ≈ 1.4) and
  the other is worse; the "2944" claim is not a runnable agent at all.
* **Field change: the collapse is Elo regression, not a stronger field** — cutoffs fell 69–110 points
  over three days, the collapsed line was moved to opponents averaging 2,336 (just above our displayed
  2,272.5 but 386 below its own two-day-old display), and 15 of its 18 recent losses were to
  higher-rated teams.
* **Practical implication for T-3:** our best build (`comp_straw`) is still ahead of everything we can
  extract from the public frontier, and the score drop is a rating-convergence effect that a fresh
  submission of the same line (or of `comp_straw` unchanged) addresses by resetting the age/tracking
  clock — consistent with the Task-29 recommendation.

## 5. Artifacts

| file | content |
|---|---|
| `scripts/t32_field.py` | window splits, opponent-rating distributions, new-submission share, cutoff history |
| `data/episodes-{56523821,56496301,56496292}-raw.json` | the three refs' game lists |
| `data/notebooks-t32.csv`, `data/notebooks-t32-fresh.txt` | the fresh notebook list (23 new since Task 29) |
| `data/provenance-guard-t32.json` | blob hashes for the 18 newest notebooks |
| `scripts/t32_duels.py`, `log/t32-duels.log` | smoke gate + duel runner and its output |
| `data/composite/duel-t32-*.json` | the four duel cells (per-seed deltas, counters, exceptions) |
