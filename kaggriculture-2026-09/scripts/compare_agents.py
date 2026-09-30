#!/usr/bin/env python
"""Rank several agent builds on identical towns (paired, parallel).

Each candidate plays the SAME seeds against the SAME opponent, so the wallet
differences are paired per town and town luck cancels out.

Usage:
  python scripts/compare_agents.py --agents a.py,b.py,c.py --seeds 8000-8059 \
      --opponent <main.py> --procs 60
"""
import argparse
import json
import multiprocessing as mp
import statistics
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))
V42 = (ROOT / "data" / "league" /
       "ahmedberatozer_kaggriculture-v42-production-that-fits-the-marke" / "main.py")


def _one(arg):
    path, opponent, seeds = arg
    from kaggle_environments import make
    import par_eval
    me = par_eval._load_path(path, None)
    opp = par_eval._load_path(opponent, None)
    out = []
    for s in seeds:
        env = make("kaggriculture", configuration={"episodeSteps": 720, "seed": s})
        env.run([me, opp])
        f = env.steps[-1]
        out.append({"seed": s, "mine": f[0]["reward"] or 0, "theirs": f[1]["reward"] or 0})
    return path, out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--agents", required=True)
    ap.add_argument("--opponent", default=str(V42))
    ap.add_argument("--seeds", default="8000-8059")
    ap.add_argument("--procs", type=int, default=60)
    args = ap.parse_args()
    agents = [a.strip() for a in args.agents.split(",") if a.strip()]
    seeds = []
    for part in args.seeds.split(","):
        if "-" in part:
            a, b = part.split("-")
            seeds.extend(range(int(a), int(b) + 1))
        else:
            seeds.append(int(part))
    per = max(1, (args.procs * 2) // max(1, len(agents)))
    jobs = []
    for a in agents:
        step = max(1, -(-len(seeds) // per))
        for i in range(0, len(seeds), step):
            jobs.append((a, args.opponent, seeds[i:i + step]))
    with mp.Pool(min(args.procs, len(jobs))) as pool:
        res = pool.map(_one, jobs)
    by = {}
    for path, rows in res:
        by.setdefault(path, []).extend(rows)
    print(f"paired on {len(seeds)} towns vs {Path(args.opponent).parent.name[-20:]}")
    means = {}
    for a in agents:
        rows = sorted(by[a], key=lambda r: r["seed"])
        means[a] = statistics.mean(r["mine"] for r in rows)
        print(f"  {Path(a).parent.name[:26]:28} mean wallet {means[a]:10,.0f}  "
              f"(vs opponent {statistics.mean(r['theirs'] for r in rows):10,.0f})")
    # pairwise vs the first agent
    base = agents[0]
    brows = {r["seed"]: r["mine"] for r in by[base]}
    print(f"\npaired deltas vs {Path(base).parent.name[:26]}:")
    for a in agents[1:]:
        rows = sorted(by[a], key=lambda r: r["seed"])
        d = [r["mine"] - brows[r["seed"]] for r in rows if r["seed"] in brows]
        mu = statistics.mean(d)
        sd = statistics.stdev(d) if len(d) > 1 else 0.0
        t = mu / (sd / len(d) ** 0.5) if sd else 0.0
        print(f"  {Path(a).parent.name[:26]:28} {mu:+9,.0f}  t={t:+5.2f}  "
              f"W/L {sum(1 for x in d if x > 0)}/{sum(1 for x in d if x < 0)}")


if __name__ == "__main__":
    main()
