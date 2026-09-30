#!/usr/bin/env python
"""Group towns by the route the champion's router actually plays at step 300.

The router picks its tape at step 144 from the first two unlocked shops of the day-6
tuple.  That tuple CANNOT be captured with a dummy agent: the shop draw takes its
randomness from the same RNG stream as end-of-day weed spawning, whose consumption
depends on how many empty tiles the agents leave, so the draw depends on the farm
play.  The only valid source is a real game.

Usage: .venv/bin/python scripts/route_groups.py --seeds 9000-9029,9100-9129
"""
from __future__ import annotations

import argparse
import collections
import json
import multiprocessing as mp
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
CHAMPION = str(ROOT / "data" / "tapeopt" / "rgcs" / "main.py")


def one(seed):
    from kaggle_environments import make
    ns = {"__name__": "rg"}
    exec(compile(Path(CHAMPION).read_text(), CHAMPION, "exec"), ns)
    box = {}

    def wrap(obs):
        if int(obs["step"]) == 300:
            box["route"] = ns["_IMPL"].chassis.players.get(0, {}).get("route")
            box["shops"] = list(obs.town["unlocked_shops"])
        return ns["agent"](obs)

    env = make("kaggriculture", configuration={"episodeSteps": 320, "seed": seed})
    env.run([wrap, ns["agent"]])
    return {"seed": seed, "route": box.get("route"), "shops": box.get("shops")}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--seeds", default="9000-9029,9100-9129")
    ap.add_argument("--procs", type=int, default=10)
    ap.add_argument("--out", default=str(ROOT / "data" / "route" / "groups.json"))
    a = ap.parse_args()
    seeds = []
    for part in a.seeds.split(","):
        lo, _, hi = part.partition("-")
        seeds.extend(range(int(lo), int(hi) + 1) if hi else [int(lo)])
    with mp.Pool(a.procs) as pool:
        rows = pool.map(one, seeds)
    groups = collections.defaultdict(list)
    for r in rows:
        groups[r["route"]].append(r["seed"])
    print(f"{len(rows)} towns, {len(groups)} distinct routes actually played")
    for route, ss in sorted(groups.items(), key=lambda kv: -len(kv[1])):
        print(f"  route {route}: {len(ss):2d} towns (IS {sum(1 for s in ss if s < 9100)}, "
              f"OOS {sum(1 for s in ss if s >= 9100)})  {sorted(ss)}")
    Path(a.out).write_text(json.dumps({str(k): v for k, v in groups.items()}, indent=1))
    print("wrote", a.out)
    return 0


if __name__ == "__main__":
    sys.exit(main())
