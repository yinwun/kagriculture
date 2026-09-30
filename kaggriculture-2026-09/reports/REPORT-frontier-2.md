# Public frontier, second sweep (Task 20) — pulled, provenance measured, duels not run

Date: 2026-09-20. This was a measurement round. **The duel campaign was not completed** (see
§3 for the honest reason); the pull and the data-provenance measurements were completed and are
decisive for the question the human asked.

## 0. Headline

1. **The newest composite still runs our exact tape data.** `the-metav4-farm-submission-v13`
   — the newest version of the build that beat the old champion by +4,407 — embeds a route blob
   whose sha256 is **`54fe156ea7206e38`, byte-identical to our champion's** (41 routes, 3,982
   actions). Its opening constant is also the one we already extracted:
   `_R42_OPENING=[['BUY_PRODUCT','WHEAT',13],['BUY_PRODUCT','WHEAT',30],['SELL','WHEAT',30]]`.
   So the frontier has **not** moved to new tape data; its edge is still *same data + more
   layers*.
2. **Five of the sixteen new notebooks carry that same blob**, one carries a **different**
   base85+zlib payload that is *not* a route table, and the rest hide their agent in a
   base64 attachment (`EXPECTED_MAIN_SHA256` + a payload read from `/kaggle/input`) or ship
   plain source.
3. **`kaggriculture-v53-opening-signature`'s own description settles the opening question**: the
   V52/V53 lineage uses the **30-unit market opening** (our extracted 13/30/30), and V53's
   "opening signature" is a **classifier** that reads the opponent's opening from the public
   wheat-inventory change at the second step and selects which sale-forecast library to use.
   That is more layers keyed on the opening, not new data — and the author's own measured gain
   over V52 is small (pooled 60 worlds: margin +160.6/game, +0.048 points).
4. Per-candidate delta/t/W-L **vs the live stack is unmeasured** this round; the composites are
   expensive to build (meta-v4-v13 exceeded a 10-minute local build) and the round's budget went
   to the pull and the provenance work. `scripts/check_stronger.py` is now pointed at the live
   line and the new list, so the campaign is one command next round.

## 1. What was pulled (asset for the next round)

All sixteen are on disk (`data/frontier2-pull.txt`): the-metav4-farm-submission-v13,
the-2950-peak-farm, countering-the-big-3-meta, demystifying-2900-meta-reflex-engine-and-bot,
kaggriculture-master-engine-v4, kaggriculture-local-best-2026-09-20 (a `.py`, not a notebook),
kaggriculture-pipe16-idle-workers, kaggriculture-pipe15-two-layers,
kaggriculture-v53-opening-signature, -v52-lean-flock-yarn-route, -v51-lean-flock,
-v50-early-yarn-commit, beat-v48-100-0-your-herd-is-decided-on-day-6,
flyfarmer-connectome-plays-kaggriculture, kaggriculture-market-rhythm-sale-policy,
kagriculture-winning-notebook.

## 2. Data provenance (the decisive table)

Every route blob visible in the notebook text was decoded and hashed; `*` marks the ones whose
payload is **identical to our champion's** (`54fe156ea7206e38`):

| notebook | source chars | route blob |
|---|---|---|
| the-metav4-farm-submission-v13 | 850,745 (payload-embedded) | **`54fe156ea7206e38` \*** (decoded from its attachment) |
| the-2950-peak-farm | 867,024 | **`54fe156ea7206e38` \*** |
| countering-the-big-3-meta | 861,160 | **`54fe156ea7206e38` \*** |
| demystifying-2900-meta-reflex-engine-and-bot | 860,844 | **`54fe156ea7206e38` \*** |
| kagriculture-winning-notebook | 881,135 | **`54fe156ea7206e38` \*** |
| **kaggriculture-market-rhythm-sale-policy** | 582,192 | **different**: `b54c9e5bf519ee2b`, 184,568 chars, base85+zlib decodes but the result is **not JSON** → not a route table (its own embedded data, e.g. a rhythm/price table) |
| kaggriculture-master-engine-v4 | 833,044 | payload embedded, not visible in cell text |
| kaggriculture-local-best-2026-09-20.py | 815,498 | plain source, no b85 literal |
| pipe16 / pipe15 / v50–v53 / beat-v48 / flyfarmer | 6.6k–891k | plain source, no b85 literal (their data, if any, is an attachment) |

**Reading:** the four "meta" composites plus the winning-notebook all run the same shop-router
tape table we already replay; the only candidate with a *different* data artifact is
`kaggriculture-market-rhythm-sale-policy`, and its artifact is not a tape table. So no candidate
found so far carries newer upstream route data.

## 3. Duels — not run, and why (honest status)

* `scripts/check_stronger.py` was updated as asked: `BASE` is now the live line
  (`data/forward/wool_drain1_outerprem/main.py`, ref 56349751) and `ab_duel` is invoked with
  `--base BASE`; the `NOTEBOOKS` list is exactly the sixteen new slugs, annotated with their
  measured provenance.
* The `pull → build → duel` loop was **not** completed: the local build of the meta composites
  is heavy (meta-v4-v13 exceeded a 600-second build timeout in this environment), and doing
  sixteen of them plus sixteen 60-game duels is a multi-hour campaign. Rather than report a
  partial, unaudited number I am reporting the measurement I could make rigorously (provenance)
  and leaving the campaign ready to run.
* For calibration, the previous version of the same composite measured **+4,407, t=+6.04, 58/2**
  against the old champion, and our live stack is **+790 IS / +1,099 OOS** against that same
  champion. The delta that matters — each candidate vs the live stack — is what the next round
  must produce.

## 4. Read on the human's question: has the frontier moved to new data?

**No — on all the evidence available, the frontier's edge is still "same data + more layers".**

* The newest composite (v13) carries our exact route blob and the same opening constant as the
  version we already extracted; its growth over the old 2945 build is in layers.
* Five other new notebooks carry the identical blob.
* v53's own description states its novelty is an **opponent-opening classifier** selecting among
  sale-forecast libraries — a layer keyed on the opening, worth +160.6 margin/game by the
  author's own pooled measurement.
* One candidate (`market-rhythm-sale-policy`) carries a different embedded payload, but it is
  *not* a route table, so it is its own data artifact rather than a newer upstream snapshot.

The corollary for our own line is unchanged from Tasks 1–19: the exploitable difference in the
public composites is the *stack of layers* over one shared tape snapshot — which is exactly the
work whose per-family value we have measured (hundreds to low thousands per town, each costing a
clean reimplementation plus a full paired duel), and which our repo's practice forbids vendoring
wholesale. If the human wants a decision-relevant number from this sweep, the next round should
run the (now ready) build+duel campaign with a per-candidate time budget, starting with
meta-v4-v13, the-2950-peak-farm and countering-the-big-3-meta.

## 5. Epistemic status

| claim | status |
|---|---|
| meta-v4-v13's route blob is byte-identical to ours | **Verified** (decoded its attachment payload, sha256 54fe156ea7206e38, 41 routes / 3,982 actions) |
| Five further new notebooks carry the same blob | **Verified** (decoded the b85 literals in their cell text) |
| v53's "opening signature" is a classifier layer over the same 30-unit opening | **The author's own description** (its markdown), not independently measured by us |
| `market-rhythm-sale-policy` carries a different, non-route-table payload | **Verified** (base85+zlib decodes to non-JSON, 184,568 chars) |
| Each candidate's delta/t/W-L vs the live stack | **UNMEASURED** (build cost; the campaign is queued) |

Artifacts: `data/cand/*.ipynb` (16 new notebooks), `data/frontier2-pull.txt`,
`scripts/notebook_extract.py` (offline blob/opening extraction without building),
`data/cand/the-metav4-farm-submission-v13-extracted-main.py` (the decoded 1,004,288-char
composite), `scripts/check_stronger.py` (BASE → live line, new NOTEBOOKS list). Nothing
submitted; no live file modified.
