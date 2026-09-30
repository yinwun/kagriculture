#!/usr/bin/env python
"""Exact wheat-flow decomposition for both players of a real game.

Why this is measurable at all: in a step the engine runs the unit actions first and
the market second, and the only things that move WHEAT during the unit phase are

    HARVEST        + (yield_units move from the tile into a unit's inventory)
    FEED           - (one wheat per fed animal)
    PICKUP         shed -> inventory      (conserves the total)
    DROP / PLACE   inventory -> shed      (conserves it, minus shed overflow discard)

so replaying the step's unit actions one at a time on a copy of the farm/private
state -- with the engine's own `_apply_unit_action`, the instrument used by
scripts/race_trace.py -- and watching the total wheat held by (shed + farmer + hands)
after each action attributes every unit exactly: a positive jump is a harvest, a
negative jump on a FEED is feed, a negative jump elsewhere is a discard at the shed
cap.  The market phase then gives executed sells and WHEAT buys from the validated
replica (`scripts/lockstep.py`).

Usage:
  .venv/bin/python scripts/wheat_flow.py --cand <main.py> --base <main.py> --seeds 9005,9009
"""
from __future__ import annotations

import argparse
import copy
import json
import multiprocessing as mp
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))
import lockstep  # noqa: E402

CHAMPION = str(ROOT / "data" / "tapeopt" / "rgcs" / "main.py")
FRONTIER = str(ROOT / "data" / "cand" / "the-2945-farm-96-vs-the-top-10-public-bots" / "main.py")
ITEM = "WHEAT"


def _load(path):
    ns = {"__name__": "wheat_mod"}
    exec(compile(Path(path).read_text(), str(path), "exec"), ns)
    return ns["agent"]


def _held(farm, priv):
    """Wheat held by the shed and by every unit (the quantity the unit phase moves)."""
    total = max(0, int(priv["shed"].get(ITEM, 0)))
    for inv in priv["inventories"]:
        total += max(0, int((inv or {}).get(ITEM, 0)))
    return total


def flow(seed, cand_path, base_path):
    from kaggle_environments import make
    from kaggle_environments.envs.kaggriculture import kaggriculture as eng

    agents = [_load(cand_path), _load(base_path)]
    acc = {0: {"harvest": 0, "fed": 0, "discard": 0, "steps": 0, "fert": 0,
               "plant_wheat": 0, "wheat_tile_steps": 0, "harvest_actions": 0},
           1: {"harvest": 0, "fed": 0, "discard": 0, "steps": 0, "fert": 0,
               "plant_wheat": 0, "wheat_tile_steps": 0, "harvest_actions": 0}}
    steps_rec = {0: {}, 1: {}}

    def wrap(agent, seat):
        def fn(obs):
            act = agent(obs) or {}
            board = len(obs.farms[seat]["tiles"])
            day = int(obs.day)
            priv = copy.deepcopy(obs.private)
            farm = copy.deepcopy(obs.farms[seat])
            units = [act.get("farmer") or ["PASS"]] + list(act.get("hands") or [])
            for a in units:
                if isinstance(a, list) and a:
                    if a[0] == "FERTILIZE":
                        acc[seat]["fert"] += 1
                    elif a[0] == "PLANT" and len(a) > 1 and a[1] == "WHEAT":
                        acc[seat]["plant_wheat"] += 1
                    elif a[0] == "HARVEST":
                        acc[seat]["harvest_actions"] += 1
            tiles = obs.farms[seat]["tiles"]
            for row in tiles:
                for t in row:
                    if isinstance(t, dict) and t.get("kind") == "PLANT" and t.get("crop") == ITEM:
                        acc[seat]["wheat_tile_steps"] += 1
            for idx, a in enumerate(units):
                before = _held(farm, priv)
                eng._apply_unit_action(farm, priv, idx, a, board, day, 24, 100)
                after = _held(farm, priv)
                if after > before:
                    acc[seat]["harvest"] += after - before
                elif after < before:
                    if isinstance(a, list) and a and a[0] == "FEED":
                        acc[seat]["fed"] += before - after
                    else:
                        acc[seat]["discard"] += before - after
            acc[seat]["steps"] += 1
            steps_rec[seat][int(obs["step"])] = {
                "market": [list(o) for o in (act.get("market") or [])],
                "inv": {k: int(v) for k, v in dict(obs.market.inventory).items()},
                "shed_mkt": {k: int(v) for k, v in dict(priv["shed"]).items()},
                "shed_obs": {k: int(v) for k, v in dict(obs.private["shed"]).items()},
            }
            return act
        return fn

    env = make("kaggriculture", configuration={"episodeSteps": 720, "seed": seed})
    env.run([wrap(agents[0], 0), wrap(agents[1], 1)])
    final = [float(env.steps[-1][i]["reward"] or 0) for i in (0, 1)]

    out = {"seed": seed, "final": final, "delta": final[0] - final[1]}
    for seat, name in ((0, "cand"), (1, "base")):
        per_item = {}
        for it in lockstep.PRODUCTS:
            sld = bt = 0
            neti = 0.0
            for st in sorted(steps_rec[seat]):
                e = steps_rec[seat][st]
                both = [o for o in e["market"] if isinstance(o, list) and len(o) >= 3
                        and o[0] in ("SELL", "BUY_PRODUCT") and o[1] == it]
                if not both:
                    continue
                r = lockstep.clear(both, [], e["inv"], (e["shed_mkt"], {}),
                                   money=(10 ** 9, 10 ** 9))
                sld += r["units"][0]
                neti += r["rev"][0]
                bt += r["shed"][0][it] - e["shed_mkt"].get(it, 0) + r["units"][0]
            per_item[it] = {"sold": sld, "bought": bt, "net_cash": neti}
        out[name + "_items"] = per_item
        rec = steps_rec[seat]
        sold = bought = 0
        net = 0.0        # cash change from this item's sells minus its buys
        gross = 0.0      # sell revenue only (buy prices then differ slightly)
        spend = 0.0      # wheat buy cost only
        for s in sorted(rec):
            e = rec[s]
            both = [o for o in e["market"] if isinstance(o, list) and len(o) >= 3
                    and o[0] in ("SELL", "BUY_PRODUCT") and o[1] == ITEM]
            if not both:
                continue
            r = lockstep.clear(both, [], e["inv"], (e["shed_mkt"], {}),
                               money=(10 ** 9, 10 ** 9))
            sold += r["units"][0]
            net += r["rev"][0]
            bought += r["shed"][0][ITEM] - e["shed_mkt"].get(ITEM, 0) + r["units"][0]
            sells = [o for o in both if o[0] == "SELL"]
            buys = [o for o in both if o[0] == "BUY_PRODUCT"]
            if sells:
                rs = lockstep.clear(sells, [], e["inv"], (e["shed_mkt"], {}),
                                    money=(10 ** 9, 10 ** 9))
                gross += rs["rev"][0]
            if buys:
                rb = lockstep.clear(buys, [], e["inv"], (e["shed_mkt"], {}),
                                    money=(10 ** 9, 10 ** 9))
                spend += -rb["rev"][0]
        last = rec[max(rec)]
        leftover = sum(max(0, int((inv or {}).get(ITEM, 0)))
                       for inv in [{}]) + 0
        out[name] = {
            "harvested": acc[seat]["harvest"],
            "fed": acc[seat]["fed"],
            "discarded": acc[seat]["discard"],
            "sold": sold,
            "bought": bought,
            "sell_revenue": gross,
            "buy_spend": spend,
            "net_cash": net,
            "fert_actions": acc[seat]["fert"],
            "plant_wheat": acc[seat]["plant_wheat"],
            "wheat_tile_steps": acc[seat]["wheat_tile_steps"],
            "harvest_actions": acc[seat]["harvest_actions"],
            "shed_end": last["shed_obs"].get(ITEM, 0),
            "balance": acc[seat]["harvest"] + bought - acc[seat]["fed"]
                       - acc[seat]["discard"] - sold - last["shed_obs"].get(ITEM, 0),
        }
    return out


def show(rows):
    keys = ("harvested", "bought", "fed", "discarded", "sold", "sell_revenue",
            "buy_spend", "net_cash")
    if rows and "cand_items" in rows[0]:
        print("\nper-item cash (net of that item's own buys), aggregated:")
        print(f"{'item':12s} {'cand sold':>10} {'base sold':>10} {'d sold':>8} "
              f"{'cand net':>10} {'base net':>10} {'d net':>10}")
        for it in lockstep.PRODUCTS:
            c = sum(r["cand_items"][it]["net_cash"] for r in rows)
            b = sum(r["base_items"][it]["net_cash"] for r in rows)
            cs = sum(r["cand_items"][it]["sold"] for r in rows)
            bs = sum(r["base_items"][it]["sold"] for r in rows)
            cb = sum(r["cand_items"][it]["bought"] for r in rows)
            bb = sum(r["base_items"][it]["bought"] for r in rows)
            print(f"{it:12s} {cs:10d} {bs:10d} {cs-bs:+8d} {c:10,.0f} {b:10,.0f} {c-b:+10,.0f}"
                  f"   (bought {cb} vs {bb})")
    print(f"{'seed':>5} {'who':>5} " + " ".join(f"{k:>10}" for k in keys))
    for r in rows:
        for who in ("cand", "base"):
            d = r[who]
            print(f"{r['seed']:5d} {who:>5} " + " ".join(f"{d[k]:10.0f}" for k in keys))
        print(f"      delta {r['cand']['harvested']-r['base']['harvested']:+d} harvested, "
              f"{r['cand']['sold']-r['base']['sold']:+d} sold, "
              f"{r['cand']['discarded']-r['base']['discarded']:+d} discarded, "
              f"{r['cand']['sell_revenue']-r['base']['sell_revenue']:+,.0f} sell revenue, "
              f"{r['cand']['net_cash']-r['base']['net_cash']:+,.0f} net (wallet {r['delta']:+,.0f})")


def _job(arg):
    seeds, cand, base = arg
    return [flow(s, cand, base) for s in seeds]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--cand", default=FRONTIER)
    ap.add_argument("--base", default=CHAMPION)
    ap.add_argument("--seeds", default="9005,9009")
    ap.add_argument("--procs", type=int, default=10)
    ap.add_argument("--out", default=None)
    a = ap.parse_args()
    seeds = []
    for part in a.seeds.split(","):
        lo, _, hi = part.partition("-")
        seeds.extend(range(int(lo), int(hi) + 1) if hi else [int(lo)])
    if len(seeds) <= 6:
        rows = [flow(s, a.cand, a.base) for s in seeds]
    else:
        chunks = [seeds[i::a.procs] for i in range(a.procs)]
        with mp.Pool(a.procs) as pool:
            res = pool.map(_job, [(c, a.cand, a.base) for c in chunks if c])
        rows = sorted((r for sub in res for r in sub), key=lambda r: r["seed"])
    show(rows)
    if len(rows) > 3:
        n = len(rows)
        tot = lambda k, who: sum(r[who][k] for r in rows)
        print(f"\naggregate over {n} towns (cand vs base):")
        for k in ("harvested", "bought", "fed", "discarded", "sold", "sell_revenue",
                  "buy_spend", "net_cash", "fert_actions", "plant_wheat",
                  "wheat_tile_steps", "harvest_actions"):
            c, b = tot(k, "cand"), tot(k, "base")
            print(f"   {k:10s} {c:10,.0f} vs {b:10,.0f}  ({c-b:+,.0f})")
        print(f"   wallet     {sum(r['final'][0] for r in rows):10,.0f} vs "
              f"{sum(r['final'][1] for r in rows):10,.0f}  "
              f"({sum(r['delta'] for r in rows):+,.0f})")
    if a.out:
        Path(a.out).write_text(json.dumps(rows, indent=1))
        print("wrote", a.out)
    return 0


if __name__ == "__main__":
    sys.exit(main())
