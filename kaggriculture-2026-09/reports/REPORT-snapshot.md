# Snapshot hunt (Task 10) — there is no newer snapshot; the frontier's edge is its layer stack

Date: 2026-09-19. Base/live line: the STACK `data/forward/wool_drain1_outerprem/main.py`
(submitted, ref 56349751). Instrument: `scripts/ab_duel.py` (paired, seats alternating,
60 games per panel) plus `scripts/extract_snapshot.py` and `scripts/build_opening.py`.

## 0. Headline

1. **There is no newer upstream route snapshot to extract.** The compressed route table
   (`_R108_DATA`, the yhay81 shop-router data our champion already replays) is
   **byte-identical** in all three local builds of this lineage:

   | build | measured value | blob sha256 | routes | actions |
   |---|---|---|---|---|
   | `data/tapeopt/rgcs/main.py` (champion) | ladder 2,147.5 | `54fe156ea7206e38` | 41 | 3,982 |
   | `data/cand/demand-preserving-turn-sale-timing` | +2,468, t=4.77 | `54fe156ea7206e38` | 41 | 3,982 |
   | `data/cand/the-2945-farm-96-vs-the-top-10-public-bots` | +4,407, t=6.04 | `54fe156ea7206e38` | 41 | 3,982 |

   So the "newer snapshot" hypothesis is refuted: the frontier did not move to newer
   upstream tape data.
2. **Diffing the *effective* tapes** (`_IMPL.chassis.routes`, after every composite's own
   post-load edits) sharpens it: tetsutani's 41 tapes are **100% identical** to ours, and the
   frontier's differ in **41 of 29,479 step-slots — exactly one step per route, always step
   0** — the opening market sequence, with **zero** differences in any farmer/hands action:

   | step 0 market list | |
   |---|---|
   | our champion / tetsutani | `BUY_PRODUCT WHEAT 5`, `BUY_PRODUCT WHEAT 10`, `SELL WHEAT 60` |
   | the-2945 frontier | `BUY_PRODUCT WHEAT 13`, `BUY_PRODUCT WHEAT 30`, `SELL WHEAT 30` |

3. **That opening is the whole extractable plan-data delta, and it does not earn its place
   on our stack.** Applied as a step-0 overlay on the live stack
   (`data/snapshot/opening/main.py`): **+632, t=+3.58, W/L 43/17 vs the champion** — but
   **−166, t=−1.67, W/L 3/57 vs the live stack**. It is a real standalone edit (clears the
   bar against the champion) and a net minus on top of our own layers, so it is not kept.
4. **Best build unchanged**: the submitted stack. Fraction of the frontier's +4,407 now
   explained: **~18% IS / ~25% OOS** (the stack: +790 IS / +1,099 OOS over the champion).
5. The consequence is that the frontier's edge is **its ~120-layer composite itself**
   (sell-timing family, herd heuristics, opening, and their parameters), not newer upstream
   data and not any single mechanism — every mechanism we could rebuild has now been
   measured one family at a time (Tasks 1–9) and totals 18%/25%.

## 1. Extraction (step 1–2 of the brief)

`scripts/extract_snapshot.py` decodes every `base64.b85decode` + `zlib.decompress` blob in a
build in our exact shape (`{actions, routes}`, `routes` = id → action indices) and writes it
with a provenance header. Artifacts:

* `data/snapshot/champion_r108.json` / `.blob.txt` — our own table, for reference;
* `data/snapshot/tetsutani_dp.json` / `.blob.txt` — tetsutani's, **identical** blob;
* `data/snapshot/the2945.json` / `.blob.txt` — the frontier's, **identical** blob.

Headers name the source file, author, `Apache-2.0`, the notebook reference and the measured
value, the blob sha256/size, route and action counts, route ids, route lengths and max step.
Verification: the extracted tables replay through our chassis for 720 steps with all error
counters 0 (`layer_fallbacks`, `entry_fallbacks`, `race_errors`), because they are the same
table the champion already replays — `data/snapshot/opening/main.py` was run end-to-end for
this (0/0/0).

**Because the blobs are identical, the brief's `snapshot/plain` build (our chassis + new
tapes + champion settings) is not constructible: there are no new tapes to install.** I
verified that positively rather than assuming it, by extracting and hashing the data and by
diffing the effective tapes (both above), rather than by inspecting the obfuscated source.

## 2. The one real difference, measured

The frontier's step-0 opening is a legitimate upstream-lineage edit (their own "funded
opening"), so I applied it as the narrowest possible overlay on top of our stack
(`scripts/build_opening.py`, one step, no other change) and duelled it both ways:

| candidate | base | IS delta | t | W/L | wallet |
|---|---|---|---|---|---|
| opening overlay on the stack | champion | +632 | +3.58 | 43/17 | 104,718 vs 104,086 |
| opening overlay on the stack | **the live stack** | **−166** | **−1.67** | **3/57** | 104,239 vs 104,405 |

Interesting in its own right — a single-step tape edit is worth +632/town against the
champion, i.e. of the same order as our entire race layer — but on top of our own layers it
is a small net minus, and out-of-sample was not run because the head-to-head against the
live line is already non-positive (protocol: only winners advance). Error counters 0 on the
build; the action counters show it changes PLANT (−120) and PASS (+113) over 60 games, i.e.
it shifts the early cash/seed plan slightly, which is why it interacts with our layers.

## 3. Which layers earned their place

No layer changes in this round: with no new tapes there is nothing to re-tune, and the one
extractable delta (the opening) fails its head-to-head. The standing answer from Task 8 is
unchanged — `outer_prem` (race layout) + `wool_drain1` (drain-keyed forward sales) are the
two layers that earn their place, and the herd/wheat/rule/hypothesis families do not.

## 4. Runtime and error counters

* `data/snapshot/opening/main.py`: 720-step end-to-end run and a 60-game duel with
  `err=0`; `layer_fallbacks 0`, `entry_fallbacks 0`, `race_errors 0`.
* Per-step wall clock is unchanged by a step-0 edit; the last measured figures stand
  (`scripts/race_timing.py`: stack 0.5 ms mean / 0.2 median / 0.8 p95 / 56.5 ms worst, with
  the champion alone at 1.5 ms / 3.0 / 135 ms under the same harness in an earlier run —
  absolute values track machine load, the layer's share is sub-millisecond).

## 5. Assessment: where the remaining ~75% is, and what to do

The residual is **not** newer tape data (§0), **not** the route/tape selection (Task 4),
**not** the herd composition, sheep-days, care, or wheat (Tasks 2, 5, 9), and **not** the
market layer on any of its four axes (Tasks 1, 3, 6, 8 — +790 extracted against a
perfect-information oracle of +513/+963). The frontier is a ~5,700-line composite of roughly
120 stacked layers from many public authors; its edge is the *sum* of that stack, and its
tapes are the same as ours. Our repo's practice (and the standing instruction) is not to
vendor a foreign agent wholesale, so the reproducible path is exactly what we have been
doing — rebuild each mechanism family ourselves and measure it — and that path has now been
walked to its end: **+790 IS / +1,099 OOS, 18%/25% of the frontier's edge.**

Options, honestly ranked for the remaining 75%:

* (a) **Extract more of the frontier's *layer* families one at a time** (the way we extracted
  and measured its opening) — expensive: each family needs a clean reimplementation from the
  engine rules plus a full paired duel, and the composite is largely obfuscated. Tasks 1–9
  suggest each family contributes hundreds, not thousands, so closing 75% this way is a
  long multi-round effort.
* (b) **A from-scratch tape re-plan** (a 719-step search), whose every candidate needs a
  full 60-game paired duel and whose objective can flip the shop draw — days to weeks,
  uncertain payoff.
* (c) **Accept the current line.** It is measured, submitted, and reproducible, and every
  cheaper channel has been tested and closed.

My recommendation is (a) only if the human wants to keep investing rounds, otherwise (c).

## 6. Artifacts and rebuild

```bash
# extraction (writes data/snapshot/<name>.json + .blob.txt with provenance headers)
.venv/bin/python scripts/extract_snapshot.py --file data/cand/the-2945-farm-96-vs-the-top-10-public-bots/main.py \
    --name the2945 --author "thomastschinkel et al. (composite)" \
    --ref "kaggle notebook thomastschinkel/the-2945-farm-96-vs-the-top-10-public-bots (+4407 vs champion)"
# the one extractable delta, as an overlay on the live line
.venv/bin/python scripts/build_opening.py --base data/forward/wool_drain1_outerprem/main.py --name opening
.venv/bin/python scripts/ab_duel.py --cand data/snapshot/opening/main.py \
    --base data/forward/wool_drain1_outerprem/main.py --seeds 9000-9029 --procs 10 \
    --label opening-vs-STACK-IS --out data/snapshot/duel-opening-vs-stack-IS.json
# the live line, unchanged, for reference
python scripts/build_race.py --name outer_prem
python - <<'PY'
import sys; sys.path.insert(0, "scripts")
import build_forward
build_forward.build({"forward_items": ["WOOL"], "forward_drain": True},
                    "wool_drain1_outerprem", "data/forward",
                    base_path="data/race/outer_prem/main.py")
PY
```

Artifacts: `scripts/extract_snapshot.py`, `scripts/build_opening.py`,
`data/snapshot/{champion_r108,tetsutani_dp,the2945}.{json,blob.txt}`,
`data/snapshot/opening/main.py`, `data/snapshot/duel-opening-{IS,vs-stack-IS}.json`.
Nothing submitted to Kaggle.
