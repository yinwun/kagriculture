# Task 42 — where the `pi_stack` ladder line loses, and what could reach 2,400

**Date:** 2026-09-29 · **Subject:** submission ref **56642424** (`data/candidate/pi_stack/main.py`,
sha256 `65962e928b0712946e1bacb929b4fb919a7231f34e1bc99c7e350d4e2755f317`), the public
"Kaggriculture V78 Master Engine" base plus our three outermost market layers.
**Nothing was submitted.** Ladder state at measurement: **nickyl 2,141.4, rank 776 / 10,139
(top 7.7 %)**; top-5 % cutoff 2,254.3, top-10 % 2,043.4, top-1 % 2,582.2 — so **2,400 is
~rank 260 and +258.6 points away**.

**Instruments built for this task** (all new, all in-repo):

| file | what it does |
|---|---|
| `scripts/pi_fetch_replays.py` | downloads every public replay of a ref |
| `scripts/pi_attribute.py` | bank-exact re-simulation of a replay with three engine hooks → per-item units/revenue/spend by seat, per-item production, per-item discards, per-day liquid net worth; **91/91 games reproduced the recorded rewards to the dollar** and the channel accounting closes to **residual 0.0000** |
| `scripts/pi_analyse.py` | the channel / volume-price / production tables below |
| `scripts/pi_opp_strength.py` | rating-free opponent strength: each opponent *submission*'s own episode list → its own W–L record |
| `scripts/t42_sweep.py` | builds, smoke-gates and duels the market-layer candidates |

Artifacts: `data/pi-episodes-56642424.json`, `data/replays-56642424/` (91 replays),
`data/pi-attr-56642424.json`, `data/pi-analysis-56642424.json`,
`data/pi-opp-strength-56642424.json`, `data/pi-episode-table.md`, `log/pi-analysis.log`.

---

## 0. Headline

1. **The ladder games are coin flips at the 1 % level.** Margin distribution over all 91
   games: **5 games decided by ≤100 coins, 12 by ≤250, 29 by ≤500, 54 by ≤1,000** — against a
   mean wallet of ~100,000. Median margin **+587**, mean **+3,665** (the mean is carried by a
   handful of blowouts against weak lines).
2. **In the 14 losses the two biggest coin channels are EGG (−1,368/game) and WHEAT
   (−1,367/game); both are production/feed channels inside the base, not the market layer.**
   The market layer's own net contribution in those games is *positive*: WOOL +567,
   MILK +325, MELON +138, FERTILIZER +12, plus a negative STRAWBERRY −116.
3. **8 of 14 losses are by < 1,100 coins.** Their margins sum to −3,326; a *uniform*
   +1,039 coins/game converts 8 of them, +2,553 converts 10.
4. **The losses are mostly — not entirely — against genuinely stronger opponents.** The 14
   loss opponents win **0.679** of their own ladder games on average (mean reward 100,204);
   the 77 win opponents win **0.509** (mean reward 97,361). Correlation between the
   opponent's own win rate and our margin: **−0.390** over 91 games. **4 of the 14 losses are
   to teams at or below 0.533** (linhaiy 0.472, Munshi-PremChand 0.505, Mathurin Ache 0.510,
   ReD_MooN_rise 0.533) whose own mean reward is below ours.
5. **Reaching 2,400 at the observed opponent pool requires a ~96 % win rate** (from 84.6 %),
   i.e. **converting ~10–11 of the 14 losses**. On the margin distribution that means a
   **uniform +2,860 coins/game** (converts 10 → 87/91 → Elo ≈ 2,380) or **+3,306** (converts 11
   → 88/91 → ≈ 2,430) — **+2.9 … +3.3 % of wallet**. The ruler: a one-parameter Elo fit to our
   own 91 games (`R = pool + 400·log10(w/(1−w))`) gives `pool = 1,845` at our observed
   (w = 0.846, R = 2,141.4) — and the mean displayed score of our 91 opponents is 1,860, so
   the fit is self-consistent. Solving for R = 2,400 gives w = 0.961. For scale: **our entire
   market-layer stack on this base is worth +593 coins/game (+0.6 % wallet, t = +10.86)**. The
   required change is **~4.8× everything we have built**.
6. The one genuinely unexploited market-side channel found is **end-of-day shed destruction**:
   we destroy **8.37 units/game** (12.71 in losses) versus the opponent's 7.52 (7.93), worth
   about **+518 coins/game at market prices** if all of it were sold instead. A candidate that
   attacks exactly this was built and duelled (§4) — **and it measures +0.73 coins per unit
   released**, i.e. the channel is a mirage: at the margin this market pays ~nothing for an
   extra unit offered.
7. **No candidate cleared the two-panel bar. Nothing was promoted and nothing was submitted.**
   The best cell (`t42_guard3`) is +2.5 (t = +1.09) on panel 16400–16429 and +5.8 (t = +1.81)
   on 16500–16529 — worth +0.3 … +0.9 rating points on the project's own ruler.

---

## 1. Episode table (91 public episodes, joined to `data/leaderboard.json` and to each
opponent submission's own episode list)

Fields: our seat, both rewards, margin, opponent team, opponent leaderboard score (the
*currently tracked* submission — see the caveat in §3), the opponent submission's own record
from its own episode list, and the outcome class used throughout this report
(`close win` = margin < 2,000).

| # | episode | seat | our reward | opp reward | margin | opp team | opp LB score | opp own W-L | opp own WR | class |
|---|---|---|---|---|---|---|---|---|---|---|
| 1 | 114843483 | 0 | 92,685 | 104,891 | -12,206 | Blu3s | 2332.6 | 71-10 | 0.877 | **LOSS** |
| 2 | 114736078 | 0 | 101,010 | 109,854 | -8,844 | Kaileh57 | 995.6 | 63-33 | 0.656 | **LOSS** |
| 3 | 114798430 | 1 | 70,156 | 74,257 | -4,101 | Munshi-PremChand | 1915.5 | 159-156 | 0.505 | **LOSS** |
| 4 | 114808081 | 0 | 99,587 | 102,892 | -3,305 | 涵哥 | 2413.3 | 65-29 | 0.691 | **LOSS** |
| 5 | 114816105 | 1 | 80,441 | 83,301 | -2,860 | Eesh saxena | 2448.7 | 66-4 | 0.943 | **LOSS** |
| 6 | 114767278 | 0 | 112,499 | 115,051 | -2,552 | ReD_MooN_rise | 1870.7 | 57-50 | 0.533 | **LOSS** |
| 7 | 114740561 | 0 | 87,342 | 88,380 | -1,038 | linhaiy | 1688.9 | 100-112 | 0.472 | **LOSS** |
| 8 | 114742038 | 1 | 108,766 | 109,478 | -712 | lucataco | 1634.8 | 71-39 | 0.645 | **LOSS** |
| 9 | 114789468 | 0 | 86,278 | 86,877 | -599 | Bohann Wang | 2576.2 | 79-14 | 0.849 | **LOSS** |
| 10 | 114796806 | 0 | 122,304 | 122,765 | -461 | Ryutaro Tsujii | 2110.5 | 71-22 | 0.763 | **LOSS** |
| 11 | 114764713 | 1 | 81,570 | 81,797 | -227 | Mathurin Ache | 2259.7 | 75-72 | 0.510 | **LOSS** |
| 12 | 114761205 | 0 | 105,091 | 105,251 | -160 | iheng88 | 1947.0 | 69-30 | 0.697 | **LOSS** |
| 13 | 114811274 | 1 | 76,776 | 76,883 | -107 | z7777 | 2231.7 | 60-28 | 0.682 | **LOSS** |
| 14 | 114799831 | 1 | 106,249 | 106,271 | -22 | z7777 | 2231.7 | 60-28 | 0.682 | **LOSS** |
| 15 | 114807393 | 0 | 75,495 | 75,484 | +11 | Timothee Henry | 2025.0 | 66-30 | 0.688 | close win |
| 16 | 114869894 | 1 | 73,742 | 73,713 | +29 | 일필휘지 | 2329.1 | 76-31 | 0.710 | close win |
| 17 | 114777683 | 0 | 72,757 | 72,709 | +48 | ゴロ・イ | 2299.4 | 75-39 | 0.658 | close win |
| 18 | 114813150 | 1 | 77,711 | 77,639 | +72 | anngle | 2209.9 | 63-74 | 0.460 | close win |
| 19 | 114906202 | 0 | 138,875 | 138,673 | +202 | mocatti | 2218.7 | 133-41 | 0.764 | close win |
| 20 | 114852737 | 1 | 130,688 | 130,462 | +226 | Sutee | 2078.6 | 120-86 | 0.583 | close win |
| 21 | 114811768 | 1 | 119,013 | 118,769 | +244 | yuyinghuang | 2048.9 | 78-92 | 0.459 | close win |
| 22 | 114759937 | 0 | 81,986 | 81,741 | +245 | 4418 | 1893.2 | 87-90 | 0.492 | close win |
| 23 | 114884590 | 1 | 112,108 | 111,817 | +291 | 王子铖 | 2162.9 | 93-119 | 0.439 | close win |
| 24 | 114786571 | 1 | 79,265 | 78,938 | +327 | Justin Gao | 2025.9 | 76-44 | 0.633 | close win |
| 25 | 114877506 | 0 | 90,277 | 89,934 | +343 | Dr_F | 2003.3 | 63-65 | 0.492 | close win |
| 26 | 114757114 | 0 | 162,656 | 162,298 | +358 | yarneo | 2208.1 | 77-89 | 0.464 | close win |
| 27 | 114780729 | 0 | 91,498 | 91,134 | +364 | Sarthak Sharma  | 1947.7 | 54-67 | 0.446 | close win |
| 28 | 114912896 | 0 | 116,162 | 115,792 | +370 | HyperARC | 2167.8 | 70-58 | 0.547 | close win |
| 29 | 114801281 | 0 | 113,463 | 113,087 | +376 | FLA | 1935.8 | 54-56 | 0.491 | close win |
| 30 | 114755493 | 0 | 77,444 | 77,042 | +402 | John Doe | 1718.8 | 205-241 | 0.460 | close win |
| 31 | 114782094 | 0 | 130,819 | 130,416 | +403 | Iskander Yusupov | 1858.8 | 154-249 | 0.382 | close win |
| 32 | 114748046 | 0 | 142,443 | 142,034 | +409 | eliasruntime | 1617.3 | 132-223 | 0.372 | close win |
| 33 | 114787969 | 1 | 67,596 | 67,181 | +415 | Shoko | 1998.4 | 111-71 | 0.610 | close win |
| 34 | 114792303 | 0 | 80,688 | 80,239 | +449 | auouer | 2020.7 | 55-69 | 0.444 | close win |
| 35 | 114790993 | 1 | 74,682 | 74,219 | +463 | Forrest | 1909.9 | 214-241 | 0.470 | close win |
| 36 | 114835113 | 1 | 135,558 | 135,066 | +492 | キムチ納豆 | 2054.1 | 59-34 | 0.634 | close win |
| 37 | 114861545 | 1 | 60,954 | 60,461 | +493 | Happy Farm | 2116.8 | 86-14 | 0.860 | close win |
| 38 | 114859634 | 0 | 83,001 | 82,501 | +500 | artem3605 | 2050.9 | 49-38 | 0.563 | close win |
| 39 | 114775190 | 0 | 115,070 | 114,567 | +503 | kevin zhou | 1941.6 | 226-314 | 0.419 | close win |
| 40 | 114770310 | 0 | 101,863 | 101,359 | +504 | Suvrat Rai | 1759.6 | 105-224 | 0.319 | close win |
| 41 | 114870418 | 1 | 70,420 | 69,915 | +505 | Economist | 1906.7 | 32-26 | 0.552 | close win |
| 42 | 114745069 | 1 | 140,685 | 140,179 | +506 | neuro168 | 1634.8 | 256-436 | 0.370 | close win |
| 43 | 114802842 | 1 | 74,739 | 74,218 | +521 | Максим Бортник | 2048.7 | 81-82 | 0.497 | close win |
| 44 | 114746575 | 0 | 81,238 | 80,697 | +541 | darkphase11 | 1586.4 | 65-70 | 0.481 | close win |
| 45 | 114892255 | 0 | 119,789 | 119,224 | +565 | Pand | 2159.4 | 80-29 | 0.734 | close win |
| 46 | 114783606 | 0 | 150,905 | 150,318 | +587 | umair zia | 1829.5 | 101-65 | 0.608 | close win |
| 47 | 114795249 | 1 | 129,410 | 128,818 | +592 | Yuxiao Wang | 2020.9 | 75-44 | 0.630 | close win |
| 48 | 114793905 | 0 | 112,054 | 111,439 | +615 | Aniket Sharma | 2238.2 | 97-61 | 0.614 | close win |
| 49 | 114758464 | 0 | 77,889 | 77,262 | +627 | Manasa.ai | 1804.2 | 194-256 | 0.431 | close win |
| 50 | 114801313 | 0 | 90,930 | 90,272 | +658 | kerlgd | 1954.6 | 112-176 | 0.389 | close win |
| 51 | 114762927 | 0 | 128,893 | 128,233 | +660 | shiiin9 | 2081.5 | 63-30 | 0.677 | close win |
| 52 | 114830808 | 1 | 143,985 | 143,303 | +682 | Saulo Quiñones Góngora | 2177.8 | 55-29 | 0.655 | close win |
| 53 | 114766040 | 1 | 75,383 | 74,681 | +702 | Yi Wang | 1854.5 | 67-40 | 0.626 | close win |
| 54 | 114761673 | 0 | 108,129 | 107,425 | +704 | elegantangel (628700) | 1772.0 | 122-197 | 0.382 | close win |
| 55 | 114816117 | 0 | 123,437 | 122,711 | +726 | T.Uehira | 2069.3 | 58-36 | 0.617 | close win |
| 56 | 114898675 | 0 | 107,017 | 106,245 | +772 | PincheCabrón | 2132.8 | 66-91 | 0.420 | close win |
| 57 | 114780202 | 1 | 90,072 | 89,294 | +778 | 猫猫开大运 | 2200.8 | 61-34 | 0.642 | close win |
| 58 | 114768860 | 1 | 108,481 | 107,692 | +789 |  Master Bob111 | 1807.8 | 85-152 | 0.359 | close win |
| 59 | 114884656 | 0 | 104,711 | 103,867 | +844 | jiatu.l | 2180.7 | 127-63 | 0.668 | close win |
| 60 | 114779261 | 0 | 91,294 | 90,404 | +890 | github/shepsci/kaggle-skill | 1895.5 | 92-40 | 0.697 | close win |
| 61 | 114785172 | 0 | 121,458 | 120,472 | +986 | mayukistarry | 2156.4 | 134-233 | 0.365 | close win |
| 62 | 114860636 | 0 | 80,849 | 79,826 | +1,023 | ShadowT_T | 2065.9 | 31-33 | 0.484 | close win |
| 63 | 114751041 | 1 | 78,553 | 77,522 | +1,031 | Ndabenhle Ngema | 1694.7 | 166-80 | 0.675 | close win |
| 64 | 114820727 | 1 | 130,687 | 129,655 | +1,032 | p pxl16 | 2040.6 | 52-77 | 0.403 | close win |
| 65 | 114737543 | 0 | 72,176 | 71,134 | +1,042 | G*Sim | nan | 131-172 | 0.432 | close win |
| 66 | 114805796 | 0 | 76,699 | 75,626 | +1,073 | ykuroka | 2011.9 | 52-64 | 0.448 | close win |
| 67 | 114776070 | 0 | 131,071 | 129,972 | +1,099 | ReD_MooN_rise | 1870.7 | 57-50 | 0.533 | close win |
| 68 | 114773577 | 0 | 128,966 | 127,789 | +1,177 | Enes Altunbaş | 1780.1 | 182-195 | 0.483 | close win |
| 69 | 114743911 | 0 | 111,791 | 110,490 | +1,301 | Yasuhiro Manai | 1671.5 | 74-42 | 0.638 | close win |
| 70 | 114731723 | 1 | 88,398 | 87,053 | +1,345 | Abdoulaye DIAW | 1460.4 | 373-565 | 0.398 | close win |
| 71 | 114754022 | 0 | 129,904 | 128,526 | +1,378 | Jinhan Gao | 1733.7 | 97-142 | 0.406 | close win |
| 72 | 114749342 | 1 | 107,349 | 105,770 | +1,579 | Shunsuke Hayashi | 1686.1 | 79-14 | 0.849 | close win |
| 73 | 114752506 | 0 | 92,094 | 90,383 | +1,711 | pumpkin | 1701.5 | 183-232 | 0.441 | close win |
| 74 | 114792438 | 1 | 90,962 | 89,212 | +1,750 | Dhruvik Chauhan | 2042.4 | 196-302 | 0.394 | close win |
| 75 | 114771493 | 0 | 102,325 | 100,539 | +1,786 | Hire me! 🤗 [Viktor Cikojevic] | 1849.9 | 393-515 | 0.433 | close win |
| 76 | 114808687 | 0 | 140,764 | 138,966 | +1,798 | Alperen Aydın | 2075.8 | 110-101 | 0.521 | close win |
| 77 | 114814594 | 0 | 84,532 | 82,551 | +1,981 | ZEE | 1957.3 | 115-97 | 0.542 | close win |
| 78 | 114733172 | 1 | 85,180 | 81,001 | +4,179 | jingyang tu | 1227.1 | 28-41 | 0.406 | big win |
| 79 | 114810271 | 1 | 91,682 | 87,328 | +4,354 | e3k | 2065.0 | 169-271 | 0.384 | big win |
| 80 | 114739059 | 1 | 100,680 | 95,374 | +5,306 | KharinTymofii | 1543.7 | 37-44 | 0.457 | big win |
| 81 | 114836316 | 1 | 135,890 | 123,237 | +12,653 | minghao mei | 2133.1 | 55-48 | 0.534 | big win |
| 82 | 114734619 | 1 | 88,593 | 75,218 | +13,375 | tcipin-egor | 1441.9 | 258-460 | 0.359 | big win |
| 83 | 114728824 | 0 | 102,157 | 88,759 | +13,398 | dongdong zhang | 1091.6 | 346-604 | 0.364 | big win |
| 84 | 114804333 | 0 | 133,955 | 120,033 | +13,922 | pangzi233 | 2181.7 | 79-21 | 0.790 | big win |
| 85 | 114727377 | 1 | 91,216 | 69,211 | +22,005 | anton leyn | 1057.7 | 160-295 | 0.352 | big win |
| 86 | 114730285 | 1 | 69,328 | 45,358 | +23,970 | Controlvector | 967.1 | 360-586 | 0.381 | big win |
| 87 | 114725949 | 0 | 74,606 | 43,565 | +31,041 | Miles Oberting | 851.6 | 172-320 | 0.350 | big win |
| 88 | 114724511 | 0 | 149,416 | 114,396 | +35,020 | Saud Saudesen | 714.9 | 255-465 | 0.354 | big win |
| 89 | 114721591 | 0 | 109,852 | 69,747 | +40,105 | 关注塔菲喵 | 738.6 | 78-118 | 0.398 | big win |
| 90 | 114720160 | 0 | 105,778 | 55,213 | +50,565 | Zerabyte_X | 658.6 | 264-604 | 0.304 | big win |
| 91 | 114723077 | 0 | 113,310 | 57,373 | +55,937 | Fizie Fulumaka | 634.0 | 75-116 | 0.393 | big win |

**Class sizes:** 14 losses, 63 close wins (<2,000), 14 big wins (≥2,000).
Our mean reward **102,047**, opponent mean **98,382** (+3.7 %); mean margin **+3,665**, median
**+587**.

---

## 2. Loss attribution (14 losses, mean margin −2,657)

Method: each replay is re-simulated through the official engine with `_commit_unit`,
`_do_hire`, `_do_buy_land`, `_drop_inventories_to_shed` and `_end_of_day` wrapped, and each
agent call wrapped with a `_apply_unit_action` shadow evaluation (the `scripts/wheat_flow.py`
instrument). This yields **exact** per-seat per-item units, realised price, revenue, purchase
spend and production; money closes exactly: `3000 + sells − buys − hire − land = recorded`
with **residual 0.0000** in every window.

### 2.1 The five requested channels, mean coins per game

| item | units me / opp | price me / opp | Δ revenue | Δ purchase spend | **net** | volume effect | price effect |
|---|---|---|---|---|---|---|---|
| **EGG** | 64.9 / 93.6 | 26.49 / 33.53 | −1,368 | 0 | **−1,368** | −683 | −686 |
| **WHEAT** (incl. seed) | 897.4 / 895.6 | 39.14 / 39.24 | +412 | **+1,779** | **−1,367** | +507 | −95 |
| TOMATO | 11.4 / 15.1 | 30.24 / 36.64 | −330 | −29 | −302 | −168 | −162 |
| CARROT | 153.6 / 155.7 | 47.63 / 48.50 | −180 | +21 | −201 | −19 | −160 |
| STRAWBERRY | 245.9 / 237.6 | 101.65 / 105.01 | +26 | +143 | −116 | +607 | −580 |
| MELON | 72.0 / 73.2 | 200.02 / 195.37 | +121 | −17 | +138 | −237 | +357 |
| MILK | 176.0 / 171.6 | 90.51 / 90.26 | +325 | 0 | **+325** | +295 | +30 |
| WOOL | 209.5 / 200.9 | 117.57 / 121.70 | +567 | 0 | **+567** | +1,791 | −1,223 |
| FERTILIZER | 336.9 / 326.3 | 43.18 / 45.49 | −217 | −229 | +12 | +473 | −690 |
| GOOSE / COW / SHEEP (bought) | — | — | 0 | −43 | −43 | — | — |
| hire + land | — | — | — | — | −388 | — | — |
| **total** | | | **−643** | **+1,626** | **−2,657** | **+2,566** | **−3,209** |

Reading the channels as asked:

* **(a) units sold** — we sell *more* than the opponent on every premium item in the losses
  (wool +8.6, strawberry +8.2, milk +4.4, fertilizer +10.6, wheat +1.7) and *less* on egg
  (−28.7), tomato (−3.7), carrot (−2.1), melon (−1.2).
* **(b) realised price** — we are *behind* on wool (−4.12), strawberry (−3.35), fertilizer
  (−2.31), egg (−7.04) and *ahead* on melon (+4.65), milk (+0.24). Total price effect
  **−3,209/game**.
* **(c) money spent buying inputs** — we out-spend the opponent by **+1,626/game**:
  **wheat +1,779** (product + seed), plus small carrot/berry/fertilizer amounts; animals −43.
* **(d) animal/crop output** — EGG **−28.8 units** (65.3 vs 94.1) with −0.9 geese placed,
  WHEAT harvest −37.1, TOMATO −3.8, CARROT −1.1, MELON −1.2, MILK +4.0, STRAWBERRY +8.9,
  WOOL +9.4. **The egg gap alone is −1,368 coins.**
* **(e) idle / unused actions** — PASS share 7.9 % (me) vs 7.1 % (opp); we take **+57 PASS
  and +54 fewer MOVE** actions per loss game, i.e. ~2 % of ~2,880 worker actions. Worker-verb
  totals are otherwise equal (HARVEST +2, WATER +3, FEED −3, FERTILIZE −18, PLACE +2).
* **Waste:** we destroy 12.71 units/game at the end-of-day shed drop vs the opponent's 7.93
  (+4.8 units). The discarded mix is **FERTILIZER 4.14, WHEAT 3.43, CARROT 1.64, WOOL 1.57,
  STRAWBERRY 1.50, EGG 0.43**. There is **no end-of-game stock** (mean end-of-day-29
  `worth − money` = 10 coins for us, 12 for the opponent; mean end shed ≈ 0 for both), so
  the leak is the *nightly* drop, not the final liquidation.

### 2.2 Per-game channel table (the same accounting, one row per loss)

Sign convention: positive = in our favour. `resid` is the closure residual and is **0** in
every row.

| episode | margin | wheat | egg | straw | wool | milk | tomato | carrot | fert | melon | animals | hire+land | resid |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| 114843483 | −12,206 | +13,075 | −8,307 | −2,461 | −11,378 | +1,273 | −4,308 | +180 | −3,552 | +1,078 | +2,100 | +94 | 0 |
| 114736078 | −8,844 | −15,266 | −10,899 | +1,961 | +26,136 | +2,717 | 0 | −4,420 | −1,749 | +1,546 | −1,500 | −7,370 | 0 |
| 114798430 | −4,101 | −22 | 0 | +45 | −5,594 | +205 | 0 | +7 | +1,258 | 0 | 0 | 0 | 0 |
| 114808081 | −3,305 | −3,767 | +4 | −199 | +43 | −42 | 0 | +393 | +321 | −346 | 0 | +288 | 0 |
| 114816105 | −2,860 | −3,793 | 0 | +292 | −630 | −192 | 0 | −189 | +1,244 | −346 | 0 | +754 | 0 |
| 114767278 | −2,552 | −2,839 | −99 | +2 | −25 | +435 | 0 | −39 | +13 | 0 | 0 | 0 | 0 |
| 114740561 | −1,038 | −2,230 | 0 | +29 | −1,252 | −43 | 0 | +2,386 | +72 | 0 | 0 | 0 | 0 |
| 114742038 | −712 | +10 | −13 | −280 | +304 | −921 | +83 | 0 | +105 | 0 | 0 | 0 | 0 |
| 114789468 | −599 | −3,079 | +141 | +110 | +23 | +5 | 0 | −1,335 | +2,583 | 0 | 0 | +953 | 0 |
| 114796806 | −461 | −60 | +24 | −1,094 | +8 | +503 | 0 | +22 | +136 | 0 | 0 | 0 | 0 |
| 114764713 | −227 | −522 | 0 | −32 | +52 | +340 | 0 | +370 | −291 | 0 | 0 | −144 | 0 |
| 114761205 | −160 | −20 | 0 | +49 | +237 | +102 | 0 | −551 | +23 | 0 | 0 | 0 | 0 |
| 114811274 | −107 | −491 | −5 | 0 | −29 | +151 | 0 | +251 | +16 | 0 | 0 | 0 | 0 |
| 114799831 | −22 | −130 | −1 | −51 | +48 | +16 | 0 | +109 | −13 | 0 | 0 | 0 | 0 |

**The single most important thing this table says:** individual games are dominated by wild
single-item swings (114843483: wool −11,378 *and* wheat +13,075; 114736078: wheat −15,266,
egg −10,899, wool **+26,136**). Only the mean is interpretable, and the mean says the two
leading deficits are **egg output** and **net wheat/feed cost**, i.e. base economy, not our
market layer.

### 2.3 Where the deficit opens in time (mean liquid net worth, me − opp)

| day | 9 | 10 | 11 | **12** | **13** | 15 | 19 | 24 | 29 |
|---|---|---|---|---|---|---|---|---|---|
| **losses** | +292 | +942 | +128 | **−1,135** | **−1,742** | −2,383 | −2,267 | −2,352 | −2,658 |
| close wins | +21 | +5 | +4 | +96 | +92 | +83 | +190 | +382 | +706 |
| big wins | +273 | +6,506 | +5,697 | +5,922 | +6,229 | +8,999 | +13,349 | +16,206 | +23,201 |

The loss class crosses zero between **day 11 and day 12** and then stays ~2,000–2,900 behind
for the rest of the season; before day 11 losses and close wins are indistinguishable. This
reproduces the Task-26/30 finding on a completely different base (V78 + our layers) and a
completely different line: **the deficit opens in the second half, at ~2 % of the final
wallet, and never recovers.**

### 2.4 What our own build did differently in the loss games (not the opponent's doing)

Our own mean reward is **95,054 in losses vs 103,318 in wins**; the opponents' is 100,204 vs
97,361. So the loss games are towns where **our** build under-performs its own average by
~7,000 while the opponent is ~1,800 above theirs. Concretely, in the loss class our own
production is *lower than in our close wins* on the items that matter: EGG 65.3 vs 76.8,
MILK 176.0 vs 208.1, WHEAT 526.3 vs 549.5, CARROT 155.3 vs 140.2. The town draw (which
drives the base's herd/crop branch) moves our own output by more than the whole margin.

---

## 3. Are the losses against stronger opponents?

Two independent strength measures, both computed from data, not from reputation:

| | 14 losses | 63 close wins | 14 big wins |
|---|---|---|---|
| opponent LB score (mean / median) | **2,047 / 2,171** | 1,964 / 2,008 | 1,236 / 1,075 |
| opponent submission's **own** W–L record | **0.679** win rate | — | — |
| opponent's own mean reward | 100,204 (all 91: 100,493) | — | — |
| opponent's own mean *opponent* reward | 95,970 | — | — |
| opponent's own games | 121 | — | — |
| our own mean reward | 95,054 | — | — |

* **corr(opponent's own win rate, our margin) = −0.390** over 91 games: the stronger the
  opponent's own record, the worse our margin. Our build is *not* being beaten at random.
* The 14 loss opponents win **67.9 %** of their own games; the 77 win opponents win
  **50.9 %** — no overlap in the means, and the *pool* they sit in is identical
  (their opponents average 95,970 vs 96,160 coins), so the discriminator is genuine skill,
  not matchmaking.
* **But 4 of the 14 losses are to average-or-weaker teams**: linhaiy (own WR 0.472, own mean
  reward 97,596, margin −1,038), Munshi-PremChand (0.505, 98,456, −4,101), Mathurin Ache
  (0.510, 95,483, −227), ReD_MooN_rise (0.533, 99,308, −2,552). **That is where the cheap
  points are** — but two of those four are still large margins (−4,101, −2,552), so they are
  not unlucky coin flips either; they are towns where the opponent's build found more than
  ours.
* Caveat that matters: the opponent's **leaderboard score** is the score of the team's
  *currently tracked* submission, which is frequently a **newer** submission than the one we
  faced, and therefore immature. Kaileh57 beat us 109,854–101,010 while displaying **995.6** —
  their tracked submission was created at 20:01 the same evening, after our game at ~14:00.
  Their faced submission's own record is 63–33 (0.656). **Do not read the LB column as the
  strength of the submission we played; read the own-record column.**

**Answer:** 10 of 14 losses are to teams that win ~70–94 % of their own games — we are
*mostly* losing to genuinely better builds. 4 are to teams no better than the field, and
those 4 games are worth ~+4 rating points each; converting all four would move us from 2,141
to roughly **2,200**, not 2,400.

---

## 4. Ranked candidate changes (market layer only)

Constraint applied: a candidate may only touch `action["market"]` (which SELL lots we offer,
their quantities and their slot order). No farm-side action, no production quantity.

The scale to beat: **+2,860 coins/game uniformly** (or an equivalent targeted effect in ~10 of
the 14 loss games) to reach 2,400 at the observed pool. For reference the measured values of
the layers already in the build are: race/slot search **+152 (t = +8.99, 120 games)**,
forward layer **+441** (race+forward = +593, t = +10.86, 120 games), `forward_drain_mult`
already at its optimum 24 (48 is −3.5/−4.3 below it).

| # | candidate | expected value (coins/game) | evidence | status |
|---|---|---|---|---|
| 1 | **End-of-day overflow guard** — on the last turn(s) of each day, when the projected shed + carried stock exceeds the 100-unit cap, release exactly the projected overflow (ignoring the drain cap), most expensive item first, at any price ≥ 1 | **measured +2.5 / +5.8** (t = +1.09 / +1.81); the *apparent* budget was +518 | we destroy **8.37 units/game** (12.71 in losses) vs the opponent's 7.52 (7.93): FERTILIZER 3.14, WHEAT 2.00, WOOL 1.20, STRAWBERRY 1.11, EGG 0.46, CARROT 0.43. The guard released **205 units over 60 games** for **+2.5 coins/game** ⇒ **+0.73 coins per unit** — the "free lunch" is cannibalised by the price walk on our own other sales | **BUILT + DUELED — fails the bar (§4.1–4.3)** |
| 2 | **Per-item release multiplier** — decouple wool's release cap from the late-window items' (`forward_drain_mult_by_item`) | **measured +0.1 (WOOL 48) / −51.7 (late 12)** | the t38 sweep on the old base showed a plateau at ×24–×48; the t41 check on *this* base showed ×48 **−3.5 (t=−2.06) / −4.3 (t=−2.69)** — the global optimum is already at the plateau's left edge, and per-item decoupling confirms it | **BUILT + DUELED — no edge (§4.1)** |
| 3 | **MELON in the late window** (day 13+) — the only product never added to the forward list | **exactly 0 — the knob never binds** | MELON is the one item where we already beat the opponent on price in the losses (**+4.65/unit, price effect +357**), we sell **72.0 units in all 91 games (zero variance)**, and the counters of the melon build are **identical to the control** (`forward_orders` 1,439, `forward_units` 6,978) ⇒ the base already offers every melon unit it holds | **BUILT + DUELED — non-binding (§4.2)** |
| 4 | Extend the forward layer to CARROT / TOMATO / EGG | **≤ 0** | Task-28 measured on the shepherds base: carrot **+2**, tomato **0** (knob non-binding), egg **−5**, fertilizer **−299/−315**, wheat **−516/−762**. The refuted-input family | **refuted — not rebuilt** |
| 5 | Race hypothesis / robust decision rules (`implied`, `front`, `regret`, `avg`) | **≤ +4** | Task-8: all four rules differ from the clone point model in **0–2 steps per game** and land within **4 coins** of it (−177/−181/−180/−180 vs the stack, i.e. all ≈ the rebuild's own offset) | **refuted — not rebuilt** |
| 6 | Race item-set extension (CARROT/EGG/etc.) or pruning (−MELON) | **+0 … +1** | Task-36 on the shepherds base: `race_items +CARROT +EGG` = **+1**, `−MELON` = **Δ exactly 0** | **refuted — not rebuilt** |
| 7 | Price floors / deferral (hold stock for a better price) | **−376 … −546** | Task-36: floor 0.6×base **−466/−376**, 0.8× **−546/−444**, cap 0.5× **−31/−9** | **refuted — not rebuilt** |
| 8 | Sell inputs (wheat / fertilizer) as a strategy | **−299 … −762** | Task-28 fertilizer **−299/−315**, wheat **−516/−762**; Task-4/17 the buy quote exceeds the sell quote in scarcity | **refuted — not rebuilt** |
| 9 | Production-side (egg count, wheat→feed→milk conversion, herd/crop branch) | **+1,400 … +4,400** (foreign composites) | this is where the loss money actually is (§2.1: EGG −1,368, WHEAT −1,367); it lives in the base's `_hd2_*` / `_ca_*` / `_cs_*` / `_v92_p_*` economy-simulation family | **not reachable from the market layer; every attempt of ours has measured ≤ 0** |

### 4.1 Built candidates, screen and confirmation

**Screen panel 16400–16429 (60 games each, seats alternating, candidate vs
`data/candidate/pi_stack/main.py`). Every cell: `err = 0`, `cand_exceptions = 0`,
`base_exceptions = 0`, smoke `['DONE','DONE']` with an empty error dict.**

| variant | change vs the champion | screen Δ | screen t | W–L | confirm Δ | confirm t | W–L | verdict |
|---|---|---|---|---|---|---|---|---|
| **`t42_ctl`** | every new knob present but off — **the control** | **+0.0** | 0.00 | 4–4 | — | — | — | **OK: Δ exactly 0, wallet 92,583.2 vs 92,583.2** |
| `t42_guard` | overflow guard, last turn of each day, default items | +0.1 | +1.00 | 4–4 | — | — | — | no-go |
| `t42_guard_wide` | guard incl. WHEAT in the item set | +0.0 | 0.00 | 4–4 | — | — | — | no-go |
| `t42_guard_nof` | guard without FERTILIZER | +0.0 | 0.00 | 4–4 | — | — | — | no-go |
| **`t42_guard3`** | guard spread over the last **3** turns of each day | **+2.5** | +1.09 | 8–4 | **+5.8** | **+1.81** | 9–1 | **NO EDGE — best cell; fails t ≥ 3 on both panels** |
| `t42_wool48` | `forward_drain_mult_by_item = {WOOL: 48}` | +0.1 | +0.63 | 4–6 | — | — | — | no-go |
| `t42_late12` | `forward_drain_mult_by_item = {STRAWBERRY: 12, MILK: 12}` | **−51.7** | **−2.63** | 25–33 | — | — | — | no-go (worse) |
| `t42_melon` | MELON added to the forward list from step 312 | **+0.0** | 0.00 | 4–4 | — | — | — | **knob non-binding, not a bug (see §4.2)** |
| `t42b_guard_v2` | guard with corrected *executable*-sells accounting + dead-lot retargeting | +0.1 | +1.00 | 4–4 | — | — | — | no-go |
| `t42b_guard_v2_wide` | as above, incl. WHEAT | +0.0 | 0.00 | 4–4 | — | — | — | no-go |
| `t42b_guard_v2_3` | v2, last 3 turns of each day | +2.5 | +1.09 | 8–4 | (same design point as `t42_guard3`) | | | no-go |

### 4.2 Liveness evidence (byte-identity is a bug signature, so every null cell is diagnosed)

| variant | forward_orders | forward_units | guard units released | reading |
|---|---|---|---|---|
| `t42_ctl` | 1,439 | 6,978 | — | baseline |
| `t42_melon` | **1,439** | **6,978** | — | **identical to the control** in every counter: `want = min(projected, cap) − planned ≤ 0` on every step, i.e. the base already offers every melon unit it holds. This is consistent with the replay attribution — our melon sales are **72.0 units in every one of the 91 games, zero variance** — so the knob is non-binding, exactly the Task-36 strawberry-start precedent, not a broken build. |
| `t42_wool48` | 1,439 | 7,002 (+24) | — | binds, but only +0.4 units/game → Δ +0.1 |
| `t42_late12` | 1,458 | 5,867 (−1,111) | — | binds strongly → Δ −51.7 (t = −2.63) |
| `t42_guard` | 1,439 | 6,978 | **3** | barely binds |
| `t42_guard3` | 1,439 | 6,975 | **205** | binds → Δ +2.5 |
| `t42b_guard_v2_3` | — | — | **205** (independent implementation) | same ceiling: **3.4 units/game** |

### 4.3 Why the destroyed-goods channel is closed — the mechanistic measurement

The replay attribution says we **destroy 8.37 units/game** (12.71 in the losses) at the night
shed drop, worth ~518 coins/game at market prices. This is the largest single market-side
number in the whole diagnosis, which is why the guard was built to attack it. The measured
result is **≈ +0.73 coins per extra unit released**, not ~50:

* `t42_guard3` released **205 units over 60 games (3.4/game)** and gained **+2.5 coins/game**
  (+5.8 on the confirmation panel). 2.5 / 3.4 ≈ **0.73 coins per unit sold instead of
  destroyed**.
* The two guard implementations — v1 crediting the base's planned sells, v2 counting only
  *executable* sells and repairing dead lots — release **exactly 205 units** each: an
  independent cross-check of the ceiling, not a shared bug.
* The reason is structural and visible in the probe counters (`g_shed`, `g_hand`, `g_exe`): at
  hour 23 the **shed holds ~26 units but the workers carry ~102**. The overflow consists of
  *carried* goods, and `_commit_unit` SELL draws from the **shed only**, so a carried unit
  cannot be sold in the turn it is destroyed. The only way to make room is to have sold more
  *earlier* in the day — which is precisely what `forward_drain_mult` controls, and the t41
  sweep already located that optimum at ×24 (×48 is −3.5/−4.3 below it). The trade is
  "sell earlier and take the price walk" versus "hold and lose the unit", and the sweep says
  the walk costs more than the unit is worth.
* The corollary is the sharpest number in this report: **at the margin, one extra unit offered
  to this market is worth ≈ +0.7 coins**, against an average realised price of 45–120
  coins/unit for the goods in question. Any candidate whose mechanism is "offer more units" is
  dead on arrival — which is also why the whole per-item / forward-extension family
  (Task-28, Task-36) measures ≤ 0.

### 4.4 The one candidate I would still call live, and its honest EV

Nothing measured here clears the bar, so **no build was promoted**. If a further round is
spent, the only cell with a positive point estimate on both panels is `t42_guard3`
(**+2.5 / +5.8 coins per game, t = +1.09 / +1.81, W–L 8–4 / 9–1, `err = 0`, no exceptions**,
sha256 `518f36cbcd5665b3…`). Its expected value is **+0.002 … +0.006 % of wallet ≈ +0.3 … +0.9
rating points** on the project's own ruler. That does not survive the pre-registered bar, and
it is not worth a submission slot.

### 4.5 Exact artifacts for the built candidates

| variant | path | sha256 |
|---|---|---|
| control | `data/candidate/t42_ctl/main.py` | `17fe37877ab2f56b6e7bdbbf8ff4d6f30c2511e7b8af98247aa377e039f966b5` |
| overflow guard (1 turn) | `data/candidate/t42_guard/main.py` | `b60431327619327650909272ea4dc25d249ab55b7fbe81468e0f96d4a1a744b5` |
| **overflow guard (3 turns) — best cell** | `data/candidate/t42_guard3/main.py` | `518f36cbcd5665b31443308eba9b7c5e96a16e53bd3c646806eb35c06ffe6178` |
| per-item mult WOOL 48 | `data/candidate/t42_wool48/main.py` | `df163d943812a6c305efe44eaadf4912a96dc86a6469f93d8f1fd423f94e166e` |
| per-item mult late 12 | `data/candidate/t42_late12/main.py` | `147b18ac71bcf1fc3502a2bafb651bae459351f0e904786044c8a9b210803958` |
| melon late window | `data/candidate/t42_melon/main.py` | `1c9b00121a04a8d64b8b8bfa699999f0a1229b31b2457938003bdbb089d5c719` |
| guard v2 (corrected accounting) | `data/candidate/t42b_guard_v2/main.py` | `300d46d7b3b0a206d1d91a266ec857161e2f35c3c2b1b2d8dcb40296fa3f2f4e` |

**Rebuild (deterministic; both scripts rebuild every cell from the race-only intermediate
`data/candidate/pi_stack_raceonly/main.py`):**

```bash
.venv/bin/python scripts/t42_sweep.py     # 8 cells: build, smoke gate, screen, confirm
.venv/bin/python scripts/t42b_sweep.py    # the corrected guard; --probe prints g_* counters
```

Champion for reference: `data/candidate/pi_stack/main.py`, sha256
`65962e928b0712946e1bacb929b4fb919a7231f34e1bc99c7e350d4e2755f317`.
Raw results: `data/candidate/t42-sweep.json`, `data/candidate/t42b-sweep.json`,
`data/candidate/duel-t42-*.json`.

---

## 5. What I could NOT find, and why 2,400 is probably out of reach

1. **No market-layer change of the required size exists in the measured space.** The whole
   reachable channel is the realised-price channel, and in the loss games the net market
   channel is already *positive* for us (WOOL +567, MILK +325, MELON +138). The negative
   price effects (−1,223 wool, −580 strawberry, −690 fertilizer) are the mechanical cost of
   the *extra volume* we push (wool +1,791 volume effect), not a fixable mis-assignment: the
   engine quotes both players the same pre-commit price for a paired unit, so the only lever
   is slot order, and Task-1/Task-8 measured that lever's perfect-information oracle at
   **+513/+963 per game**, of which the shipped clone search already captures
   **+316/+742** (80–100 %). The remaining layout headroom is a few hundred coins/game at
   most, not 2,860.
2. **The loss money is in production, not in the market.** EGG (−1,368) and WHEAT net of feed
   (−1,367) are 103 % of the −2,657 loss margin; both are decided inside the base's economy
   layers. We can add SELL lots but we cannot make the farm produce more eggs or convert feed
   into milk more efficiently. Every attempt of ours to touch that family has measured ≤ 0
   (the standing, repeatedly reproduced result of Tasks 4–19, 26, 28).
3. **The two-panel bar is the binding constraint, not the point estimate.** A candidate worth
   +200 coins/game is ~0.2 % of wallet, which the project's own ruler (~145 rating points per
   +1 % wallet) turns into **~+29 points** — 11 % of the 259 needed. Even a candidate that
   *passed* the bar would leave us at ~2,170.
4. **The largest *apparently* reachable market number is a mirage, and I can now prove it.**
   The 8.37 destroyed units/game look like a 518-coin/game free lunch; the measured price of
   that lunch is **+0.73 coins per unit** (205 units released for +2.5 coins/game). The
   general form of the finding is that **this build's market is saturated: the marginal
   offered unit is worth ≈ 0.7 coins.** Every "sell more / sell sooner / sell something else"
   idea — the whole per-item family, the per-item multipliers, the anti-discard guard — is the
   same idea, and this is the number that kills it. Anyone proposing another one should first
   produce a measurement that the marginal unit is worth more than ~1 coin.
5. **A specific trap I want on the record.** An earlier version of my own accounting put
   `BUY_LAND` into both the "purchases" channel and the "hire+land" channel, producing a
   non-zero closure residual (−44 / −286 / +63 in the three windows). Closing the books
   *exactly* (residual 0.0000) is what makes the item table trustworthy; §2.1 is the closed
   version. **Report the closure residual or the attribution is worthless.**
6. **What would actually move the needle** (for whoever picks this up): the ladder is a
   1 %-of-wallet coin flip decided in days 12–29, and the variable that discriminates our
   losses from our wins is our *own* production in the drawn town (95,054 vs 103,318 coins,
   i.e. our build's town-branch sensitivity is bigger than the margin). That points at
   (a) making the base's herd/crop branch robust across town draws and (b) the
   feed→milk→wool conversion — both S3-scale economy work, not layers.
7. **The honest read on 2,400.** At the observed opponent pool it needs a ~96 % win rate. Our
   best measured build is 84.6 % over 91 games. The four sub-0.60-opponent losses are worth
   ~+60 points in total; the remaining ~200 points require beating the 0.68–0.94-own-WR teams
   consistently, which is exactly the population our build currently loses to — in towns where
   the *opponent's* build scores 100,204 while ours scores 95,054. **On the evidence assembled
   here, 2,400 is not reachable by any change our layer architecture can express.**

### 5.1 Full list of what was tried this round and returned nothing

| tried | result |
|---|---|
| 91 replays fetched, re-simulated, bank-exact | 91/91 gate, accounting residual 0.0000 |
| end-of-day overflow guard (2 independent implementations, 4 item sets, 1 and 3 turns) | best +2.5/+5.8, t = 1.09/1.81 → fails bar |
| per-item release multiplier (WOOL 48; late-window 12) | +0.1 ; −51.7 |
| MELON late window | knob non-binding (counters identical to control) |
| race_hyp / race_rule / race_items / pruning | not rebuilt: refuted by Task-8 / Task-36, and re-derivable from the loss tables |
| price floors, input selling, tomato/egg/carrot/fert extensions | not rebuilt: refuted by Task-28 / Task-36 |
| a stronger base | not this round: refuted by Task-27 / Task-35 / Task-40 (4 extractable high-claim bases, all neutral to worse, all carrying our exact tape) |
