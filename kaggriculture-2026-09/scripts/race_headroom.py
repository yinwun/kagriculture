#!/usr/bin/env python
"""Ceiling of the sell-layout mechanism, measured on real games.

For every step of a recorded game we know both players' true market lists.  Three
numbers per step:

  base   -- the differential `revenue_me - revenue_opp` of the layout the champion
            actually used (evaluated with the validated replica);
  oracle -- the best differential reachable by re-assigning our own SELL lots to
            slots, given the rival's TRUE layout (perfect information);
  honest -- the differential of the layout our layer picks when the rival's layout
            is only PREDICTED (the hypothesis it will really run with).

`sum(oracle - base)` over a game is an upper bound on what any sell-layout layer
could add to our wallet in that game; `sum(honest - base)` is the realistic one.

Usage:
  .venv/bin/python scripts/race_headroom.py --base data/tapeopt/rgcs/main.py \
      --cand data/cand/the-2945-.../main.py --seeds 9000,9005
  .venv/bin/python scripts/race_headroom.py --seeds 9000,9001        # mirror game
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))
import lockstep  # noqa: E402
import race_layer  # noqa: E402
import race_trace  # noqa: E402

CHAMPION = ROOT / "data" / "tapeopt" / "rgcs" / "main.py"
PRODUCTS = list(lockstep.PRODUCTS)
BASE_PRICE = {it: lockstep.MARKET_PARAMS[it]["base"] for it in PRODUCTS}


def step_diff(my_orders, rival_orders, inv, my_shed, rival_shed):
    """Exact `revenue_me - revenue_opp` for a whole step, per item, summed."""
    total = 0.0
    rivals = race_layer.schedule(rival_orders)
    mine = race_layer.schedule(my_orders)
    for it in set(list(rivals) + list(mine)):
        a, b, _s, _i = lockstep.clear_item(
            mine.get(it, {}), rivals.get(it, {}), it, inv.get(it, 0),
            max(0, int(my_shed.get(it, 0))), max(0, int(rival_shed.get(it, 0))))
        total += a - b
    return total


def oracle_diff(my_orders, rival_orders, inv, my_shed, rival_shed, max_slots=10):
    """Best differential over all re-assignments of our sells, perfect rival info."""
    sells, fixed = race_layer.split_orders(my_orders, max_slots)
    if not sells:
        return None, None
    rivals = race_layer.schedule(rival_orders)
    contest = [i for i, (_s, it, _q) in enumerate(sells) if rivals.get(it)]
    if not contest:
        return None, None
    fixed_slots = {s for s, _o in fixed}
    allowed = [s for s in range(max_slots) if s not in fixed_slots]
    weight = {}
    for i in contest:
        _sl, it, q = sells[i]
        avail = min(q, max(0, int(my_shed.get(it, 0))))
        opp = max(0, int(rival_shed.get(it, 0)))
        weight[i] = {s: lockstep.clear_item({s: avail}, rivals.get(it, {}), it,
                                            inv.get(it, 0), avail, opp)[0]
                        - lockstep.clear_item({s: avail}, rivals.get(it, {}), it,
                                              inv.get(it, 0), avail, opp)[1]
                     for s in allowed}
    # exact assignment by brute force (contested set is small on real steps)
    items = sorted(weight)
    best = {"v": None, "p": None}

    def rec(pos, used, val, place):
        if pos == len(items):
            if best["v"] is None or val > best["v"]:
                best["v"], best["p"] = val, dict(place)
            return
        i = items[pos]
        for s in allowed:
            if s in used:
                continue
            used.add(s)
            place[i] = s
            rec(pos + 1, used, val + weight[i][s], place)
            del place[i]
            used.remove(s)

    rec(0, set(), 0.0, {})
    if best["p"] is None:
        return None, None
    new = race_layer._assemble(my_orders, best["p"], max_slots)
    return step_diff(new, rival_orders, inv, my_shed, rival_shed), new


def analyse(seed, base_path, cand_path, max_slots=10):
    trace, final = race_trace.record(seed, [str(cand_path), str(base_path)])
    steps = sorted(set(trace[0]) & set(trace[1]))
    sum_base = sum_oracle = sum_honest = 0.0
    n_oracle = n_reorder = 0
    top = []
    for s in steps:
        a, b = trace[0][s], trace[1][s]
        base = step_diff(a["market"], b["market"], a["inv"], a["shed_mkt"], b["shed_mkt"])
        sum_base += base
        od, odlayout = oracle_diff(a["market"], b["market"], a["inv"], a["shed_mkt"],
                                   b["shed_mkt"], max_slots)
        if od is not None:
            n_oracle += 1
            sum_oracle += od
            if od - base > 0.5:
                top.append((od - base, s, a["market"], b["market"], odlayout))
        # honest: rival layout predicted as our own pre-layer list
        new, _gain = race_layer.choose_layout(
            a["market"], a["market"], a["inv"], a["shed_mkt"], a["shed_mkt"],
            max_slots=max_slots)
        hd = step_diff(new, b["market"], a["inv"], a["shed_mkt"], b["shed_mkt"])
        sum_honest += hd
        if new != a["market"]:
            n_reorder += 1
    top.sort(reverse=True)
    print(f"seed {seed}: final cand {final[0]:,.0f} base {final[1]:,.0f} "
          f"(delta {final[0]-final[1]:+,.0f})")
    print(f"   per-step differential: actual {sum_base:,.0f}   "
          f"oracle {sum_oracle:,.0f} (+{sum_oracle-sum_base:,.0f})   "
          f"honest-clone-hypothesis {sum_honest:,.0f} "
          f"(+{sum_honest-sum_base:,.0f})")
    print(f"   steps where a layout could help: {len(top)} of {n_oracle} contested "
          f"steps; steps the layer actually changed: {n_reorder}")
    for gain, s, mine, theirs, layout in top[:5]:
        print(f"      step {s:3d} oracle gain {gain:+8.1f}: {mine} vs {theirs} -> {layout}")
    return {"seed": seed, "base": sum_base, "oracle": sum_oracle, "honest": sum_honest,
            "n_oracle": n_oracle, "n_help": len(top), "n_reorder": n_reorder,
            "final": final}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--seeds", default="9000,9001")
    ap.add_argument("--base", default=str(CHAMPION))
    ap.add_argument("--cand", default=str(CHAMPION))
    ap.add_argument("--max-slots", type=int, default=10)
    args = ap.parse_args()
    for seed in [int(x) for x in args.seeds.split(",")]:
        analyse(seed, args.base, args.cand, args.max_slots)
    return 0


if __name__ == "__main__":
    sys.exit(main())
