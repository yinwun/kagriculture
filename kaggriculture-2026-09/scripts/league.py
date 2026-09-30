#!/usr/bin/env python
"""Round-robin league for kaggriculture agents.

Usage:
    python scripts/league.py --seeds 8 --out data/league_result.json [name=path ...]

Plays every pair over the same seed set and reports a win matrix. This is the
local proxy for ladder strength: the ladder only counts win/loss/tie, never the
coin margin, so the matrix is scored the same way.
"""
import argparse
import itertools
import json
import os
import statistics
import time

from kaggle_environments import make

DEFAULT = {
    "v109": "pkg/v109_extract/main.py",
    "herd-safe-2700": "data/nb_build/main.py",
    "0911-simple": "data/nb_0911_build/main.py",
    "0909-base": "data/nb_base_build/main.py",
    "aurax7-reactive": "data/league/aurax7_kaggriculture-shop-router-reactive-v2/main.py",
    "v36-guarded": "data/league/ahmedberatozer_kaggriculture-v36-guarded-four-turn-sales/main.py",
}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("agents", nargs="*", help="name=path overrides/additions")
    ap.add_argument("--seeds", type=int, default=8)
    ap.add_argument("--start", type=int, default=5000)
    ap.add_argument("--out", default="data/league_result.json")
    ap.add_argument("--only", nargs="*", help="restrict to these agent names")
    args = ap.parse_args()

    agents = dict(DEFAULT)
    for item in args.agents:
        name, _, path = item.partition("=")
        agents[name] = os.path.abspath(path)
    if args.only:
        agents = {k: v for k, v in agents.items() if k in args.only}
    for name, path in list(agents.items()):
        if not os.path.exists(path):
            print(f"!! missing {name}: {path}")
            del agents[name]

    names = list(agents)
    seeds = [args.start + i for i in range(args.seeds)]
    score = {n: {"w": 0, "l": 0, "t": 0, "bank": []} for n in names}
    matrix = {a: {b: {"w": 0, "l": 0, "t": 0} for b in names if b != a} for a in names}

    t0 = time.time()
    for a, b in itertools.combinations(names, 2):
        for seed in seeds:
            env = make("kaggriculture", configuration={"episodeSteps": 720, "seed": seed})
            env.run([agents[a], agents[b]])
            f = env.steps[-1]
            ra, rb = f[0]["reward"], f[1]["reward"]
            score[a]["bank"].append(ra)
            score[b]["bank"].append(rb)
            if ra > rb:
                score[a]["w"] += 1
                score[b]["l"] += 1
                matrix[a][b]["w"] += 1
                matrix[b][a]["l"] += 1
            elif rb > ra:
                score[b]["w"] += 1
                score[a]["l"] += 1
                matrix[b][a]["w"] += 1
                matrix[a][b]["l"] += 1
            else:
                score[a]["t"] += 1
                score[b]["t"] += 1
                matrix[a][b]["t"] += 1
                matrix[b][a]["t"] += 1
        print(f"  {a} vs {b}: done ({time.time() - t0:.0f}s)", flush=True)

    print("\n=== overall (ties = 0.5) ===")
    print(f"{'agent':<18} {'games':>6} {'W':>4} {'L':>4} {'T':>3} {'winrate':>8} {'mean bank':>11}")
    rank = []
    for n in names:
        s = score[n]
        g = s["w"] + s["l"] + s["t"]
        wr = (s["w"] + 0.5 * s["t"]) / g
        rank.append((wr, n, s, g))
        print(f"{n:<18} {g:>6} {s['w']:>4} {s['l']:>4} {s['t']:>3} {wr * 100:>7.1f}% "
              f"{statistics.mean(s['bank']):>11,.0f}")
    print("\n=== head-to-head winrate (row vs column) ===")
    print(" " * 18 + "".join(f"{n[:11]:>12}" for n in names))
    for a in names:
        cells = []
        for b in names:
            if a == b:
                cells.append(f"{'-':>12}")
                continue
            m = matrix[a][b]
            g = m["w"] + m["l"] + m["t"]
            cells.append(f"{(m['w'] + 0.5 * m['t']) / g * 100:>11.0f}%")
        print(f"{a:<18}" + "".join(cells))

    rank.sort(reverse=True)
    print("\nranking: " + " > ".join(f"{n}({wr * 100:.0f}%)" for wr, n, _, _ in rank))
    json.dump(
        {"score": {k: {kk: (vv if kk != "bank" else vv) for kk, vv in v.items()} for k, v in score.items()},
         "matrix": matrix, "seeds": seeds, "elapsed": time.time() - t0},
        open(args.out, "w"), indent=1)
    print(f"\nwrote {args.out}  ({time.time() - t0:.0f}s)")


if __name__ == "__main__":
    main()
