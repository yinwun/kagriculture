#!/usr/bin/env python
"""Extract the AGRONOMIC PLAN (not the keystrokes) from a tape route.

The tape's value is its plan: which tile grows which crop, planted on which day,
harvested on which day, when animals are placed, when land is bought, and the
market schedule (hires, seeds, animals, sells).  The walking is the part we want
to replace with our own closed-loop scheduler -- the measurements say the tape
spends 8-10% of its unit-turns idling (rank 1: 0.8%) and the plan already
collects 377 fertilizer that it then dumps at 1 coin.

Usage:
  python scripts/extract_schedule.py --route 105 --out data/tapeopt/sched105.json
  python scripts/extract_schedule.py --all --out data/tapeopt/sched_all.json
"""
import argparse
import collections
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))
from tape_sim2 import load_blob, simulate, cmd_of, COMMIT, MOVES  # noqa: E402


def plan_of_route(tape, nhand):
    """Per-unit day-aware trajectories -> plant/harvest/animal events."""
    traj = simulate(tape, nhand)
    plants, harvests, places, builds, collects = [], [], [], [], []
    for k, rows in traj.items():
        for step, pos, c in rows:
            if not (isinstance(c, list) and c and pos is not None):
                continue
            day = step // 24
            op = c[0]
            if op == "PLANT":
                plants.append([pos[0], pos[1], day, c[1] if len(c) > 1 else None, k])
            elif op == "HARVEST":
                harvests.append([pos[0], pos[1], day, k])
            elif op == "PLACE":
                places.append([pos[0], pos[1], day, c[1] if len(c) > 1 else None])
            elif op in ("BUILD_COOP", "BUILD_PASTURE"):
                builds.append([pos[0], pos[1], day, op])
            elif op == "COLLECT_FERTILIZER":
                collects.append([pos[0], pos[1], day])
    # market schedule: hires / seeds / animals / sells, with the order list per step
    market = []
    sells = collections.Counter()
    for step, a in enumerate(tape):
        if not isinstance(a, dict):
            continue
        orders = [o for o in (a.get("market") or []) if isinstance(o, list) and o]
        for o in orders:
            if o[0] == "SELL" and len(o) >= 3:
                sells[o[1]] += int(o[2] or 0)
        if orders:
            market.append([step, orders])
    return {"plants": sorted(plants), "harvests": sorted(harvests),
            "places": sorted(places), "builds": sorted(builds),
            "collects": sorted(collects), "market": market,
            "sell_totals": dict(sells)}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--route", type=int, default=105)
    ap.add_argument("--all", action="store_true")
    ap.add_argument("--out", default="data/tapeopt/sched.json")
    ap.add_argument("--tape", default=None)
    args = ap.parse_args()
    if args.tape:
        src = Path(args.tape).read_text()
        import base64, re, zlib
        blob = re.search(r"b85decode\('([^']+)'\)", src).group(1)
        data = json.loads(zlib.decompress(base64.b85decode(blob)))
    else:
        src, m, data = load_blob()
    routes = data["routes"]
    acts = data["actions"]
    rids = sorted(int(k) for k in routes) if args.all else [args.route]
    out = {}
    for rid in rids:
        tape = [acts[i] for i in routes[str(rid)]]
        nhand = max(len(a.get("hands") or []) for a in tape if isinstance(a, dict))
        out[str(rid)] = plan_of_route(tape, nhand)
        p = out[str(rid)]
        by_crop = collections.Counter(x[3] for x in p["plants"] if len(x) > 3)
        print(f"route {rid:>3}: plants {len(p['plants'])} {dict(by_crop)} | "
              f"harvests {len(p['harvests'])} | places {len(p['places'])} | "
              f"collects {len(p['collects'])} | market steps {len(p['market'])}")
    Path(ROOT / args.out).write_text(json.dumps(out))
    print(f"wrote {args.out}")


if __name__ == "__main__":
    main()
