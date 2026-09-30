# Wheat-gap decomposition — verdict: neither produce-more nor lose-less, and not worth reaching

Date: 2026-09-19. Incumbent/live line: `data/forward/wool_drain1_outerprem/main.py`
(the stack, ref 56349751). Instrument: `scripts/wheat_flow.py` (per-action replay of
the engine's own `_apply_unit_action`, plus the validated `scripts/lockstep.py` replica
for the market phase), 60 duel towns (9000–9029 + 9100–9129), one game per town.

## 0. Verdict

1. **They do not produce more wheat** — over the 60 towns the frontier harvests
   **−278 units** relative to us, with **−14,210 wheat tile-steps** and **−237 wheat
   plantings**. Its crop allocation is, if anything, slightly smaller on wheat.
2. **Neither of us loses wheat** — shed-overflow discards are **0 for both agents**
   across all 60 towns (`discarded` counts every unit lost when a DROP/PLACE or the
   end-of-day cargo drop hits the 100-item shed cap). There is no loss channel to close.
3. The only wheat difference is that the frontier **buys +1,040 and sells +495 more
   units**, and that channel is **net negative for it: −6,658 cash** over the 60 towns,
   because in the scarcity regime the buy quote (`price(inv-1)`) is above the sell quote
   (`price(inv)`), so buying wheat to sell it is a losing round trip.
4. **Correction to my own Task 4 numbers.** The "+2,215 / +3,426 wheat" I reported was a
   two-seed artefact (9009 / 9005). Aggregated over the 60 duel towns the wheat cash
   delta is **−111 per town** (median +8, positive in 30/60 towns), its correlation with
   the per-town wallet gap is **−0.02**, and its share of the gap is **−2.5%**. Wheat is
   not the residual.
5. **No build.** No lever in our plan is indicated by the decomposition: there is no
   discard to avoid, no harvest to recover (we already harvest more), and the one flow we
   could copy (extra buys) loses money. Ladder unchanged, so the fraction of the frontier
   gap explained stays **~18% in-sample / ~25% out-of-sample** (the stack).

## 1. The flow decomposition (60 towns, frontier = cand vs champion = base)

Every unit is attributed exactly: a positive jump in the wheat held by (shed + farmer +
hands) when replaying a unit action is a HARVEST, a negative jump on a FEED is feed, a
negative jump elsewhere is a discard at the shed cap, and the market phase gives executed
sells and executed WHEAT buys. The accounting closes to ≤6 units per game (`balance`),
which is the check that nothing is unaccounted for.

| metric | frontier | champion | delta |
|---|---|---|---|
| harvested units | 34,627 | 34,905 | **−278** |
| wheat tile-steps (crop-days planted) | 723,442 | 737,652 | **−14,210** |
| wheat plantings | 9,481 | 9,718 | −237 |
| HARVEST actions (all crops) | 29,115 | 29,124 | −9 |
| FERTILIZE actions | 7,037 | 6,494 | +543 |
| **discarded units (shed overflow)** | **0** | **0** | 0 |
| bought units (executed) | 17,880 | 16,840 | **+1,040** |
| fed units | 20,113 | 19,891 | +222 |
| sold units | 32,269 | 31,774 | **+495** |
| sell revenue | 1,271,725 | 1,238,257 | +33,468 |
| buy spend | 704,771 | 659,831 | +44,940 |
| **net wheat cash** | 596,731 | 603,389 | **−6,658** |
| wallet (whole agent) | 6,032,653 | 5,768,121 | +264,532 |

Per town the wheat net delta is +4,409 wallet for the frontier but **−111** wheat cash,
positive in only half the towns, and uncorrelated with the win (−0.02): two towns show
large losses (−2,974 at 9127, −2,018 at 9128) where the frontier still wins by 6,196 and
7,216. So the wheat flow is an incidental by-product of its "ask for everything every
step" style (more buys execute), not a source of edge.

## 2. Where the frontier's +264,532 actually comes from (per-item cash, 60 towns)

Same instrument, per product, cash net of that product's own buys:

| item | frontier sold | champion sold | Δ units | frontier net | champion net | **Δ net** | share of the gap |
|---|---|---|---|---|---|---|---|
| **WOOL** | 10,704 | 10,029 | +675 | 1,358,873 | 1,191,064 | **+167,809** | **63%** |
| **MILK** | 12,163 | 12,126 | +37 | 1,385,683 | 1,326,871 | **+58,812** | **22%** |
| **CARROT** | 6,514 | 5,598 | +916 | 327,955 | 276,437 | **+51,518** | **20%** |
| **STRAWBERRY** | 14,763 | 14,973 | −210 | 1,839,182 | 1,799,865 | **+39,317** | **15%** |
| TOMATO | 800 | 800 | 0 | 113,849 | 113,322 | +527 | 0% |
| MELON | 4,320 | 4,320 | 0 | 882,405 | 883,590 | −1,185 | −0.4% |
| WHEAT | 32,269 | 31,774 | +495 | 596,731 | 603,389 | −6,658 | −2.5% |
| FERTILIZER | 20,067 | 20,594 | −527 | 760,354 | 769,238 | −8,884 | −3.4% |
| EGG | 3,498 | 3,937 | −439 | 188,497 | 211,502 | −23,005 | −8.7% |
| **total** | | | | | | **+278,251** | (wallet +264,532) |

And the mechanism is **price, not quantity** — the frontier sells the same units in the
same day windows and simply realises more per unit:

| seed | item | frontier units (early/late) | mean price | champion units (early/late) | mean price | Δ mean |
|---|---|---|---|---|---|---|
| 9005 | WOOL | 393 (266/127) | 168.7 | 353 (216/137) | 161.7 | +7.0 |
| 9005 | MILK | 149 (106/43) | 36.5 | 150 (109/41) | 30.8 | +5.8 |
| 9005 | STRAWBERRY | 246 (170/76) | 79.6 | 249 (170/79) | 76.5 | +3.1 |
| 9009 | WOOL | 236 (172/64) | 113.4 | 243 (162/81) | 95.4 | +18.0 |
| 9009 | MILK | 176 (113/63) | 116.4 | 175 (116/59) | 112.6 | +3.8 |
| 9009 | STRAWBERRY | 246 (170/76) | 50.3 | 249 (170/79) | 44.0 | +6.3 |

The day-window columns are near-identical, so this is not temporal spreading; it is the
lockstep's within-turn ordering — whichever side commits earlier in a turn's global unit
order gets the higher price for that unit, and the frontier is persistently earlier. Our
race layer exploits the same lever but only reaches +597 per game (18% of the gap), and
the forward layer adds ~+200 on top, because both are limited to re-slotting *our own*
list under a clone hypothesis about the rival's layout.

## 3. Levers considered and rejected (all measured, no build)

| candidate lever | why not |
|---|---|
| avoid shed-overflow discards | discards are 0 for both agents on all 60 towns — nothing to recover |
| harvest more wheat / allocate more land to wheat | we already harvest +278 more on −14,210 fewer tile-steps; nothing to copy |
| FERTILIZE more (the frontier runs +543 actions) | its extra fertilising does not translate into more harvested wheat (it harvests less), so this is not a wheat lever; it may be a carrot/strawberry lever (see below) |
| buy wheat to re-sell, frontier-style | measured net −6,658 over 60 towns: the buy quote exceeds the sell quote in the scarcity regime |
| move a bulk wheat purchase earlier | not indicated by any of the above; and per Task 4 any plan edit can flip the day-6 shop draw, so it would need a full paired duel for an effect the decomposition shows is ~0 |
| close the EGG gap (−23,005) | this is the frontier losing on eggs (fewer geese), i.e. the mirror of its wool/milk gain; it is not a lever for us |

## 4. What this leaves, and the recommended next round

The residual is now measured to be: **the same units at a systematically better realised
price, on WOOL (63%), MILK (22%), CARROT (20%) and STRAWBERRY (15%)**, with our offsetting
advantages on EGG/FERTILIZER/WHEAT. The only lever that attacks that is the within-turn
ordering, and our implementation of it captures 18% of the gap. So the highest-value next
step is to strengthen that mechanism rather than to touch the plan:

1. **Replace the clone hypothesis in the race layer with a predictive rival layout.**
   The clone assumption (our list == the rival's list) is what caps the assignment: it can
   only permute our items among our own slots. The observable rival information is its
   per-item executed quantities, recoverable exactly from the public inventory delta and
   the town drain (`race_layer.implied_quantities`, already implemented but unused), and
   its slot layout can be inferred from the first turn in which each item's inventory
   moves. Place each of our items at the earliest slot where the rival is *not* selling
   that item, rather than at the slot the clone hypothesis likes.
2. **Extend the drain-keyed forward layer to MILK and CARROT** (`prem_drain1` was only
   smoke-tested at one seed, −189, and never duelled); these two are 42% of the gap
   between them and have no geese/herd entanglements.
3. Do not spend another round on the plan: wheat is measured at −2.5% of the gap, the
   herd mix is negative, sheep-days are +27 days (~+8% of output), care coverage is equal
   to better, and the router's tape choice is not mis-selecting.

## 5. Artifacts and rebuild

```bash
# wheat flow + per-item cash over the 60 duel towns (also prints the per-item table)
.venv/bin/python scripts/wheat_flow.py --seeds 9000-9029,9100-9129 --procs 10 \
    --out data/wheat-flow-items.json
# depth on one town
.venv/bin/python scripts/wheat_flow.py --seeds 9005,9009
```

Artifacts: `scripts/wheat_flow.py`, `data/wheat-flow.txt`, `data/wheat-flow.json`,
`data/wheat-flow-items.txt`, `data/wheat-flow-items.json`.

Note on the revenue columns: `sell_revenue` / `buy_spend` come from replaying the sells
and the buys separately (so the buy prices differ slightly from the joint replay);
`net_cash` comes from the joint replay and is the authoritative money figure. The
per-item table uses the joint replay, so its row sum (+278,251) differs from the wallet
gap (+264,532) only by the non-market costs (seeds, animals, land, hires).
