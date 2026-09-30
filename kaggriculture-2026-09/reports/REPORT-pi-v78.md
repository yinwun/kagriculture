# REPORT — the V78 frontier base and the `pi_stack` submission (Task 40 → submit)

**Date:** 2026-09-28 ~13:40 UTC · **Outcome:** submitted ref **56642424** (the best build ever measured in this project)
**Artifacts:** `data/candidate/pi_stack/main.py` (sha256 `65962e928b071294…`) · `data/submits/ready-pi_stack.tar.gz` (sha256 `7e30ab4a45e13dd0…`) · rebuild: `.venv/bin/python scripts/t40_stack.py` · scan report: `REPORT-frontier-3.md`

---

## 0. Headline

After six failed sweeps for a stronger public base, one was finally found that clears the
decision bar decisively. Our market layers were stacked onto it, the stack was smoke-gated,
timed, paired-duelled on fresh panels, and submitted.

**`pi_stack` beats our previous best `shep_v_cap24` by +1,666 coins/game ≈ +1.7 % wallet ≈ +250 rating points**
— which is essentially the entire gap the project has been chasing all week.

---

## 1. A correction I owe the record

While reading the scan I claimed the winning notebook carried **new** route data because the
literal string `54fe156ea7206e38` does not appear in it. That was **wrong**. The subagent
hashes the *decoded* payload, and the decoded route table is **byte-identical to ours**
(`54fe156ea7206e38`); the string is simply base85-encoded in that notebook.

**So: no new data exists anywhere on the frontier. The gain is a better engine on the same data.**
That is the sixth independent confirmation that the tape blob is universal, and it retires the
"find newer upstream data" route for good.

## 2. Provenance of the field (newest 20 notebooks)

| notebook | route payload |
|---|---|
| `leoprovorov/3141592…4197169399` — **the winner**, "Kaggriculture V78 Master Engine" | **ours** `54fe156ea7206e38` |
| `haideptry/the-2965-master-hybrid-engine`, `guruprasaathas111/kaggriculture-top-2-master-engine-v4`, `haideptry/the-shepherds-ledger-herd-safe-sovereign`, `tetsutani/demand-preserving-turn-sale-timing` | **ours** `54fe156ea7206e38` |
| `guruprasaathas111/kaggriculture-master-engine-v53e01d74d8f`, `evgendvorkin/…bronze-going-up`, `kunaldesale2408/kaggriculture-2026-v1` | `5df1c84699004845` = `{base,patches}` **action tape** (a re-encoding, not a route table) |
| remaining 12 | no route payload exposed (dataset / base85 attachment) |

## 3. Screening result — 12 candidates, exactly one survives

Paired duels, seats alternating, vs our strongest build `shep_v_cap24`, panels 13000–13029 / 13100–13129, all `err=0`.

| candidate | p1 Δ / t | p1 W–L | p2 Δ / t | p2 W–L | verdict |
|---|---|---|---|---|---|
| **`leoprovorov/3141592…4197169399` (V78)** | **+1,142 / +8.78** | **60–0** | **+1,071 / +6.28** | **56–4** | **GO** |
| the-2965-master-hybrid-engine | −410 / −2.77 | 12–48 | −495 / −4.88 | 18–42 | no |
| top-2-master-engine-v4 | −537 / −3.37 | 8–52 | −522 / −4.02 | 16–44 | no |
| master-engine-v53e01d74d8f | −3,341 / −5.86 | 2–58 | −4,447 / −8.65 | 2–58 | no |
| shepherds-ledger-herd-safe-sovereign (our own base, alone) | −155 / −2.05 | 17–43 | −91 / −0.94 | 20–40 | no |

Note what this says: the *same* route data plus a *newer engine* is worth +1,142, while our old
base **without** our layers is *worse* than our old base **with** them. Policy beats data here.

## 4. The stack and its evidence (all numbers fresh panels, seats alternating)

| build | opponent | n | Δ | t | W–L |
|---|---|---|---|---|---|
| `pi_base` (V78 alone) | `shep_v_cap24` | 120 | **+1,109** | +8.65 | 102–18 |
| `pi_stack_raceonly` (base + race layer) | `pi_base` | 120 | +152 | +8.99 | 110–4 |
| **`pi_stack` (base + race + forward)** | `pi_base` | 120 | **+593** | +10.86 | 118–2 |
| **`pi_stack`** | `shep_v_cap24` | 60 | **+1,612** | +8.91 | 60–0 |
| **`pi_stack`** | `shep_v_cap24` | 60 | **+1,720** | +8.29 | 58–2 |

Decomposition is self-consistent: base +1,109, our layers +593 on that base ⇒ +1,666 total.
Our layers are worth **~3× more on the V78 base than on the shepherds base** (+593 vs +112/+64 pooled),
which is expected: the shepherds base already contained its own `_v92_*`/`_v44y_*`/`_race_*` market
layers that partly duplicate and partly fight ours.

Composition of `pi_stack` (all outermost wrappers, market list only, never quantities):
1. **race/slot search** — own lockstep replica, maximises `revenue_me − revenue_opp`
2. **wool/strawberry/milk sell-forward** — `forward_drain=True`, `forward_drain_mult=24.0`, late start 312 for strawberry/milk

Controls: **forward-off control Δ = +0.0, t = 0.00**; smoke `['DONE','DONE']` with an **empty error dict**;
`cand_exceptions = 0`, `errors = 0` in every cell.

## 5. A second correction — the runtime scare was an artifact

The scan reported mean 19.4 ms / p99 267 ms / **max 836.8 ms** per step (84 % of the 1 s `actTimeout`)
and recommended trimming the build. That measurement was taken while 8-process duels and the scan
itself were saturating the machine. Re-measured on an idle machine (`composite_timing.py --seed 14000`):

| build | mean | p95 | p99 | max | >250 ms | full game |
|---|---|---|---|---|---|---|
| V78 base alone | 3.3 ms | 6.5 | 46.9 | 208.0 | 0 | 9.5 s |
| `pi_stack_raceonly` | 4.2 | 7.2 | 58.3 | 240.6 | 0 | 11.5 s |
| **`pi_stack` (full)** | **3.6** | **6.5** | **39.5** | **161.2** | **0** | **10.3 s** |
| `shep_v_cap24` (incumbent) | 2.8 | 5.5 | 10.1 | 118.2 | 0 | 8.9 s |

Worst step is **16 % of `actTimeout`**, nothing exceeds 250 ms, and the full stack is *faster at the
tail than the base alone* (161 vs 208 ms — plan/RNG divergence, not a defect). **No trimming needed.**
Lesson, again: never read a timing number taken under load.

## 6. Submission

- **ref 56642424**, submitted **2026-09-28 13:37:25 UTC**, status PEND at submit time, quota 5/5 used for the day.
- Supersedes **56627360** (`cap24`, frozen at 1,761.1); the tracked pair is now
  **{56642424 `pi_stack` (fresh, 0 games), 56627381 `shep_straw` 1,842.2}**.
  Displayed score = better of the two, so nothing was lost — `cap24` at 1,761 was not the displayed line.
- Description records provenance honestly: the V78 base is public and not our work; the market layers are ours.

## 7. Monitoring

`scripts/push_live.py` had **two** label defects, both now fixed and verified by push:

1. the key `"x24"` also matched ARM B's description ("… the matched x1-vs-x24 experiment …"),
   so ref 56627381 (`shep_straw`) was labelled `cap24` and the real `cap24` row was untracked;
2. the description is lowercased before matching, so newly added keys had to be lowercase —
   an uppercase key matched nothing and silently fell through to `x2`.

The renderer also crashed on a freshly submitted instance (score `None`); it now prints `NEW`.
Current push reads correctly:

```
cap8        1930.9  118g wr20  50%(+0) wr10  50%(+0) opp20  1856 [flat]
shep_straw  1842.2  100g wr20  30%(+0) wr10  20%(+0) opp20  1986 [flat]
cap24       1761.1   83g wr20  60%(+0) wr10  50%(+0) opp20  2002 [flat]
pi_stack       NEW    0g (awaiting first episodes) ref=56642424
```

Live standing at push time: **1,842.2**, rank **1,621/10,120** (top 16.0 %); cutoffs 1 % 2,594, 5 % 2,279, 10 % 2,071.
Crontab pushes every 30 min; `PUSH_FORCE=1` bypasses the dedupe guard.

## 8. What to watch, and the decision it drives

The open question is **ladder translation**, not local strength: every build's *local* edge has
been ~+1.7 % wallet, and our landings have been noisy (median 2,058, mean 2,131, 8/18 ≥ 2,131).
The `pi_stack` line starts from zero and should take ~2 h to converge.

- If it **converges above ~2,050**, it becomes the displayed line and the submission was worth it.
- If it **stalls near 1,700–1,800** like `cap24` did, that confirms the ladder saturates below the
  local edge, and the remaining days are better spent holding the strongest code than churning slots.
- Either way: **do not resubmit to refresh.** Every submission freezes a running line.

Remaining days: submit nothing further unless a build clears Δ > 0, t ≥ 3 on two fresh panels.
Otherwise hold `pi_stack` + `shep_straw` into the 16-day closed period.

---

## 9. Task 41 — is drain_mult=24 still optimal on the NEW base? (answer: yes)

Every parameter sweep in this project was run on the **old shepherds base**, so the optimum could
have moved when the base changed. Five variants were rebuilt on the V78 base (all five smoke
`['DONE','DONE']` with an empty error dict) and duelled against the submitted champion
(`pi_stack`, drain_mult = 24) on fresh panel 15000–15029, then the best was confirmed on
unused panel 15100–15129.

| variant | screen Δ | screen t | W–L | confirm Δ | confirm t | W–L |
|---|---|---|---|---|---|---|
| dm = 1 | −458.4 | −9.14 | 3–57 | — | — | — |
| dm = 2 | −421.8 | −9.06 | 3–57 | — | — | — |
| dm = 8 | −160.2 | −5.95 | 9–51 | — | — | — |
| dm = 12 | −34.6 | −2.45 | 19–39 | — | — | — |
| **dm = 24 (champion)** | — | — | — | — | — | — |
| dm = 48 | −3.5 | −2.06 | 8–14 | −4.3 | −2.69 | 11–21 |

All `err=0`, `cand_exceptions=0`. The curve is **monotone from 1 → 24 and flat-to-slightly-negative
at 48**, which is both a real optimum and a liveness check: a knob with no effect would have
produced byte-identical output and Δ exactly 0, and a bug would have produced a flat or random
curve. Note the small decisive-game count at dm=48 (22 of 60): with a higher release cap the
forward layer binds less often, so many games become byte-identical ties against the champion.

**Verdict: NO EDGE — champion stays.** `pi_stack` at drain_mult = 24 is confirmed optimal on the
new base as well, so there is nothing to submit from this knob. The remaining submission slots
should not be spent on it.

This closes the last untested parameter family on the frontier base. Together with §1 (no new
data exists anywhere on the frontier) the picture is now: we hold the strongest measured build,
its key knob is at its optimum, and further local tuning has nowhere obvious left to go.

---

## 10. Task 43 — `_CA_MARGIN`, the last live knob on this base (answer: -22 is optimal)

The entire public frontier rolled `_CA_MARGIN` from -22.0 to -15.0 and rebranded it "V79"/"V85",
and the public narrative was that -22 hurt the ladder. Measured against our own bare V78 base that
rollback is a **regression**, and since the swap condition is

    pays_now = 3*(p_carrot - DROP) - 20 > 4*p_wheat - 10 + _CA_MARGIN

a *more negative* margin makes the carrot swap *easier* -- so everything below -22 was unexplored.

| `_CA_MARGIN` | screen Δ (18000-18029) | t | W–L | confirm Δ (18100-18129) | t | W–L |
|---|---|---|---|---|---|---|
| **-15.0** (public "V79" rollback) | −64.2 | −1.84 | 19–25 | — | — | — |
| **-22.0** (champion, self-check) | **+0.0** | +0.00 | 3–3 | — | — | — |
| **-30.0** | +7.3 | +0.54 | 25–21 | +11.3 | +0.35 | 28–28 |
| -40.0 | −28.0 | −0.44 | 18–38 | — | — | — |
| -55.0 | −425.4 | −3.72 | 9–47 | — | — | — |
| -70.0 | −1,549.4 | −3.30 | 5–55 | — | — | — |

**Verdict: NO EDGE — champion stays.** The curve peaks at −22…−30 (the two are statistically
indistinguishable, both t < 1) and falls off a cliff beyond −40. The base author's −22 was already
at the optimum.

Two independent validations came out of this sweep, and they matter more than the negative result:

1. **The self-check passed exactly.** Rebuilding the champion's own value produced `sha256
   65962e928b071294…` — byte-identical to the file we submitted — and Δ exactly +0.0. That proves
   the anchor replacement and the duel pipeline introduce no artifact of their own.
2. **Two independent measurements agree on the public rollback**: this sweep measured −64.2
   (t=−1.84) and the Frontier-4 scan measured −61 (t=−3.23) on completely different seed panels.
   The instrument is reproducible across operators, which is the strongest evidence we have that
   the whole measurement chain is sound.

`data/candidate/t43-ca-margin.json`, rebuild `.venv/bin/python scripts/t43_ca_margin.py`.

## 11. Closing position

Every lever on this base is now measured and closed: our own layer stack (race, forward, drain
multiplier 24, late strawberry/milk) is at a confirmed optimum, the base's own tunable constant is
at a confirmed optimum, no newer or stronger public engine exists on the frontier, and no public
notebook carries different route data. The loss money is production (EGG + WHEAT = 103 % of the
loss margin) inside the base's economy machinery, which is multi-week work, not a layer.

`pi_stack` was left alone to keep playing, and it kept climbing on its own.

---

## 12. Final submission: a second instance of the strongest build (ref 56657816)

Submitted **2026-09-29 00:54:55 UTC**, byte-identical to ref 56642424 (sha256 `65962e928b071294`).

**Why a duplicate rather than a new build:** there is nothing better to submit. Task 42 closed our
own layer stack, Task 43 closed the base's last live constant (`_CA_MARGIN`), and Task 43/Frontier-4
closed the entire public frontier (no newer engine, no different route data). A duplicate is the only
action with non-negative expected value: it takes a second independent draw of the best code, given
the large per-instance spread we have measured (the same `shep_straw` family has landed 2403.1 and
1785 under the same field), and it puts the strongest code in both tracked slots for the closed period.

**The historical trajectory is what makes the case, and it corrects an earlier belief.** Our own
`data/cmp-track.csv` shows our lines reach far higher than the current reading:

| when | our score | rank |
|---|---|---|
| 2026-09-21 07:03 | 2,499.5 | 791 |
| 2026-09-22 15:11 | **2,661.6** | **292** |
| 2026-09-22 23:57 | 2,658.7 | 276 |

and the 2026-09-22 evening sequence shows the mechanic plainly:

```
22:49  2642.7  rank 301      <- a warm line is carrying the score
23:05  1518.2  rank 2614     <- a new submission displaced it; the score collapsed
23:20  1752.5  rank 2110     <- the new line starts cold
23:57  2658.7  rank 276      <- it climbed back inside the hour
```

So (a) score **climbs with games played**, rather than saturating in 2 h as an earlier weaker-build
sample suggested; (b) a new submission only collapses the displayed score when it displaces the line
that is *carrying* it; and (c) our code has already reached 2,490–2,661 (rank ~276–301, top ~3 %),
which is the real target and it is a matter of accumulated episodes, not of code.

**Safety was verified empirically, not assumed.** A new submission displaces the OLDER of the tracked
pair, so `pi_stack` (56642424, the newer) had to survive. Measured across a 7-minute window:

| ref | build | episodes | verdict |
|---|---|---|---|
| 56642424 | `pi_stack` (carrying the score) | 102 → **103** | **still playing — intact** |
| 56627381 | `shep_straw` | 140 → 140 | frozen (displaced), as predicted |
| 56657816 | duplicate | 0 (cold start) | new line |

Tracking after the submission (`PUSH_FORCE=1`):

```
pi_stack    2184.3  102g  wr20 95%  wr10 90%  opp20 2152  [flat]
pi_stack2      NEW    0g  ref=56657816
shep_straw  1779.1  139g  (frozen)      cap24  1761.1   83g  (frozen)
```

Displayed **2,184.3, rank 622/10,141 (top 6.13 %), 155 points above the top-10 % line.**

## 13. Plan for the remaining time (deadline 2026-09-30 23:59 UTC)

1. **Submit nothing further** unless a genuinely new lever appears. Every measured lever is closed.
2. **Let both `pi_stack` instances accumulate episodes** — that is what moves the score, and the
   duplicate does not interrupt the original.
3. Monitor via the Telegram push (every 25 min, `PUSH_FORCE=1` to force) and the inbox poller
   `scripts/tg_inbox.py`, which now lets the user reach the agent from Telegram.
4. Two-source honesty note: Task 40's provenance rows for `the-2965`, `top-2-master-engine-v4`,
   `tetsutani` and `harvest-ledger` were STALE (`t40_frontier.py` only pulled notebooks whose local
   `.ipynb` was absent, so it measured 22–25 Sep bytes). The Task 40 winner is unaffected — V78 was
   pulled fresh and `pi_stack` is built from `836cbfb633583890` — but future scans must re-pull
   unconditionally.
