#!/usr/bin/env python
"""Audit where the champion's idle worker-turns actually are.

The naive idle-fill layer (work only on the tile the unit already stands on) fires
almost never, so before building a dispatcher we need the shape of the slack:

  * how many units are idle per step, and by what mechanism (the tape's own PASS
    vs the padding that `_hand_align` adds for hands the tape never commands),
  * what the idle units are standing on,
  * how much real work is pending on the farm at that moment and how far away it is
    (Manhattan distance to the nearest needed tile).

Usage:
  python scripts/idle_audit.py --seeds 9000-9004 --agent data/tapeopt/rgcs/main.py
"""
import argparse
import collections
import json
import statistics
from pathlib import Path

from kaggle_environments import make

CROPS = None


def load_agent(path):
    ns = {"__name__": "idle_audit"}
    exec(compile(Path(path).read_text(), str(path), "exec"), ns)
    return ns


def pending_tasks(obs, p, day):
    """Tiles that would repay a visit right now: [(kind, (r,c))]."""
    from kaggle_environments.envs.kaggriculture.kaggriculture import CROPS as C
    out = []
    tiles = obs["farms"][p]["tiles"]
    for r, row in enumerate(tiles):
        for c, cell in enumerate(row):
            if not isinstance(cell, dict):
                continue
            kind = cell.get("kind")
            if kind == "PLANT":
                cd = C.get(cell.get("crop"))
                if not cd:
                    continue
                age = day - cell.get("planted_day", day)
                units = cell.get("yield_units", 0)
                if not cell.get("watered_today"):
                    if cell.get("consecutive_unwatered", 0) >= 1:
                        out.append(("WATER_RISK", (r, c)))
                    elif (not cd["ongoing"] and units < cd["max_yield"]
                          and (cd["max_yield_day"] + 1) // 2 <= age <= cd["max_yield_day"]):
                        out.append(("WATER_WIN", (r, c)))
                if units > 0 and (age >= cd["first_yield_day"] if cd["ongoing"]
                                  else age >= cd["max_yield_day"] or units >= cd["max_yield"]):
                    out.append(("HARVEST", (r, c)))
            elif kind in ("PASTURE", "COOP") and cell.get("animal"):
                if not cell.get("fed_today"):
                    out.append(("FEED", (r, c)))
                elif not cell.get("cared_today"):
                    out.append(("CARE", (r, c)))
                if cell.get("fertilizer_available"):
                    out.append(("FERT", (r, c)))
            elif kind == "WEED":
                out.append(("DIG", (r, c)))
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--agent", default="data/tapeopt/rgcs/main.py")
    ap.add_argument("--opp", default="data/tapeopt/rgcs/main.py")
    ap.add_argument("--seeds", default="9000-9004")
    args = ap.parse_args()
    seeds = []
    for part in args.seeds.split(","):
        if "-" in part:
            a, b = part.split("-")
            seeds.extend(range(int(a), int(b) + 1))
        else:
            seeds.append(int(part))

    cand = load_agent(args.agent)["agent"]
    opp = load_agent(args.opp)["agent"]
    idle_by_mechanism = collections.Counter()
    idle_tile = collections.Counter()
    dists = []
    pending_when_idle = []
    per_step_idle = []
    for seed in seeds:
        env = make("kaggriculture", configuration={"episodeSteps": 720, "seed": seed})
        env.run([cand, opp])
        for t in range(len(env.steps)):
            e = env.steps[t][0]
            obs = e.get("observation")
            a = e.get("action") or {}
            if not obs:
                continue
            day = obs.get("day", t // 24)
            farmer = a.get("farmer") or ["PASS"]
            hands = list(a.get("hands") or [])
            pos = [obs["farms"][0]["farmer"]] + [list(x) for x in obs["farms"][0]["hands"]]
            idle = 0
            tasks = pending_tasks(obs, 0, day)
            for i, cmd in enumerate([farmer] + hands):
                if not (isinstance(cmd, list) and cmd and cmd[0] == "PASS"):
                    continue
                idle += 1
                p = pos[i] if i < len(pos) else None
                tile = "?"
                if isinstance(p, (list, tuple)) and len(p) >= 2:
                    cell = obs["farms"][0]["tiles"][p[1]][p[0]]
                    tile = (cell.get("kind") if isinstance(cell, dict)
                            else ("EMPTY" if cell is None else str(cell)))
                idle_tile[tile] += 1
                if tasks and isinstance(p, (list, tuple)):
                    d = min(abs(p[0] - q[0]) + abs(p[1] - q[1]) for _, q in tasks)
                    dists.append(d)
            pending_when_idle.append(len(tasks))
            per_step_idle.append(idle)
        print(f"seed {seed}: done", flush=True)

    n = len(per_step_idle)
    print(f"\nsteps audited: {n}")
    print(f"idle units per step: mean {statistics.mean(per_step_idle):.2f} "
          f"median {statistics.median(per_step_idle)} max {max(per_step_idle)}")
    print(f"pending tasks per step: mean {statistics.mean(pending_when_idle):.2f} "
          f"median {statistics.median(pending_when_idle)}")
    print(f"idle-unit tiles: {dict(idle_tile.most_common(8))}")
    if dists:
        dists.sort()
        q = lambda f: dists[min(len(dists) - 1, int(f * len(dists)))]
        print(f"distance from an idle unit to the nearest pending task: "
              f"p25={q(.25)} median={q(.5)} p75={q(.75)} p90={q(.9)}")
    Path("data/idle_audit.json").write_text(json.dumps({
        "idle_per_step_mean": statistics.mean(per_step_idle),
        "pending_mean": statistics.mean(pending_when_idle),
        "idle_tiles": dict(idle_tile),
        "dist_median": statistics.median(dists) if dists else None,
        "steps": n}, indent=1))
    print("wrote data/idle_audit.json")


if __name__ == "__main__":
    main()
