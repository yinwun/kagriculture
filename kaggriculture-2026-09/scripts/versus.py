#!/usr/bin/env python
"""Strict head-to-head evaluation with alternating seats.

For every seed both seat orders are played: (A seat0, B seat1) and (B seat0, A seat1).
That removes any first-mover advantage in the shared market queue, so the reported
win rate is purely about agent strength.

Usage:
  python scripts/versus.py A/main.py B/main.py --seeds 40 [--binary WILSON]

Reports W/L/T, win rate (ties = 0.5), a 95% Wilson interval, and bank stats.
"""
import argparse
import json
import math
import os
import statistics
import time

from kaggle_environments import make


def wilson(w, n, z=1.96):
    if n == 0:
        return (0.0, 0.0)
    p = w / n
    d = 1 + z * z / n
    c = p + z * z / (2 * n)
    r = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n))
    return ((c - r) / d, (c + r) / d)


def run(a, b, seed):
    env = make("kaggriculture", configuration={"episodeSteps": 720, "seed": seed})
    env.run([a, b])
    f = env.steps[-1]
    return f[0]["reward"], f[1]["reward"], f[0]["status"], f[1]["status"]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("agent_a")
    ap.add_argument("agent_b")
    ap.add_argument("--seeds", type=int, default=40)
    ap.add_argument("--start", type=int, default=20000)
    ap.add_argument("--out", default=None)
    args = ap.parse_args()

    A, B = os.path.abspath(args.agent_a), os.path.abspath(args.agent_b)
    na = os.path.basename(os.path.dirname(A))
    nb = os.path.basename(os.path.dirname(B))

    aw = bw = tie = 0
    banks_a, banks_b = [], []
    seats = {"a0": [0, 0], "a1": [0, 0]}  # [wins, games] for A in seat0 / seat1
    errors = 0
    t0 = time.time()

    for i in range(args.seeds):
        seed = args.start + i
        for a_first in (True, False):
            x, y, sx, sy = run(A, B, seed) if a_first else run(B, A, seed)
            if not a_first:
                x, y = y, x
                sx, sy = sy, sx
            if sx != "DONE" or sy != "DONE":
                errors += 1
            banks_a.append(x)
            banks_b.append(y)
            if a_first:
                seats["a0"][1] += 1
            else:
                seats["a1"][1] += 1
            if x > y:
                aw += 1
                seats["a0" if a_first else "a1"][0] += 1
            elif y > x:
                bw += 1
            else:
                tie += 1
    n = aw + bw + tie
    wr = (aw + 0.5 * tie) / n
    lo, hi = wilson(aw + 0.5 * tie, n)

    print(f"A = {na}")
    print(f"B = {nb}")
    print(f"games per side = {args.seeds}  ->  total {n} games (alternating seats)")
    print(f"  {na:<10} {aw:>4} W / {bw:>4} L / {tie:>4} T   winrate = {wr * 100:.1f}% "
          f"(95% CI {lo * 100:.1f}-{hi * 100:.1f}%)")
    print(f"  mean bank: {na}={statistics.mean(banks_a):,.0f}  {nb}={statistics.mean(banks_b):,.0f} "
          f"(diff {statistics.mean(banks_a) - statistics.mean(banks_b):+,.0f})")
    print(f"  seat check: {na} seat0 {seats['a0'][0]}/{seats['a0'][1]}  "
          f"seat1 {seats['a1'][0]}/{seats['a1'][1]}")
    if errors:
        print(f"  !! non-DONE statuses: {errors}")
    verdict = "A stronger" if lo > 0.5 else "B stronger" if hi < 0.5 else "NO significant difference"
    print(f"  verdict: {verdict}")
    print(f"  elapsed {time.time() - t0:.0f}s")

    if args.out:
        json.dump({"a": na, "b": nb, "a_wins": aw, "b_wins": bw, "ties": tie,
                   "winrate_a": wr, "ci": [lo, hi], "seeds": args.seeds,
                   "banks_a": banks_a, "banks_b": banks_b},
                  open(args.out, "w"), indent=1)


if __name__ == "__main__":
    main()
