#!/usr/bin/env python
"""Wool lot timing: did the units EXIST earlier on the frontier's side, or were they
merely OFFERED earlier?

Per step, for each seat (each seat reads its own private state, so hands are visible):

  on_sheep   wool standing on that seat's sheep tiles (public, needs a HARVEST to move)
  in_shed    wool in the shed at MARKET time (the unit actions of the step are replayed
             on a copy with the engine's own `_apply_unit_action`, as in race_trace.py)
  in_hands   wool carried by the farmer/hands (visible in `private.inventories`; the
             end-of-day drop moves it into the shed)
  offered    wool units requested by this step's SELL orders
  executed   wool units the replica says were actually sold (stock-capped)

Aggregated per day and split at day 23/24 (the price collapse), this separates
  (a) production/collection: their pool (shed + hands, i.e. sellable now) is larger early
  (b) offer sequencing: pools match, offers differ
  (c) interaction: offers differ only because a plan change also moved production.

Usage: .venv/bin/python scripts/wool_lot_timing.py --seeds 9009,9005
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

ITEM = "WOOL"
FRONTIER = str(ROOT / "data" / "cand" / "the-2945-farm-96-vs-the-top-10-public-bots" / "main.py")
CHAMPION = str(ROOT / "data" / "tapeopt" / "rgcs" / "main.py")


def _load(path):
    ns = {"__name__": "wool_mod"}
    exec(compile(Path(path).read_text(), str(path), "exec"), ns)
    return ns["agent"]


def run(seed, cand_path, base_path):
    from kaggle_environments import make
    from kaggle_environments.envs.kaggriculture import kaggriculture as eng

    agents = [_load(cand_path), _load(base_path)]
    per = {0: {}, 1: {}}

    def wrap(agent, seat):
        def fn(obs, *a, **k):
            act = agent(obs) or {}
            board = len(obs.farms[seat]["tiles"])
            day = int(obs.day)
            priv = copy.deepcopy(obs.private)
            farm = copy.deepcopy(obs.farms[seat])
            units = [act.get("farmer") or ["PASS"]] + list(act.get("hands") or [])
            for idx, ua in enumerate(units):
                eng._apply_unit_action(farm, priv, idx, ua, board, day, 24, 100)
            on_sheep = 0
            for row in obs.farms[seat]["tiles"]:
                for t in row:
                    if isinstance(t, dict) and t.get("animal") == "SHEEP":
                        on_sheep += max(0, int(t.get("yield_units", 0)))
            market = [list(o) for o in (act.get("market") or [])]
            offered = sum(max(0, int(o[2])) for o in market
                          if isinstance(o, list) and len(o) >= 3 and o[0] == "SELL"
                          and o[1] == ITEM)
            shed = max(0, int(priv["shed"].get(ITEM, 0)))
            hands = sum(max(0, int((inv or {}).get(ITEM, 0)))
                        for inv in priv["inventories"])
            inv_now = {k: int(v) for k, v in dict(obs.market.inventory).items()}
            executed = 0
            if offered:
                orders = [o for o in market if isinstance(o, list) and len(o) >= 3
                          and o[0] == "SELL" and o[1] == ITEM]
                r = lockstep.clear(orders, [], inv_now, (priv["shed"], {}))
                executed = r["units"][0]
            per[seat][int(obs["step"])] = {"on_sheep": on_sheep, "in_shed": shed,
                                           "in_hands": hands, "offered": offered,
                                           "executed": executed}
            return act
        return fn

    env = make("kaggriculture", configuration={"episodeSteps": 720, "seed": seed})
    env.run([wrap(agents[0], 0), wrap(agents[1], 1)])
    final = [float(env.steps[-1][i]["reward"] or 0) for i in (0, 1)]
    out = {"seed": seed, "final": final, "delta": final[0] - final[1]}
    for seat, name in ((0, "cand"), (1, "base")):
        rec = per[seat]
        agg = {"early": {}, "late": {}, "days": []}
        for window, lo, hi in (("early", 0, 24), ("late", 24, 30)):
            steps = [s for s in rec if lo <= s // 24 < hi]
            agg[window] = {
                "executed": sum(rec[s]["executed"] for s in steps),
                "offered": sum(rec[s]["offered"] for s in steps),
                "pool_max": max((rec[s]["in_shed"] + rec[s]["in_hands"] for s in steps),
                                default=0),
                "pool_mean": (sum(rec[s]["in_shed"] + rec[s]["in_hands"] for s in steps)
                              / max(1, len(steps))),
                "shed_mean": sum(rec[s]["in_shed"] for s in steps) / max(1, len(steps)),
                "hands_mean": sum(rec[s]["in_hands"] for s in steps) / max(1, len(steps)),
                "on_sheep_mean": sum(rec[s]["on_sheep"] for s in steps) / max(1, len(steps)),
            }
            if window == "early":
                agg["days"] = [{
                    "day": d,
                    "executed": sum(rec[s]["executed"] for s in rec if s // 24 == d),
                    "offered": sum(rec[s]["offered"] for s in rec if s // 24 == d),
                    "pool_end": max((rec[s]["in_shed"] + rec[s]["in_hands"]
                                     for s in rec if s // 24 == d), default=0),
                    "on_sheep_end": max((rec[s]["on_sheep"] for s in rec if s // 24 == d),
                                        default=0),
                } for d in range(24)]
        out[name] = agg
    return out


def _job(arg):
    seeds, c, b = arg
    return [run(s, c, b) for s in seeds]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--cand", default=FRONTIER)
    ap.add_argument("--base", default=CHAMPION)
    ap.add_argument("--seeds", default="9009,9005")
    ap.add_argument("--procs", type=int, default=10)
    ap.add_argument("--daily", action="store_true")
    ap.add_argument("--out", default=None)
    a = ap.parse_args()
    seeds = []
    for part in a.seeds.split(","):
        lo, _, hi = part.partition("-")
        seeds.extend(range(int(lo), int(hi) + 1) if hi else [int(lo)])
    if len(seeds) <= 4:
        rows = [run(s, a.cand, a.base) for s in seeds]
    else:
        chunks = [seeds[i::a.procs] for i in range(a.procs)]
        with mp.Pool(a.procs) as pool:
            res = pool.map(_job, [(c, a.cand, a.base) for c in chunks if c])
        rows = sorted((r for sub in res for r in sub), key=lambda r: r["seed"])

    keys = ("executed", "offered", "pool_max", "pool_mean", "shed_mean", "hands_mean",
            "on_sheep_mean")
    for r in rows:
        print(f"=== seed {r['seed']}  delta {r['delta']:+,.0f}")
        for w in ("early", "late"):
            for who in ("cand", "base"):
                d = r[who][w]
                print(f"   {w:5s} {who:4s} " + " ".join(f"{k}={d[k]:8.2f}" for k in keys))
            dc, db = r["cand"][w], r["base"][w]
            print(f"   {w:5s} delta " + " ".join(f"{k}={dc[k]-db[k]:+8.2f}" for k in keys))
        if a.daily:
            print("   day  exec(c/b)  offer(c/b)  pool_end(c/b)  on_sheep_end(c/b)")
            for d in r["cand"]["days"]:
                e = r["base"]["days"][d["day"]]
                print(f"   {d['day']:3d}  {d['executed']:3d}/{e['executed']:<3d}    "
                      f"{d['offered']:4d}/{e['offered']:<4d}   {d['pool_end']:3d}/{e['pool_end']:<3d}"
                      f"        {d['on_sheep_end']:3d}/{e['on_sheep_end']:<3d}")
    if len(rows) > 2:
        print(f"\naggregate over {len(rows)} towns (cand vs base):")
        for w in ("early", "late"):
            print(f"  window {w}:")
            for k in keys:
                c = sum(r["cand"][w][k] for r in rows)
                b = sum(r["base"][w][k] for r in rows)
                print(f"    {k:14s} {c:10,.1f} vs {b:10,.1f}  ({c-b:+,.1f})")
        print(f"  wallet {sum(r['final'][0] for r in rows):,.0f} vs "
              f"{sum(r['final'][1] for r in rows):,.0f} "
              f"({sum(r['delta'] for r in rows):+,.0f})")
    if a.out:
        Path(a.out).write_text(json.dumps(rows, indent=1))
        print("wrote", a.out)
    return 0


if __name__ == "__main__":
    sys.exit(main())
