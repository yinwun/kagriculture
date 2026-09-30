#!/usr/bin/env python
"""Strength-matched pool evaluation + noise floor measurement.

Context (see REPORT-metric-study.md): our local instruments failed to predict the
ladder. Two suspected reasons:
  1. the opponent pool is mismatched (either far weaker -> win-rate saturation,
     or far stronger -> floor effect), and
  2. the measurement noise may be larger than the effects we care about.

This script attacks both:
  * a POOL of current strong public agents (23-party strength band) instead of
    `starter`,
  * SPLIT-HALF noise estimation: the same candidate is measured on two disjoint
    seed halves; the disagreement between halves is the instrument's noise floor.

Output: data/pool_eval.json + a printed table.

Usage:
  python scripts/pool_eval.py --seeds 40 --candidates v42clamp,v42base,...
"""
import argparse
import json
import os
import statistics
import time
from pathlib import Path

from kaggle_environments import make

ROOT = Path(__file__).resolve().parent.parent

POOL = {
    "v42":        "data/league/ahmedberatozer_kaggriculture-v42-production-that-fits-the-marke/main.py",
    "v41":        "data/league/ahmedberatozer_kaggriculture-v41-review-candidate/main.py",
    "aurax7v5":   "data/league/aurax7_kaggriculture-shop-router-reactive-v5/main.py",
    "v40":        "data/league/ahmedberatozer_kaggriculture-v40-plans-that-fit-the-shops/main.py",
    "masterv3":   "data/league/pool_guruprasaathas111_kaggriculture-master-engine-v3/main.py",
    "xu_landalloc": "data/league/pool_xuantianfengwu/main.py",
}

CANDIDATES = {
    "v42clamp": "data/v42clamp/main.py",
    "v42base":  "data/league/ahmedberatozer_kaggriculture-v42-production-that-fits-the-marke/main.py",
    "v40clamp": "data/v40clamp/on_clamp_sells/main.py",
    "v37clamp": "data/variants/on_clamp_sells/main.py",
    "fr":       "data/enh/fr/main.py",
}


def play(cand, opp, seed):
    env = make("kaggriculture", configuration={"episodeSteps": 720, "seed": seed})
    env.run([cand, opp])
    f = env.steps[-1]
    return f[0]["reward"], f[1]["reward"]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--seeds", type=int, default=40)
    ap.add_argument("--start", type=int, default=500000)
    ap.add_argument("--candidates", default="v42clamp,v42base,v40clamp,v37clamp,fr")
    ap.add_argument("--out", default="data/pool_eval.json")
    args = ap.parse_args()

    cands = {k: os.path.abspath(ROOT / CANDIDATES[k]) for k in args.candidates.split(",") if k in CANDIDATES}
    pool = {k: os.path.abspath(ROOT / v) for k, v in POOL.items() if os.path.exists(ROOT / v)}
    print(f"candidates={list(cands)}  pool={list(pool)}  seeds={args.seeds} (x2 seats)")
    t0 = time.time()

    result = {"seeds": args.seeds, "start": args.start, "candidates": {}}
    for cname, cpath in cands.items():
        per_opp = {}
        for oname, opath in pool.items():
            banks_a, banks_b = [], []          # A = first half seeds, B = second half
            opps_a, opps_b = [], []
            half = args.seeds // 2
            for i in range(args.seeds):
                seed = args.start + i
                for first in (True, False):
                    a, b = play(cpath, opath, seed) if first else play(opath, cpath, seed)
                    mine, theirs = (a, b) if first else (b, a)
                    if i < half:
                        banks_a.append(mine); opps_a.append(theirs)
                    else:
                        banks_b.append(mine); opps_b.append(theirs)
            per_opp[oname] = {
                "bank": statistics.mean(banks_a + banks_b),
                "opp_bank": statistics.mean(opps_a + opps_b),
                "bank_half1": statistics.mean(banks_a),
                "bank_half2": statistics.mean(banks_b),
                "n": len(banks_a) + len(banks_b),
            }
        allb1 = [v["bank_half1"] for v in per_opp.values()]
        allb2 = [v["bank_half2"] for v in per_opp.values()]
        score1, score2 = statistics.mean(allb1), statistics.mean(allb2)
        noise = abs(score1 - score2) / max(1.0, (score1 + score2) / 2) * 100
        result["candidates"][cname] = {"per_opponent": per_opp,
                                       "pool_bank_half1": score1,
                                       "pool_bank_half2": score2,
                                       "split_half_gap_pct": noise}
        print(f"  {cname:<10} pool_bank={statistics.mean([score1, score2]):>9,.0f}  "
              f"half1={score1:>9,.0f} half2={score2:>9,.0f}  gap={noise:>5.2f}%  "
              f"({(time.time()-t0)/60:.1f} min)", flush=True)

    print("\n=== 噪声地板(split-half 差距) ===")
    gaps = [(v["split_half_gap_pct"], k) for k, v in result["candidates"].items()]
    for g, k in sorted(gaps):
        print(f"  {k:<10} {g:>5.2f}%")
    if gaps:
        print(f"  中位噪声 = {statistics.median([g for g, _ in gaps]):.2f}%  "
              f"=> 小于此幅度的改动本地无法分辨")

    print("\n=== 候选排序(按对手池平均自身金币)===")
    rank = sorted(((statistics.mean([v['pool_bank_half1'], v['pool_bank_half2']]), k)
                   for k, v in result["candidates"].items()), reverse=True)
    for s, k in rank:
        print(f"  {k:<10} {s:>10,.0f}")

    json.dump(result, open(ROOT / args.out, "w"), indent=1)
    print(f"\nwrote {args.out}  ({(time.time()-t0)/60:.1f} min)")


if __name__ == "__main__":
    main()
