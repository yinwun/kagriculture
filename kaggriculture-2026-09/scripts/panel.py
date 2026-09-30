#!/usr/bin/env python
"""Score one candidate against a fixed panel of diverse opponents.

The ladder only counts win/loss, so a candidate is scored by its win rate over a
panel of *different* agents (not just its own twin, which mainly measures
market-timing rock-paper-scissors).

Usage:
  python scripts/panel.py <candidate main.py> --seeds 8 --out data/panel/x.json
"""
import argparse
import json
import math
import os
import statistics
import time

from kaggle_environments import make

PANEL = {
    "0911-simple": "data/nb_0911_build/main.py",
    "v36": "data/league/ahmedberatozer_kaggriculture-v36-guarded-four-turn-sales/main.py",
    "v109": "pkg/v109_extract/main.py",
    "0909-base": "data/nb_base_build/main.py",
    "tetsutani": "data/league/tetsutani/main.py",
    "aurax7": "data/league/aurax7_kaggriculture-shop-router-reactive-v2/main.py",
    "nusrati": "data/league/nusrati/main.py",
    "prvsiyan": "data/league/prvsiyan_kaggriculture-frontier-the-moon-counts-melons/main.py",
}


def wilson(w, n, z=1.96):
    if n == 0:
        return (0.0, 0.0)
    p = w / n
    d = 1 + z * z / n
    c = p + z * z / (2 * n)
    r = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n))
    return ((c - r) / d, (c + r) / d)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("candidate")
    ap.add_argument("--seeds", type=int, default=8)
    ap.add_argument("--start", type=int, default=40000)
    ap.add_argument("--out", default=None)
    ap.add_argument("--only", nargs="*")
    args = ap.parse_args()

    cand = os.path.abspath(args.candidate)
    panel = {k: os.path.abspath(v) for k, v in PANEL.items() if os.path.exists(v)}
    if args.only:
        panel = {k: v for k, v in panel.items() if k in args.only}

    tot_w = tot_n = 0
    per = {}
    t0 = time.time()
    print(f"candidate: {os.path.basename(os.path.dirname(cand))}")
    print(f"{'opponent':<14} {'games':>6} {'W':>4} {'L':>4} {'T':>3} {'winrate':>9} {'mean margin':>12}")
    for name, path in panel.items():
        w = l = t = 0
        margins = []
        for i in range(args.seeds):
            seed = args.start + i
            for cand_first in (True, False):
                first, second = (cand, path) if cand_first else (path, cand)
                env = make("kaggriculture", configuration={"episodeSteps": 720, "seed": seed})
                env.run([first, second])
                f = env.steps[-1]
                r0, r1 = f[0]["reward"], f[1]["reward"]
                mine, theirs = (r0, r1) if cand_first else (r1, r0)
                margins.append(mine - theirs)
                if mine > theirs:
                    w += 1
                elif theirs > mine:
                    l += 1
                else:
                    t += 1
        n = w + l + t
        tot_w += w + 0.5 * t
        tot_n += n
        per[name] = {"w": w, "l": l, "t": t, "winrate": (w + 0.5 * t) / n,
                     "mean_margin": statistics.mean(margins)}
        print(f"{name:<14} {n:>6} {w:>4} {l:>4} {t:>3} {(w + 0.5 * t) / n * 100:>8.1f}% "
              f"{statistics.mean(margins):>+12,.0f}")
    wr = tot_w / tot_n
    lo, hi = wilson(tot_w, tot_n)
    print(f"\nPANEL TOTAL: {tot_n} games  winrate = {wr * 100:.2f}%  (95% CI {lo * 100:.2f}-{hi * 100:.2f}%)")
    print(f"elapsed {time.time() - t0:.0f}s")
    if args.out:
        os.makedirs(os.path.dirname(args.out), exist_ok=True)
        json.dump({"candidate": cand, "seeds": args.seeds, "total": tot_n,
                   "winrate": wr, "ci": [lo, hi], "per_opponent": per},
                  open(args.out, "w"), indent=1)


if __name__ == "__main__":
    main()
