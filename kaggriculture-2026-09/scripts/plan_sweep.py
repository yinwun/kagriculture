#!/usr/bin/env python
"""Sweep plan_v0's policy knobs and report both the score and the L1 mechanics.

Structure first, parameters second: this tool is for the second layer (schedules,
thresholds, batch sizes) once the needs-driven scheduler runs.  It reports the
L1 profile next to the reward so a knob's effect is visible, not just its score:
a config that raises the reward while lowering coverage is a lucky town, not an
improvement.

Usage:
  python scripts/plan_sweep.py --seeds 900-911 --procs 10 --out data/plan-sweep-1.json
  python scripts/plan_sweep.py --configs data/plan-configs.json --seeds 900-909
"""
import argparse
import collections
import json
import multiprocessing as mp
import statistics
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))

MOVE = {"NORTH", "SOUTH", "EAST", "WEST"}


def _play(arg):
    name, params, seeds, opp = arg
    from kaggle_environments import make
    import plan_v0
    out = []
    for seed in seeds:
        planner = plan_v0.PlanV0(params=params)

        def seat0(obs, configuration=None):
            return planner.act(obs)

        env = make("kaggriculture", configuration={"episodeSteps": 720, "seed": seed})
        env.run([seat0, opp])
        steps = env.steps
        cov = collections.defaultdict(lambda: [0, 0, 0, 0])
        verbs = collections.Counter()
        for t in range(len(steps)):
            o = steps[t][0].get("observation")
            a = steps[t][0].get("action") or {}
            if not o:
                continue
            day, hour = t // 24, t % 24
            if hour == 0:
                cov[day][0] = sum(1 for row in o["farms"][0]["tiles"] for c in row
                                  if isinstance(c, dict) and c.get("kind") == "PLANT")
                cov[day][1] = sum(1 for row in o["farms"][0]["tiles"] for c in row
                                  if isinstance(c, dict) and c.get("animal"))
            for cmd in [a.get("farmer") or []] + list(a.get("hands") or []):
                if not (isinstance(cmd, list) and cmd):
                    continue
                v = cmd[0]
                verbs["MOVE" if v in MOVE else v] += 1
                if v == "WATER":
                    cov[day][2] += 1
                elif v in ("FEED", "CARE", "COLLECT_FERTILIZER"):
                    cov[day][3] += 1
        mid = range(10, 26)
        waters = sum(cov[d][2] for d in mid)
        plants = sum(cov[d][0] for d in mid)
        out.append({
            "seed": seed,
            "reward": float(steps[-1][0]["reward"] or 0),
            "status": str(steps[-1][0]["status"]),
            "cover": waters / plants if plants else 0.0,
            "plants_d10": cov[10][0], "animals_d10": cov[10][1],
            "plants_d15": cov[15][0], "animals_d15": cov[15][1],
            "idle": verbs["PASS"] / max(1, sum(verbs.values())),
            "move_share": verbs["MOVE"] / max(1, sum(verbs.values())),
            "water": verbs["WATER"], "harvest": verbs["HARVEST"],
            "feed": verbs["FEED"], "collect": verbs["COLLECT_FERTILIZER"],
        })
    return name, out


def chunks(seq, n):
    step = max(1, -(-len(seq) // max(1, n)))
    return [seq[i:i + step] for i in range(0, len(seq), step)]


def parse_seeds(spec):
    out = []
    for part in spec.split(","):
        if "-" in part:
            a, b = part.split("-")
            out.extend(range(int(a), int(b) + 1))
        else:
            out.append(int(part))
    return out


def default_configs():
    import plan_v0
    cfgs = [("baseline", {})]
    grid = {
        "hire_mult": [1.4, 2.6],
        "claim_slack": [0, 5],
        "age_div": [4, 16],
        "feed_days": [2, 5],
        "sell_batch": [4, 16],
        "plant_scale": [0.85, 1.2],
        "animal_scale": [0.8, 1.3],
        "pen_ahead": [0, 3],
        "land_first_day": [5, 8],
        "hire_cap": [9, 14],
    }
    for k, vals in grid.items():
        for v in vals:
            cfgs.append((f"{k}={v}", {k: v}))
    return cfgs


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--seeds", default="900-911")
    ap.add_argument("--procs", type=int, default=10)
    ap.add_argument("--opponent", default="starter")
    ap.add_argument("--out", default="data/plan-sweep.json")
    ap.add_argument("--configs", default=None, help="JSON: [[name, {params}], ...]")
    args = ap.parse_args()

    seeds = parse_seeds(args.seeds)
    if args.configs:
        cfgs = [(n, p) for n, p in json.loads(Path(args.configs).read_text())]
    else:
        cfgs = default_configs()
    jobs = [(name, params, ch, args.opponent) for name, params in cfgs
            for ch in chunks(seeds, 2)]
    t0 = time.time()
    with mp.Pool(args.procs) as pool:
        raw = pool.map(_play, jobs)
    by_name = collections.defaultdict(list)
    for name, rows in raw:
        by_name[name].extend(rows)
    print(f"[{len(cfgs)} configs x {len(seeds)} seeds in {time.time()-t0:.0f}s]",
          file=sys.stderr)

    table = []
    for name, rows in by_name.items():
        table.append({
            "name": name,
            "reward": statistics.mean(r["reward"] for r in rows),
            "cover": statistics.mean(r["cover"] for r in rows),
            "idle": statistics.mean(r["idle"] for r in rows) * 100,
            "move": statistics.mean(r["move_share"] for r in rows) * 100,
            "p10": statistics.mean(r["plants_d10"] for r in rows),
            "a10": statistics.mean(r["animals_d10"] for r in rows),
            "p15": statistics.mean(r["plants_d15"] for r in rows),
            "a15": statistics.mean(r["animals_d15"] for r in rows),
            "water": statistics.mean(r["water"] for r in rows),
            "moves_per_action": (statistics.mean(r["move_share"] for r in rows)
                                 / max(1e-9, 1 - statistics.mean(r["idle"] for r in rows)
                                       - statistics.mean(r["move_share"] for r in rows))),
            "harvest": statistics.mean(r["harvest"] for r in rows),
            "err": sum(1 for r in rows if r["status"] != "DONE"),
            # an agent exception is swallowed by the engine, which then plays PASS
            # every step: reward == starting money and total idleness.  Flag it,
            # because such a config looks "stable" and scores exactly 3000.
            "broken": sum(1 for r in rows if r["reward"] <= 5000 and r["idle"] > 0.3),
        })
    table.sort(key=lambda r: -r["reward"])
    print(f"{'config':18s} {'reward':>9s} {'cover':>6s} {'idle%':>6s} {'move%':>6s} "
          f"{'plants10':>8s} {'anim10':>6s} {'plants15':>8s} {'water':>6s} {'harv':>6s} "
          f"{'mv/act':>6s} {'err':>3s} {'bad':>3s}")
    for r in table:
        print(f"{r['name']:18s} {r['reward']:9,.0f} {r['cover']:6.2f} {r['idle']:6.1f} "
              f"{r['move']:6.1f} {r['p10']:8.1f} {r['a10']:6.1f} {r['p15']:8.1f} "
              f"{r['water']:6.0f} {r['harvest']:6.0f} {r['moves_per_action']:6.2f} "
              f"{r['err']:3d} {r['broken']:3d}")
    Path(args.out).write_text(json.dumps({"seeds": seeds, "table": table}, indent=1))
    print(f"wrote {args.out}")


if __name__ == "__main__":
    main()
