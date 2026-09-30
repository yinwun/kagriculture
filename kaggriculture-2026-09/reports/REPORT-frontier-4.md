# Frontier scan 4 (Task 43) — nothing newer or stronger than V78 exists; the newest public engines are V78 with one constant flipped

**Date:** 2026-09-29 (UTC) · **Mode:** measurement and extraction only — **no submission, no live file touched**
**Champion instrument:** `data/candidate/pi_stack/main.py` — sha256 `65962e928b0712946e1bacb929b4fb919a7231f34e1bc99c7e350d4e2755f317`, 1,243,411 bytes
**Panels:** `17000–17029` / `17100–17129` — fresh, unused by t35–t42, 30 seeds × 2 seats = 60 games per cell, seats alternating
**Bar:** Δ > 0 **and** t ≥ 3 on **both** panels, vs `pi_stack`. **No candidate cleared it.**

---

## 0. Answer

**No public notebook carries a newer or stronger engine than the V78 base.** Every engine-bearing notebook
published or refreshed after V78 is either (a) the **same V78 source with the single constant
`_CA_MARGIN` flipped −22.0 → −15.0** (branded "V79", "V85"), (b) a *byte-behaviourally identical* copy of an
older lineage (shepherds / MarketShock / V16 / C95), or (c) a non-engine page (analysis, dataset, harness).

The only genuinely new public *engine content* on the whole frontier is that one constant. Measured with the
paired instrument it is **not** an upgrade:

| what | vs bare V78 (`pi_base`) | vs champion `pi_stack` |
|---|---|---|
| "V79 / V85" = `_CA_MARGIN −15.0` | **−61 (t = −3.23)** / **−60 (t = −1.86)** | **−765 (t = −9.21)** / **−479 (t = −7.74)** |

Four separate notebooks (`the-2965` "V79", `harvest-ledger` "V85", `demand-preserving`, and the compact
"idle-seller" rewrite that collapses 41 closure wrappers into one fixed-point pass) all deliver that *exact*
same duel table — the wrapper/closure differences between them are inert (§3.2).

Consequences:

1. **Step 4 (stack our layers) was not triggered for anything** — no candidate met the bar — so no new stack
   was built and **nothing should be submitted**.
2. Our champion's base choice is **not dominated**: the public's "evidence-led rollback" to −15.0 is a mild
   local *regression* (−60 coins/game over 120 games), i.e. the public narrative that the −22.0 margin caused
   rating decay is not supported by the only valid local instrument. `pi_stack` stays as built.
3. **Instrument self-control:** a byte-identical copy of `pi_stack` duelled against `pi_stack` gives
   **Δ = +0.0, t = 0.00, errors = 0, exceptions = 0** on 10 seeds.
4. **Correction owed to the record:** t40's provenance/duel rows for four notebooks were computed from
   **stale local `.ipynb` copies** (see §3.1). The current frontier content is re-extracted and re-screened
   here; the verdict (no-go) is unchanged, but t40's numbers for those rows describe 22–25 Sep bytes.

---

## 1. Discovery and coverage

| channel | what was done | result |
|---|---|---|
| competition kernel listing | `kaggle kernels list --competition kaggriculture` with all 7 pages × 3 sort orders (`dateCreated`, `dateRun`, `voteCount`) | **608 notebooks**, complete listing (`data/frontier4/kernels-all.json`) |
| recency order | sort by `lastRunTime` over all 608 | newest touch is `destbreso/x-ray-your-agent` 2026-09-28 23:03 UTC; **21 notebooks have lastRun ≥ 2026-09-25 and all 21 were freshly pulled and extracted** (§2) |
| creation order | `dateCreated` ordering validated against kernel `id_no` from the pulled metadata — `id_no` is monotone along the order (verified on 28 notebooks) | the order is **descending by creation**; V78 is `id_no 133108545` at position 220/608 ⇒ **220 notebooks were created after V78**, every engine-bearing one of them is in the checked set or is an older lineage |
| off-competition coverage | `kaggle kernels list --user` for 40 authors of kaggriculture notebooks + keyword searches (`kaggriculture`, `kaggriculture master engine`, `kaggriculture v79`, `harvest ledger`, `kaggriculture herd`, `kaggriculture route tape`, `kaggriculture v78`, `kaggriculture submit`) | 764 off-list kernels; the only kaggriculture ones are old (≤ 2026-09-24) analysis/lab pages — **no engine notebook hidden off-list** |
| leaderboard | the top of the leaderboard read from `data/leaderboard.json` (leader `M & M & P & Q` 3052.5, `DSM` 2989.6, `Vadim Vasilenko` 2956.7, `Boey` 2930.8, `Victor @ Tufa Labs` 2928.2, … 10,139 teams) | **limitation:** the leaderboard API exposes only `teamId`/`teamName`/`score` — no submission ids and no notebook refs, and team names are not usernames (`--user yuto083`, `--user akmr` → "Not found"). Name searches resolve to no kaggriculture notebook. A public notebook from a top team would normally be competition-tagged and is therefore already inside the 608 swept above. |

Notebooks actually pulled and dissected: the **28 newest by `lastRunTime`** (every notebook touched on or after
2026-09-23 14:54), plus the previously pulled corpus in `data/cand/` (93 notebooks). Payload extraction was
attempted on every one of them; the results are in §2 and §4.

**Publish dates:** Kaggle's public API does **not** expose a publication timestamp (`ApiKernelMetadata` carries
only `last_run_time`; the list response zeroes `id`/`current_version_number`). The tables below therefore give
**(a)** `lastRunTime` — the publication/refresh stamp the API *does* expose, and the timestamp t40 itself used —
and **(b)** `id_no`, the kernel creation id, which orders publication reliably. Both are stated per row.

---

## 2. Provenance of every checked notebook

`sha16` is the decoded engine source actually used for screening; `payload` is the **decoded route-payload
hash** computed with the Task-40 instrument (champion blob `54fe156ea7206e38`).

| notebook | lastRun UTC | id_no | source sha16 | route payload | self-declared version |
|---|---|---|---|---|---|
| `destbreso/x-ray-your-agent` | 2026-09-28 23:03 | 132616249 | — | no route payload (analysis) | "X-ray your agent" analysis |
| `ashok205/top10-replay-dataset-archive` | 2026-09-28 22:43 | 131478793 | — | no route payload (dataset) | daily top-10 replay archive |
| `georgymamarin/kaggriculture-what-2600-farms-do-differently` | 2026-09-28 22:13 | 129213318 | — | no route payload (analysis) | ladder analysis |
| `evgendvorkin/kaggriculture-version-31-26-09-bronze-going-up` | 2026-09-28 20:33 | 132685767 | `dc5433c7996f3f18` | **action-tape `5df1c84699004845`** | "Version 31, 26.09" |
| `tetsutani/demand-preserving-turn-sale-timing` | 2026-09-28 17:41 | 134878109 | `55be5d5f124c8daa` | **OURS `54fe156ea7206e38`** | `step1009_step1008_fortyfirst_final_fixedsell_closure` |
| `leoprovorov/god-s-mode-hacked-stores` | 2026-09-28 16:31 | 134330479 | `f9588c46…`/`177d78bd…` (bundle) | **OURS `54fe156ea7206e38`** (in `base_agent.py`) | "God's Mode: Hacked Stores 0.1.0" (base_agent 860 KB V39 lineage + shop overlay) |
| `leoprovorov/a-song-of-ice-and-fire-fixed-flexible` | 2026-09-28 14:09 | 133893082 | `12ad317ecac6c07f` | **OURS `54fe156ea7206e38`** | `AGENT_NAME = MarketShock-M1-WR1K` |
| `haodou092/kaggriculture-harvest-ledger` | 2026-09-28 12:01 | 131331249 | `8cffc452c3023082` | **OURS `54fe156ea7206e38`** | **"V85 — Harvest Ledger — Fail-Closed Proven Line"** |
| `flexonafft/kaggriculture-multi-route-farming-agent` | 2026-09-28 10:57 | 129367546 | `489f5d197527f107` | no route payload (C95 replay) | "Adaptive Farm Intelligence — Top-Meta Replay C95" |
| `guruprasaathas111/kaggriculture-master-engine-v53e01d74d8f` | 2026-09-28 02:34 | 134191544 | `708c7485fa964853` | **action-tape `5df1c84699004845`** | "Master Engine V5" |
| **`haideptry/the-2965-master-hybrid-engine`** | 2026-09-28 02:13 | 135178936 | **`63dde9e4f73eb6c4`** | **OURS `54fe156ea7206e38`** | **"Kaggriculture V79 SOTA"** (2965+, V79 Harvest Ledger) |
| `guruprasaathas111/kaggriculture-top-2-master-engine-v4` | 2026-09-27 19:04 | 134995812 | **`63dde9e4f73eb6c4`** | **OURS** | "Grandmaster Agent: 41-Route Multi-Expert System" (= V79 bytes) |
| **`leoprovorov/3141592…4197169399` (V78, our base)** | 2026-09-27 17:57 | 133108545 | `836cbfb633583890` | **OURS `54fe156ea7206e38`** | **"Kaggriculture V78 SOTA"** |
| `haideptry/the-shepherds-ledger-herd-safe-sovereign` | 2026-09-27 15:15 | 135478583 | `1eb0938d1a032e61` | **OURS** | "Kaggriculture SOTA" (shepherds ledger line) |
| `kunaldesale2408/kaggriculture-ttv1` | 2026-09-27 12:02 | 130539225 | **`63dde9e4f73eb6c4`** | **OURS** | no version claim (= V79 bytes) |
| `lynnsakurai/farmer-john-and-the-idle-seller` | 2026-09-27 09:29 | 135139195 | `03165654e70bd044` | **OURS `54fe156ea7206e38`** | Farmer John / idle-seller line (Source `ARCHIVE_PARTS`) |
| `leoprovorov/kaggricult-man-reverse-engineering` | 2026-09-26 15:58 | 133772029 | — | no route payload (analysis; ships `127ed3e6`) | reverse-engineering write-up |
| `kunaldesale2408/kaggriculture-2026-v1` | 2026-09-26 12:50 | 130408740 | `dc5433c7996f3f18` | **action-tape `5df1c84699004845`** | action-tape build |
| `lynnsakurai/farmer-john-and-the-wheat-seller` | 2026-09-26 06:49 | 135211310 | `a91efdd0fb1c96f7` | **OURS** | Farmer John wheat line (= MarketShock bytes) |
| `syedtahahassan/kaggriculture-hack` | 2026-09-25 11:05 | 134764477 | `a2047ebd8ca57202` | **action-tape `5df1c84699004845`** | "Kaggriculture V38 — Smarter Feed, Stronger Margins" |
| `guruprasaathas111/kaggriculture-master-engine-v3` | 2026-09-25 02:50 | 133017305 | `dc04c0862e4d70c6` | no route payload (ships `127ed3e6`) | "Master Engine V6" |
| `degnonguidi/kaggriculture-utils-v1` | 2026-09-24 18:16 | 129772526 | — | no route payload (ships `127ed3e6`) | utils |
| `nihilisticneuralnet/kaggriculture-population-robust-economy` | 2026-09-24 13:03 | 135290730 | `3ec06d07c1076dd8` | **OURS `54fe156ea7206e38`** | "Population-Robust Economy" (Source `MAIN_BLOB`) |
| `anhadmahajan06/kaggriculture-autonomous-ai-farming-agent` | 2026-09-24 10:42 | 134775301 | `2993cf9241b467bb` | **OURS** | "Autonomous AI Farming Grandmaster Agent (Version 8)" |
| `abhinav0370/cha22-agent` *(newest-created of all 608)* | 2026-09-24 09:30 | 135642255 | `127ed3e62988c047` (assembled) | **OURS** | "cha22 route-replay agent" = MarketShock-M1-WR1K |
| `hanifnoerrofiq/pioneers-of-kaggle-town-candidate-2` | 2026-09-24 05:33 | 135580378 | — | no decodable source | Pioneers of Kaggle Town |
| `djamilabenchikh/graph-reinforcement-learning` | 2026-09-23 17:01 | 132146755 | `f029fa0cb66a9eb5` | **OTHER `c51facaac9f0dd27`** | "V16-RC5 + GNN + Double DQN" |
| `yangkuangou/kaggriculture-agent-lab-copy-replay-compare` | 2026-09-23 14:54 | 135525463 | — | no route payload (tooling) | agent lab |

### 2.1 The engine families the frontier actually contains

| family | source size | sha16 of extracted main | where it appears |
|---|---|---|---|
| **V78** (our base, best measured) | 1,196,118 | `836cbfb633583890` | V78 notebook; is the parent of `pi_stack` |
| **V78 with `_CA_MARGIN = −15.0`** ("V79"/"V85" line) | 1,196,118 | `63dde9e4f73eb6c4` (identical in `the-2965`, `top-2-v4`, `ttv1`) | the-2965, top-2-master-engine-v4, ttv1 |
| V78(−15) + **inert fail-closed wrapper** | 1,197,325 | `8cffc452c3023082` | harvest-ledger "V85" |
| V78(−15) + **guard removal** (1 seed in 120 changes, by 2 coins) | 1,196,081 | `55be5d5f124c8daa` | demand-preserving-turn-sale-timing |
| V78(−15) with the 41 `step9xx` closures **collapsed to one fixed-point pass** (behaviourally identical, 47 KB smaller) | 1,148,715 | `03165654e70bd044` | farmer-john-and-the-idle-seller |
| shepherds-ledger engine (= a-song's `MarketShock-M1-WR1K` + trailing alias line) | 897,851 / 897,884 | `12ad317ecac6c07f` / `1eb0938d1a032e61` | a-song, shepherds |
| MarketShock-M1-WR1K (canonical) | 501,543 | `127ed3e62988c0474d386db6527ae8ca9de9bb1fe7004128557ddef67126c652` | cha22, master-engine-v3, utils-v1 |
| MarketShock variant ("Farmer John wheat") | 505,779 | `a91efdd0fb1c96f7` | wheat-seller |
| "God's Mode" base_agent (V39 lineage) + shop overlay | 860,103 + 358 | `177d78bd…` / `f9588c46…` | god-s-mode |
| V8 autonomous | 1,067,635 | `2993cf9241b467bb` | autonomous-ai-farming-agent |
| V39-lineage "population-robust" | 813,203 | `3ec06d07c1076dd8` | population-robust-economy |
| action-tape builds | 299,347 / 311,246 | `dc5433c…` / `708c7485…` | evgendvorkin v31, 2026-v1, kaggriculture-hack, master-engine-v5 |
| C95 replay | 75,098 | `489f5d197527f107` | multi-route-farming-agent |
| V16-RC5 + GNN | 18,946 | `f029fa0cb66a9eb5` | graph-reinforcement-learning |

---

## 3. Extraction — what t40's tooling could not see

t40's extraction path (`notebook_extract` / `notebook_to_main` / `notebook_b64_extract`) silently missed six
payload shapes that the frontier actually uses. They are handled by the new
**`scripts/t43_extract.py`**:

| shape | example | how it is decoded |
|---|---|---|
| `PAYLOAD_B85 = ( '…' '…' )` implicit concatenation | a-song, god's-mode | Python-string payload → base85 → lzma → custom container / tar |
| `ARCHIVE_B85 = """…"""` | demand-preserving | base85 → tar.gz |
| `FILES = {'main.py': '<base85>', …}` dict | harvest-ledger, top-2-v4, ttv1 | per-file base85 → source, verified against the notebook's own `EXPECTED` hashes |
| `X = ''.join(('…','…'))` and `X = []` + `X.append('…')` across cells | population-robust (`MAIN_BLOB`), farmer-john-idle-seller (`ARCHIVE_PARTS`) | string-part accumulation → base85 → zlib / tar.gz |
| custom binary container | god's-mode | `lzma(b85)` → `[file_count u16][name_size u16][name][payload_size u64][payload]×N`, all six `EXPECTED_SHA256` verified |
| `SOURCE_BYTES = b''.join((…))` | cha22 | byte-literal assembly, verified against `EXPECTED_MAIN_SHA256` |

Every extracted engine was compile-checked, smoke-gated (§5), and had its route payload decoded. Notebooks
with **no decodable engine source** are analysis/tooling/dataset pages (`x-ray-your-agent`,
`top10-replay-dataset-archive`, `kaggriculture-what-2600-farms-do-differently`,
`kaggriculture-agent-lab-copy-replay-compare`, `pioneers-of-kaggle-town-candidate-2`,
`kaggricult-man-reverse-engineering`, `kaggriculture-utils-v1`) or a multi-file bundle handled separately
(`god-s-mode`). None of them is a strength candidate: they are all **older than V78** (lastRun ≤ 2026-09-26),
none claims a newer engine, and the MarketShock base that `kaggricult-man` / `utils-v1` / `master-engine-v3`
only redistribute was screened directly as `marketshock_m1_wr1k`. Every other extracted engine — **15 builds,
10 behaviourally distinct engines** after de-duplicating the identical groups in §3.2 — was duelled (§6).

### 3.1 Correction: t40's provenance rows for four notebooks were stale

`scripts/t40_frontier.py` pulls a notebook **only if the local `.ipynb` is absent**. Four notebooks already had
stale local copies, so t40's provenance and duels for them measured 22–25 Sep bytes, not the content that was
live at scan time:

| notebook | local copy t40 used | t40 duelled source | today's fresh source |
|---|---|---|---|
| `haideptry/the-2965-master-hybrid-engine` | 2026-09-22 23:14 | `93831c18a43c4931` (1,040,667) | **`63dde9e4f73eb6c4` (1,196,118)** |
| `guruprasaathas111/kaggriculture-top-2-master-engine-v4` | 2026-09-22 23:15 | `a5362d138ed3933a` (1,016,747) | **`63dde9e4f73eb6c4`** |
| `tetsutani/demand-preserving-turn-sale-timing` | 2026-09-23 06:07 | `a16e0e9b40c48997` (1,026,965) | **`55be5d5f124c8daa` (1,196,081)** |
| `haodou092/kaggriculture-harvest-ledger` | 2026-09-25 06:47 | extraction failed ("no-blob") | **`8cffc452c3023082` (1,197,325)** |

The t40 **winner** is unaffected: the V78 notebook was absent locally and therefore pulled fresh, and
`pi_stack` is built from that fresh extraction (`836cbfb633583890`). But any *future* frontier scan must
re-pull unconditionally.

### 3.2 Behavioural identity checks (bug-signature discipline)

Two different settings producing byte-identical results is a bug signature — so each case was resolved
explicitly, per-seed, on both panels and both bases:

| pair | verdict |
|---|---|
| `the-2965` vs `harvest-ledger` | **all 4 cells identical** ⇒ the V85 "fail-closed wrapper" never fires (by design; documented as fail-closed and inert when no exception occurs) |
| `the-2965` vs `demand-preserving` | identical vs `pi_stack`; **1 seed of 120 differs** vs `pi_base` (seed 17021: −47 vs −45) ⇒ the removed empty-order guard does fire, once, for 2 coins — live but immaterial |
| `a-song` vs `shepherds-fresh` | **all 4 cells identical**; the two sources differ only by a trailing `kaggle_submission_agent = agent` alias ⇒ `MarketShock-M1-WR1K` **is** the shepherds-ledger engine |
| `marketshock` vs `wheat-seller` | **identical on both panels** ⇒ the wheat-seller notebook ships the canonical MarketShock base |
| `the-2965` vs `farmer-john-idle-seller` | **identical on both panels**; the sources differ because the idle-seller notebook collapses the 41 sequential `step965…step1008` closure wrappers into one `step1010_fixed_point` pass (`_CA_MARGIN` is `−15.0` in both) ⇒ **the entire 41-pass closure pile is behaviourally inert** on these towns |

---

## 4. Route-payload conclusion (7th independent confirmation)

Every decodable **route table** on the frontier is byte-identical to our champion blob
**`54fe156ea7206e38`** — including the newest engines (`the-2965`, `harvest-ledger`, `ttv1`, `top-2-v4`),
the shepherds/MarketShock family, `pi_stack`'s base, and the V78 notebook itself. The only distinct payloads
found anywhere in the scan are **action tapes**, not route data:

| payload | shape | where |
|---|---|---|
| `54fe156ea7206e38` | route table (41 routes / 3,982 actions) | all V78/shepherds/MarketShock engines |
| `5df1c84699004845` | `{base: 719, patches: 12}` step-indexed action tape | evgendvorkin v31, 2026-v1, kaggriculture-hack, master-engine-v5 |
| `c51facaac9f0dd27` | 720-element raw action list (`{'farmer': ['PASS'], …}`) | graph-reinforcement-learning |

**Same data everywhere; the edge is layers, not data.** Consistent with Task 40.

---

## 5. Smoke gate (before any duel)

720-step self-play, fresh seed 17000, both seats, exception probe on the agent callable, non-zero chassis
diagnostics printed. A layered/extracted notebook that raises inside its wrapper silently returns the raw tape
and looks valid — hence the explicit exception probe.

| candidate | statuses | rewards | agent exceptions | non-zero chassis counters |
|---|---|---|---|---|
| `the-2965-master-hybrid-engine` | DONE / DONE | 105,453 / 105,453 | 0 | none |
| `harvest-ledger` (V85) | DONE / DONE | 105,453 / 105,453 | 0 | none |
| `demand-preserving-turn-sale-timing` | DONE / DONE | 105,453 / 105,453 | 0 | none |
| `a-song-of-ice-and-fire` (`MarketShock`) | DONE / DONE | 107,893 / 107,893 | 0 | none |
| `multi-route-farming-agent` (C95) | DONE / DONE | 119,466 / 119,466 | 0 | none |
| `graph-reinforcement-learning` (V16) | DONE / DONE | 113,597 / 113,597 | 0 | none |
| `god-s-mode-hacked-stores` (bundle) | DONE / DONE | 111,365 / 112,090 | 0 | none |
| `marketshock_m1_wr1k` (canonical) | DONE / DONE | 107,935 / 107,935 | 0 | none |
| `kaggriculture-autonomous-ai-farming-agent` | DONE / DONE | 107,804 / 107,804 | 0 | none |
| `farmer-john-and-the-wheat-seller` | DONE / DONE | 107,935 / 107,935 | 0 | none |
| `kaggriculture-2026-v1` (action tape) | DONE / DONE | 111,094 / 111,094 | 0 | none |
| `kaggriculture-master-engine-v5` (action tape) | DONE / DONE | 110,556 / 110,556 | 0 | none |
| `kaggriculture-population-robust-economy` | DONE / DONE | 107,975 / 107,975 | 0 | none |
| `farmer-john-and-the-idle-seller` | DONE / DONE | 105,453 / 105,453 | 0 | none |
| `cha22-agent` (cell as extracted) | — | — | `NameError: WORKDIR` | extraction artifact; canonical base re-extracted from `SOURCE_BYTES` instead |

Note that self-play reward is **not** an instrument: C95 and V16 post the two *highest* self-play rewards
(119,466 / 113,597) and are the two worst duellists (−33k and −35k). Only paired duels decide.

---

## 6. Duel table — every candidate screened

### 6.1 vs the champion `pi_stack` (primary; bar = Δ > 0 and t ≥ 3 on **both** panels)

| candidate | p1 Δ | p1 t | p1 W–L | p2 Δ | p2 t | p2 W–L | cand exc | errors | verdict |
|---|---|---|---|---|---|---|---|---|---|
| `the-2965` (V79, `−15.0`) | −765 | −9.21 | 0–60 | −479 | −7.74 | 2–58 | 0 | 0 | no-go |
| `harvest-ledger` (V85, same bytes + wrapper) | −765 | −9.21 | 0–60 | −479 | −7.74 | 2–58 | 0 | 0 | no-go |
| `demand-preserving` (`−15.0` + guard removal) | −765 | −9.21 | 0–60 | −479 | −7.74 | 2–58 | 0 | 0 | no-go |
| `farmer-john-idle-seller` (`−15.0`, closures collapsed) | −765 | −9.21 | 0–60 | −479 | −7.74 | 2–58 | 0 | 0 | no-go |
| `a-song` / `MarketShock-M1-WR1K` | −1,034 | −5.28 | 4–56 | −981 | −6.08 | 6–54 | 0 | 0 | no-go |
| `shepherds-fresh` (same bytes) | −1,034 | −5.28 | 4–56 | −981 | −6.08 | 6–54 | 0 | 0 | no-go |
| `god-s-mode-hacked-stores` | −779 | −3.74 | 15–45 | −792 | −4.86 | 13–47 | 0 | 0 | no-go |
| `marketshock_m1_wr1k` (canonical) | −884 | −3.73 | 8–52 | −672 | −4.80 | 14–46 | 0 | 0 | no-go |
| `wheat-seller` (same bytes) | −884 | −3.73 | 8–52 | −672 | −4.80 | 14–46 | 0 | 0 | no-go |
| `autonomous-v8` | −942 | −4.61 | 10–50 | −712 | −3.93 | 17–43 | 0 | 0 | no-go |
| `2026-v1` (action tape) | −5,554 | −8.79 | 0–60 | −4,800 | −8.23 | 0–60 | 0 | 0 | no-go |
| `master-engine-v5` (action tape) | −5,142 | −8.04 | 0–60 | −4,286 | −7.42 | 2–58 | 0 | 0 | no-go |
| `population-robust` | −1,093 | −5.71 | 3–57 | −1,034 | −6.45 | 6–54 | 0 | 0 | no-go |
| `multi-route C95` | −33,299 | −19.19 | 0–60 | −35,492 | −19.79 | 0–60 | 0 | 0 | no-go |
| `graph+RL V16` | −36,462 | −13.65 | 0–60 | −33,373 | −18.78 | 0–60 | 0 | 0 | no-go |

All cells: `cand_exceptions = base_exceptions = errors = 0`; every status DONE.

### 6.2 Engine-vs-engine diagnostics vs the bare V78 base (`pi_base`)

This is the comparison that isolates *engine quality*: our layers are worth **+593** on `pi_base`
(120 games, REPORT-pi-v78 §4), so `pi_stack` ≈ `pi_base` + 593.

| candidate | p1 Δ | p1 t | p1 W–L | p2 Δ | p2 t | p2 W–L | stronger than V78? |
|---|---|---|---|---|---|---|---|
| `the-2965` / `harvest-ledger` / `idle-seller` (V79) | −61 | −3.23 | 10–32 | −60 | −1.86 | 24–26 | **no** |
| `demand-preserving` | −61 | −3.22 | 10–32 | −60 | −1.86 | 24–26 | **no** |
| `a-song` / `shepherds-fresh` | −1,309 | −6.81 | 6–54 | −1,037 | −6.25 | 4–56 | **no** |
| `god-s-mode-hacked-stores` | −1,013 | −5.58 | 11–49 | −946 | −5.93 | 9–51 | **no** |
| `marketshock_m1_wr1k` | −1,160 | −5.66 | 7–53 | −768 | −6.53 | 8–52 | **no** |
| `multi-route C95` | −33,499 | −19.13 | 0–60 | −35,787 | −19.88 | 0–60 | **no** |
| `graph+RL V16` | −36,796 | −13.78 | 0–60 | −33,670 | −18.79 | 0–60 | **no** |

**Nothing on the public frontier is even as strong as our own base engine**, let alone the stack.

### 6.3 Instrument control

| control | result |
|---|---|
| `pi_stack` copy vs `pi_stack` (byte-identical), seeds 17000–17009 | **Δ = +0.0, t = 0.00, errors = 0, exceptions = 0, wallets 99,663 / 99,663**, identical command counts on both sides |

A knobs-off / identical-build control must come out at exactly zero; it does.

---

## 7. Bar verdict and why no stacking was performed

No candidate met the bar (Δ > 0 **and** t ≥ 3 on both panels), so step 4 of the task (stack race +
WOOL/STRAWBERRY/MILK forward via `scripts/t40_stack.py` at `race_layout=1`/`hyp=clone`/`hook=outer`/items
MILK,WOOL,STRAWBERRY,MELON + `forward_drain=True`, `forward_drain_mult=24.0`, start 312) was **not
triggered**, and **no new stacked build and no submission** were produced.

That decision is not a close call, and it is corroborated independently: for the best candidate
(the-2965/V79, the only one within 1,000 coins of V78), the two measurements agree —

* direct: candidate-vs-`pi_stack` = **−765 / −479** (mean ≈ −622)
* decomposition: candidate ≈ `pi_base` − 60; `pi_stack` ≈ `pi_base` + 593 ⇒ predicted ≈ **−653**

The +31-coin gap between the two lines is noise plus any layer×margin interaction, and it is two orders of
magnitude smaller than the deficit. Adding our layers to the −15 engine cannot close a ~600-coin gap.

---

## 8. Explicit answer: is anything newer than V78?

| question | answer |
|---|---|
| Any notebook **created** after V78? | **Yes — 220 of the 608** (V78 is `id_no 133108545`, creation rank 220/608). Every engine-bearing one was extracted and screened; the rest are analysis/tooling/dataset pages. |
| Any notebook **published/refreshed** after V78? | **Yes — 12** have a `lastRunTime` later than V78's 2026-09-27 17:57 (`x-ray-your-agent`, `top10-replay-dataset-archive`, `what-2600-farms`, `evgendvorkin v31`, `tetsutani demand-preserving`, `god-s-mode`, `a-song`, `harvest-ledger`, `multi-route`, `master-engine-v5`, `the-2965`, `top-2-v4`). **All 12 were freshly pulled and extracted**; 3 are analysis/dataset pages and 9 are engines — all 9 screened (§6). |
| Any **newer engine version string**? | **Yes** — "V79 SOTA" (`the-2965`), "V85 Harvest Ledger" (`harvest-ledger`), "Master Engine V6/V5", "V8", "V16-RC5". |
| Any **newer or stronger engine**? | **No.** Every newer version string decodes to the **same V78 source with `_CA_MARGIN` −22.0 → −15.0** (plus an inert wrapper or a single-coins-worth guard change), or to an *older* engine lineage (shepherds/MarketShock/V8/C95/V16). None beats V78 alone; all lose to `pi_stack` by −479 to −36,462 coins/game. |
| Any **new route data**? | **No.** Every route table decodes to `54fe156ea7206e38`; the only distinct payloads are action tapes. |
| **Strongest public base today** | **V78** (`leoprovorov/3141592…4197169399`, source `836cbfb633583890`), unchanged since the t40 pull — so **`pi_stack` remains the strongest build ever measured in this project**. |

**Recommendation: hold.** Do not spend a submission slot on anything found in this scan. The lone live knob
the public frontier moved (carrot margin −22 → −15) is a local regression on 120 paired games; if it is ever
worth a ladder test, that is a human decision with a slot cost, and it is not supported by the only valid
instrument.

---

## 9. Artifacts

| file | content |
|---|---|
| `scripts/t43_extract.py` | all-payload-shape extractor (writefile / b64 / b85 / FILES-dict / `''.join` + `.append` string parts / custom container / `SOURCE_BYTES`), route-payload hashing, compile check → `data/frontier4/extract.json` |
| `scripts/t43_provenance.py` | per-notebook provenance + version-string inventory → `data/frontier4/provenance.json` |
| `scripts/t43_smoke.py` | 720-step aliveness gate with exception probe → `log/t43-smoke2.log` |
| `scripts/t43_screen.py` | smoke-gated paired screening vs `pi_stack` (and vs `pi_base`), panels 17000–17029 / 17100–17129 → `data/frontier4/screen.json`, `data/frontier4/duels/*.json`, `log/t43-screen{,2,3,4}.log` |
| `data/frontier4/kernels-all.json` | full 608-notebook listing (3 sort orders) |
| `data/frontier4/kernels-offlist.json` | 764 off-competition kernels from 40 author lists + keyword searches |
| `data/frontier4/nb/` | 28 freshly pulled notebooks + `kernel-metadata.json` (id_no) |
| `data/frontier4/main/` | extracted mains for screening; `data/frontier4/gods_mode/` holds the 6-file God's Mode bundle + `gods_mode_driver.py` |
| `data/frontier4/pi_stack_copy.py` | self-control copy of the champion |
| `data/candidate/pi_stack/main.py` | **champion (unchanged)** — sha256 `65962e928b0712946e1bacb929b4fb919a7231f34e1bc99c7e350d4e2755f317` |
| rebuild of the champion | `.venv/bin/python scripts/t40_stack.py` |
