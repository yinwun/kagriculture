#!/usr/bin/env python
"""Re-tune the route map per shop-demand cluster, measured against the CHAMPION.

Why: the champion's per-shop-class route table (`_R108_SHOP_ROUTES`) was not derived
against a strong opponent, and the existing bandit data (41 routes x 120 towns,
measured against the default agent) hints it is off -- e.g. in the "wool only" cluster
the current pick scores -15,836 while route 126 scores +2,681.  This tool measures the
candidate routes *against the champion* on the towns of each cluster, then emits a new
map so it can be verified with a paired duel on Panel A.

Cluster definition: the set of products demanded by the first two shops the town
reveals (the same key the router uses), which groups the 36 raw shop pairs into ~20
clusters with enough towns each to separate the routes.

Usage:
  python scripts/route_map_tune.py --towns 1000-1119 --cands 4 --out data/route-map-v2.json
"""
import argparse
import collections
import json
import multiprocessing as mp
import re
import statistics
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
CHAMPION = ROOT / "data" / "tapeopt" / "rgcs" / "main.py"


def cluster_of(shops):
    import kaggle_environments.envs.kaggriculture.kaggriculture as K
    prods = set()
    for s in (shops or [])[:2]:
        prods |= set(K.SHOPS.get(s, []))
    return tuple(sorted(prods))


def build_route_agent(route):
    """Champion chassis with _router forced to one route id."""
    src = CHAMPION.read_text()
    pat = re.compile(r"def _router\(observation,step,state\):.*?(?=\n_R42_OPENING)", re.S)
    if not pat.search(src):
        raise SystemExit("could not find _router")
    src = pat.sub(f"def _router(observation,step,state):\n    return {route}\n", src, count=1)
    ns = {"__name__": f"route{route}"}
    exec(compile(src, f"<route{route}>", "exec"), ns)
    return ns["agent"]


def _job(arg):
    route, seeds, opp_path = arg
    from kaggle_environments import make
    cand = build_route_agent(route)
    opp = {"__name__": "o"}
    exec(compile(Path(opp_path).read_text(), opp_path, "exec"), opp)
    opp = opp["agent"]
    out = []
    for seed in seeds:
        for st in (0, 1):
            agents = [cand, opp] if st == 0 else [opp, cand]
            env = make("kaggriculture", configuration={"episodeSteps": 720, "seed": seed})
            env.run(agents)
            f = env.steps[-1]
            out.append({"seed": seed, "cand": float(f[st]["reward"] or 0),
                        "opp": float(f[1 - st]["reward"] or 0),
                        "status": str(f[st]["status"])})
    return route, out


def chunks(seq, n):
    step = max(1, -(-len(seq) // max(1, n)))
    return [seq[i:i + step] for i in range(0, len(seq), step)]


def parse(spec):
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
    ap.add_argument("--towns", default="1000-1119")
    ap.add_argument("--bandit", default=str(ROOT / "data" / "route_bandit.json"))
    ap.add_argument("--opp", default=str(CHAMPION))
    ap.add_argument("--cands", type=int, default=4, help="candidate routes per cluster")
    ap.add_argument("--procs", type=int, default=10)
    ap.add_argument("--out", default=str(ROOT / "data" / "route-map-v2.json"))
    args = ap.parse_args()

    towns = parse(args.towns)
    bandit = json.loads(Path(args.bandit).read_text())
    ns = {"__name__": "cur"}
    exec(compile(CHAMPION.read_text(), str(CHAMPION), "exec"), ns)
    cur_map = ns["_R108_SHOP_ROUTES"]

    # town -> shops (from the bandit data) and town -> cluster
    town_shops, town_cluster = {}, {}
    per_route_delta = collections.defaultdict(dict)
    for rid, rows in bandit.items():
        for r in rows:
            seed = int(r["seed"])
            town_shops[seed] = r["shops"]
            town_cluster[seed] = cluster_of(r["shops"])
            per_route_delta[int(rid)][seed] = r["mine"] - r["theirs"]
    towns = [t for t in towns if t in town_cluster]
    clusters = collections.defaultdict(list)
    for t in towns:
        clusters[town_cluster[t]].append(t)

    # candidates per cluster: best bandit routes + the current pick + a control
    plan = []
    for key, ts in sorted(clusters.items(), key=lambda kv: -len(kv[1])):
        means = {}
        for rid, d in per_route_delta.items():
            vals = [d[t] for t in ts if t in d]
            if vals:
                means[rid] = statistics.mean(vals)
        top = [r for r, _ in sorted(means.items(), key=lambda kv: -kv[1])[:args.cands]]
        picks = {cur_map.get(tuple(town_shops[t])) for t in ts}
        for p in picks:
            if p is not None and p not in top:
                top.append(p)
        if 0 not in top and 0 in means:
            top.append(0)
        plan.append((key, ts, top))
        print(f"cluster {str(key):46s} towns {len(ts):3d} candidates {top}", flush=True)

    jobs = [(rid, ts, args.opp) for _, ts, top in plan for rid in top]
    t0 = time.time()
    with mp.Pool(args.procs) as pool:
        res = pool.map(_job, jobs)
    print(f"[{len(jobs)} route-jobs in {time.time()-t0:.0f}s]", file=sys.stderr)
    deltas = {rid: rows for rid, rows in res}

    out = {"clusters": {}, "summary": []}
    for key, ts, top in plan:
        rows = []
        for rid in top:
            rs = [r for r in deltas.get(rid, []) if r["seed"] in ts]
            if not rs:
                continue
            d = statistics.mean(r["cand"] - r["opp"] for r in rs)
            rows.append({"route": rid, "delta": d, "n": len(rs),
                         "wallet": statistics.mean(r["cand"] for r in rs)})
        if not rows:
            continue
        rows.sort(key=lambda r: -r["delta"])
        cur = cur_map.get(tuple(town_shops[ts[0]]))
        out["clusters"][str(key)] = {"towns": len(ts), "pick": rows[0]["route"],
                                     "current": cur, "rows": rows}
        out["summary"].append({"cluster": str(key), "towns": len(ts), "pick": rows[0]["route"],
                               "pick_delta": rows[0]["delta"], "current": cur,
                               "current_delta": next((r["delta"] for r in rows
                                                      if r["route"] == cur), None)})
        print(f"{str(key):46s} n={len(ts):3d} best {rows[0]['route']:3d} {rows[0]['delta']:+9,.0f} "
              f"| current {str(cur):>4s} "
              f"{next((f'{r[chr(100)+chr(101)+chr(108)+chr(116)+chr(97)]:+.0f}' for r in rows if r['route'] == cur), '-'):>8s}")
    Path(args.out).write_text(json.dumps(out, indent=1))
    gains = [s["pick_delta"] - s["current_delta"] for s in out["summary"]
             if s["current_delta"] is not None]
    if gains:
        print(f"\nmean in-sample gain per cluster: {statistics.mean(gains):+,.0f} "
              f"(clusters {len(gains)})")
    print(f"wrote {args.out}")


if __name__ == "__main__":
    main()
