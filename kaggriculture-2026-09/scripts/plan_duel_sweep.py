#!/usr/bin/env python
"""Screen plan_v0 parameter sets against a REAL opponent, not the starter.

Why this exists: the whole plan_v0 parameter map was tuned with plan_sweep.py,
whose opponent is the built-in `starter`.  Against the starter the market is
uncontested, so a "hold when the price is crushed" selling rule looks free.  Against
the actual champion (a tape that dumps goods and crashes prices) the same rule stops
all selling and the planner starves: measured 0 wins in 400 games, delta -113,479
(t=-87.9), wallet 26,214 vs 139,693.

This tool builds each parameter set in-process, plays it against the reference agent
with the seats swapped on every seed (paired, town-controlled), and reports the
paired delta, t, win/loss, wallet levels and the mechanistic counters -- so the
tuning signal comes from the opponent that actually decides the ladder.

Usage:
  python scripts/plan_duel_sweep.py --seeds 9000-9039 --configs data/plan-opp-configs.json
  python scripts/plan_duel_sweep.py --seeds 9000-9199 --configs ... --procs 10
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


def _load(path):
    ns = {"__name__": "duel_mod"}
    exec(compile(Path(path).read_text(), str(path), "exec"), ns)
    return ns["agent"]


def _counters(env, seat):
    c = collections.Counter()
    for t in range(len(env.steps)):
        a = env.steps[t][seat].get("action") or {}
        for cmd in [a.get("farmer") or []] + list(a.get("hands") or []):
            if isinstance(cmd, list) and cmd:
                v = cmd[0]
                c["MOVE" if v in MOVE else v] += 1
    return dict(c)


def _job(arg):
    name, params, seeds, opp_path = arg
    import plan_v0
    from kaggle_environments import make
    opp = _load(opp_path)
    out = []
    for seed in seeds:
        for cand_seat in (0, 1):
            planner = plan_v0.PlanV0(params=params)

            def cand(obs, configuration=None, _p=planner):
                return _p.act(obs)

            agents = [cand, opp] if cand_seat == 0 else [opp, cand]
            env = make("kaggriculture", configuration={"episodeSteps": 720, "seed": seed})
            env.run(agents)
            f = env.steps[-1]
            # reference profile: coverage of the daily watering demand, and the
            # farm/herd census at day 10 (the reference agent runs ~52 crops/15 head)
            cov_num = cov_den = 0
            census = {}
            for t in range(len(env.steps)):
                o = env.steps[t][cand_seat].get("observation")
                if not o:
                    continue
                day, hour = t // 24, t % 24
                if 10 <= day <= 24 and hour == 0:
                    pl = sum(1 for row in o["farms"][cand_seat]["tiles"] for c in row
                             if isinstance(c, dict) and c.get("kind") == "PLANT")
                    cov_den += pl
                if day == 10 and hour == 0:
                    census = {
                        "plants10": sum(1 for row in o["farms"][cand_seat]["tiles"] for c in row
                                        if isinstance(c, dict) and c.get("kind") == "PLANT"),
                        "animals10": sum(1 for row in o["farms"][cand_seat]["tiles"] for c in row
                                         if isinstance(c, dict) and c.get("animal")),
                    }
                a = env.steps[t][cand_seat].get("action") or {}
                for cmd in [a.get("farmer") or []] + list(a.get("hands") or []):
                    if isinstance(cmd, list) and cmd and cmd[0] == "WATER":
                        cov_num += 1
            out.append({"seed": seed, "cand_seat": cand_seat, "cov": cov_num / max(1, cov_den),
                        **census,
                        "cand": float(f[cand_seat]["reward"] or 0),
                        "opp": float(f[1 - cand_seat]["reward"] or 0),
                        "status": str(f[cand_seat]["status"]),
                        "cm": _counters(env, cand_seat)})
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


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--seeds", default="9000-9039")
    ap.add_argument("--configs", required=True, help="JSON [[name, {params}], ...]")
    ap.add_argument("--opp", default=str(ROOT / "data" / "tapeopt" / "rgcs" / "main.py"))
    ap.add_argument("--procs", type=int, default=10)
    ap.add_argument("--out", default=None)
    args = ap.parse_args()

    seeds = parse_seeds(args.seeds)
    cfgs = json.loads(Path(args.configs).read_text())
    jobs = [(name, params, ch, args.opp) for name, params in cfgs
            for ch in chunks(seeds, args.procs)]
    t0 = time.time()
    with mp.Pool(args.procs) as pool:
        raw = pool.map(_job, jobs)
    by = collections.defaultdict(list)
    for name, rows in raw:
        by[name].extend(rows)
    print(f"[{len(cfgs)} configs x {len(seeds)} seeds (paired) in {time.time()-t0:.0f}s]",
          file=sys.stderr)

    table = []
    for name, rows in by.items():
        per_seed = collections.defaultdict(list)
        for r in rows:
            per_seed[r["seed"]].append(r)
        diffs = [statistics.mean(x["cand"] - x["opp"] for x in rs) for rs in per_seed.values()]
        mean = statistics.mean(diffs) if diffs else 0
        var = statistics.variance(diffs) if len(diffs) > 1 else 0
        se = (var / max(1, len(diffs))) ** 0.5
        cm = collections.Counter()
        for r in rows:
            cm.update(r["cm"])
        n = len(rows)
        table.append({
            "name": name, "delta": mean, "t": (mean / se if se else 0.0),
            "wins": sum(1 for d in diffs if d > 0), "losses": sum(1 for d in diffs if d < 0),
            "cand_wallet": statistics.mean(r["cand"] for r in rows),
            "opp_wallet": statistics.mean(r["opp"] for r in rows),
            "water": cm["WATER"] / n, "harvest": cm["HARVEST"] / n,
            "feed": cm["FEED"] / n, "care": cm["CARE"] / n,
            "collect": cm["COLLECT_FERTILIZER"] / n, "plant": cm["PLANT"] / n,
            "sell": cm["SELL"] / n,
            "plant": cm["PLANT"] / n, "sell": sum(v for k, v in cm.items() if k == "SELL"),
            "idle": 100 * cm["PASS"] / max(1, sum(cm.values())),
            "cover": statistics.mean(r.get("cov", 0) for r in rows),
            "plants10": statistics.mean(r.get("plants10", 0) for r in rows),
            "animals10": statistics.mean(r.get("animals10", 0) for r in rows),
            "err": sum(1 for r in rows if r["status"] != "DONE"),
        })
    table.sort(key=lambda r: -r["delta"])
    print(f"{'config':26s} {'delta':>10s} {'t':>8s} {'W/L':>9s} {'cand$':>9s} {'opp$':>9s} "
          f"{'water':>6s} {'harv':>6s} {'feed':>5s} {'care':>5s} {'coll':>5s} {'plant':>5s} "
          f"{'idle%':>6s} {'pl10':>5s} {'an10':>5s} {'err':>3s}")
    for r in table:
        print(f"{r['name']:26s} {r['delta']:10,.0f} {r['t']:8.2f} "
              f"{str(r['wins'])+'/'+str(r['losses']):>9s} {r['cand_wallet']:9,.0f} "
              f"{r['opp_wallet']:9,.0f} {r['water']:6.0f} {r['harvest']:6.0f} "
              f"{r['feed']:5.0f} {r['care']:5.0f} {r['collect']:5.0f} {r['plant']:5.0f} "
              f"{r['idle']:6.1f} {r['plants10']:5.1f} {r['animals10']:5.1f} {r['err']:3d}")
    if args.out:
        Path(args.out).write_text(json.dumps({"seeds": [min(seeds), max(seeds)], "table": table},
                                             indent=1))
        print(f"wrote {args.out}")


if __name__ == "__main__":
    main()
