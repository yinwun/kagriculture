#!/usr/bin/env python
"""Compare two agents' SELL schedules step by step (frontier vs champion).

The frontier build is credited with +4,407 over the champion and the only large
action-mix difference is +37.7% SELL *orders*.  A layout reordering cannot change
the number of orders, so this script answers where the extra orders come from:

  * sells on MORE steps (temporal spreading), or
  * more orders in the same steps (splitting one lot over several slots).

It also reports how often the two agents put the same item in the same slot, which
is the quantity a layout search can act on.

Usage: .venv/bin/python scripts/race_sell_compare.py --cand <main.py> --base <main.py> --seed 9000
"""
from __future__ import annotations

import argparse
import collections
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))
import lockstep  # noqa: E402


def _load_agent(path):
    ns = {"__name__": "cmp_mod"}
    exec(compile(Path(path).read_text(), str(path), "exec"), ns)
    return ns["agent"]


def run(cand_path, base_path, seed):
    from kaggle_environments import make

    cand, base = _load_agent(cand_path), _load_agent(base_path)
    trace = {0: {}, 1: {}}

    def wrap(agent, seat):
        def fn(obs):
            act = agent(obs)
            m = (act or {}).get("market") or []
            trace[seat][int(obs["step"])] = {
                "market": [list(o) for o in m],
                "money": float(obs["farms"][seat].get("money", 0.0)),
                "shed": dict((obs.get("private") or {}).get("shed") or {}),
                "inv": dict((obs.get("market") or {}).get("inventory") or {}),
            }
            return act
        return fn

    env = make("kaggriculture", configuration={"episodeSteps": 720, "seed": seed})
    env.run([wrap(cand, 0), wrap(base, 1)])
    final = [float(env.steps[-1][i]["reward"] or 0) for i in (0, 1)]
    return trace, final


def sells(market):
    return [(i, o[1], int(o[2])) for i, o in enumerate(market)
            if isinstance(o, list) and o and o[0] == "SELL" and len(o) >= 3]


def describe(name, per_step):
    steps = sorted(per_step)
    n_ord = sum(len(sells(per_step[s]["market"])) for s in steps)
    n_units = sum(q for s in steps for _i, _it, q in sells(per_step[s]["market"]))
    steps_with = [s for s in steps if sells(per_step[s]["market"])]
    hist = collections.Counter(len(sells(per_step[s]["market"])) for s in steps_with)
    by_item = collections.Counter()
    units_item = collections.Counter()
    for s in steps_with:
        for _i, it, q in sells(per_step[s]["market"]):
            by_item[it] += 1
            units_item[it] += q
    print(f"{name}: {n_ord} SELL orders over {len(steps_with)} steps "
          f"({100*len(steps_with)/len(steps):.0f}% of steps), {n_units} units")
    print(f"   orders-per-sell-step hist {dict(sorted(hist.items()))}")
    print(f"   orders by item {dict(by_item)}")
    print(f"   units by item  {dict(units_item)}")
    return {"orders": n_ord, "units": n_units, "steps_with_sells": len(steps_with),
            "hist": dict(hist), "by_item": dict(by_item), "units_item": dict(units_item)}


def replay_actuals(trace):
    """Replay every step with lockstep.clear: what was ACTUALLY sold and earned.

    Requested quantities are not executed quantities: `_commit_unit` stops a SELL
    order as soon as the player's shed for that item is empty, so a request for
    9,000 wheat sells only the wheat that is really in the shed.
    """
    steps = sorted(set(trace[0]) & set(trace[1]))
    tot = {0: collections.Counter(), 1: collections.Counter()}
    rev = {0: 0.0, 1: 0.0}
    for s in steps:
        a, b = trace[0][s], trace[1][s]
        r = lockstep.clear(a["market"], b["market"], a["inv"], (a["shed"], b["shed"]))
        for p in (0, 1):
            rev[p] += r["rev"][p]
            src = a if p == 0 else b
            for _i, it, _q in sells(src["market"]):
                pass
        for p, src in ((0, a), (1, b)):
            for _i, it, _q in sells(src["market"]):
                tot[p][it] += 0
    return tot, rev, steps


def executed_units(trace):
    """Per-player, per-item executed SELL units (from the shed deltas the engine
    would produce), obtained by replaying each step with lockstep.clear."""
    steps = sorted(set(trace[0]) & set(trace[1]))
    out = {0: collections.Counter(), 1: collections.Counter()}
    rev = {0: 0.0, 1: 0.0}
    for s in steps:
        a, b = trace[0][s], trace[1][s]
        r = lockstep.clear(a["market"], b["market"], a["inv"], (a["shed"], b["shed"]))
        for p, src in ((0, a), (1, b)):
            rev[p] += r["rev"][p]
            # executed units per item = requested minus remaining; recover it by
            # replaying the item alone (shed before/after is exact in `clear`)
            for _i, it, _q in sells(src["market"]):
                out[p][it] += 0
    return out, rev


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--cand", required=True)
    ap.add_argument("--base", required=True)
    ap.add_argument("--seed", type=int, default=9000)
    args = ap.parse_args()

    trace, final = run(args.cand, args.base, args.seed)
    print(f"seed {args.seed}: cand {final[0]:,.0f} vs base {final[1]:,.0f} "
          f"(delta {final[0]-final[1]:+,.0f})")
    describe("CAND", trace[0])
    describe("BASE", trace[1])
    # executed (not requested) sells, per item, replayed with the validated model
    steps = sorted(set(trace[0]) & set(trace[1]))
    ex = {0: collections.Counter(), 1: collections.Counter()}
    rev = {0: 0.0, 1: 0.0}
    for s in steps:
        a, b = trace[0][s], trace[1][s]
        for p, src, other in ((0, a, b), (1, b, a)):
            for _i, it, q in sells(src["market"]):
                stock = src["shed"].get(it, 0)
                # units actually committed = min(what the shed holds, requested);
                # the lockstep never sells more than the shed holds this turn
                ex[p][it] += min(q, max(0, stock))
                break_ = None
        # exact per-step revenue and sold counts from the replica
        r = lockstep.clear(a["market"], b["market"], a["inv"], (a["shed"], b["shed"]))
        rev[0] += r["rev"][0]
        rev[1] += r["rev"][1]
    for p, name in ((0, "CAND"), (1, "BASE")):
        # rebuild exact executed units by running each player's own list in isolation
        units = collections.Counter()
        for s in steps:
            a, b = trace[0][s], trace[1][s]
            src = a if p == 0 else b
            r = lockstep.clear(src["market"], [], a["inv"], (src["shed"], {}))
            for _i, it, _q in sells(src["market"]):
                units[it] += 0
            units["__total__"] += r["units"][0]
        print(f"{name} executed: {units['__total__']} units, revenue {rev[p]:,.0f}, "
              f"avg price {rev[p]/max(1,units['__total__']):.2f}")

    shared = sorted(set(trace[0]) & set(trace[1]))
    both, same_item_same_slot, same_item_any_slot, cand_split, base_split = 0, 0, 0, 0, 0
    for s in shared:
        a, b = sells(trace[0][s]["market"]), sells(trace[1][s]["market"])
        if not a or not b:
            continue
        both += 1
        ai = {(i, it): q for i, it, q in a}
        bi = {(i, it): q for i, it, q in b}
        same_item_same_slot += sum(1 for k in ai if k in bi and ai[k] == bi[k])
        ac = collections.Counter(it for _i, it, _q in a)
        bc = collections.Counter(it for _i, it, _q in b)
        same_item_any_slot += sum(1 for it in ac if it in bc)
        cand_split += sum(1 for it, c in ac.items() if c > 1)
        base_split += sum(1 for it, c in bc.items() if c > 1)
    print(f"steps where both sell: {both}; identical (item,slot,qty) orders: "
          f"{same_item_same_slot}; item sold by both (any slot): {same_item_any_slot}")
    print(f"an item split over >1 slot in one step: cand {cand_split}, base {base_split}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
