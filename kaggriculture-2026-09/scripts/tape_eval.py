#!/usr/bin/env python
"""Tape-layer optimisation harness.

Why: win-rate metrics saturate locally (our agents beat every local opponent
100%), but *absolute final bank* does not saturate and is what separates us from
the top of the ladder (top agents earn ~30% more in the same game).

This harness measures a candidate by its OWN mean final bank against a fixed
opponent set over paired seeds, plus the action-composition stats that the top
replays showed we are short on (WATER / FERTILIZE / idle PASS).

Usage:
  python scripts/tape_eval.py <candidate main.py> --seeds 30 --opponents starter,v42base
"""
import argparse
import json
import os
import statistics
import time
from collections import Counter

from kaggle_environments import make

OPPONENTS = {
    "starter": "starter",
    "v42base": "data/league/ahmedberatozer_kaggriculture-v42-production-that-fits-the-marke/main.py",
    "v42clamp": "data/v42clamp/main.py",
    "aurax7v5": "data/league/aurax7_kaggriculture-shop-router-reactive-v5/main.py",
    "v41": "data/league/ahmedberatozer_kaggriculture-v41-review-candidate/main.py",
}


def composition(steps, seat):
    ops = Counter()
    for st in steps:
        a = st[seat].get("action") or {}
        for c in [a.get("farmer") or []] + list(a.get("hands") or []):
            if isinstance(c, list) and c:
                ops[c[0]] += 1
    return ops


def run_one(cand, opp, seed, want_comp=False):
    env = make("kaggriculture", configuration={"episodeSteps": 720, "seed": seed})
    env.run([cand, opp])
    final = env.steps[-1]
    bank = final[0]["reward"]
    opp_bank = final[1]["reward"]
    status = (final[0]["status"], final[1]["status"])
    comp = composition(env.steps, 0) if want_comp else None
    return bank, opp_bank, status, comp


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("candidate")
    ap.add_argument("--seeds", type=int, default=30)
    ap.add_argument("--start", type=int, default=200000)
    ap.add_argument("--opponents", default="starter,v42base")
    ap.add_argument("--baseline", default=None, help="compare candidate against this agent too")
    ap.add_argument("--out", default=None)
    ap.add_argument("--comp-seeds", type=int, default=2)
    args = ap.parse_args()

    cand = os.path.abspath(args.candidate)
    names = [n.strip() for n in args.opponents.split(",") if n.strip()]
    result = {"candidate": cand, "seeds": args.seeds, "opponents": {}}
    t0 = time.time()

    for name in names:
        opp = OPPONENTS.get(name, name)
        opp = opp if opp in ("starter", "random", "pass") else os.path.abspath(opp)
        banks = []
        wins = 0
        comp_total = Counter()
        for i in range(args.seeds):
            seed = args.start + i
            b, ob, st, comp = run_one(cand, opp, seed, want_comp=(i < args.comp_seeds))
            banks.append(b)
            wins += b > ob
            if comp:
                comp_total.update(comp)
        n = args.seeds
        result["opponents"][name] = {
            "mean_bank": statistics.mean(banks),
            "median_bank": statistics.median(banks),
            "stdev": statistics.stdev(banks) if n > 1 else 0,
            "wins": wins,
            "winrate": wins / n,
            "banks": banks,
        }
        print(f"  vs {name:<10} mean_bank={statistics.mean(banks):>10,.0f} "
              f"median={statistics.median(banks):>10,.0f} sd={statistics.stdev(banks) if n>1 else 0:>8,.0f} "
              f"wins={wins}/{n}")
        if comp_total:
            tot = sum(comp_total.values()) or 1
            print(f"      comp: WATER={comp_total['WATER']} FERTILIZE={comp_total['FERTILIZE']} "
                  f"HARVEST={comp_total['HARVEST']} PASS={comp_total['PASS']}({comp_total['PASS']/tot*100:.1f}%) "
                  f"PLACE={comp_total['PLACE']} total_actions={tot}")

    if args.baseline:
        base = os.path.abspath(args.baseline)
        print(f"\n=== paired comparison vs baseline (same seeds) ===")
        base_res = {}
        for name in names:
            opp = OPPONENTS.get(name, name)
            opp = opp if opp in ("starter", "random", "pass") else os.path.abspath(opp)
            bb = []
            for i in range(args.seeds):
                seed = args.start + i
                b, _, _, _ = run_one(base, opp, seed)
                bb.append(b)
            cb = result["opponents"][name]["banks"]
            diffs = [c - b for c, b in zip(cb, bb)]
            mean_d = statistics.mean(diffs)
            se = (statistics.stdev(diffs) / len(diffs) ** 0.5) if len(diffs) > 1 else 0
            better = sum(1 for d in diffs if d > 0)
            base_res[name] = {"mean_bank": statistics.mean(bb), "mean_diff": mean_d,
                              "stderr": se, "better_seeds": better}
            print(f"  vs {name:<10} baseline_mean={statistics.mean(bb):>10,.0f}  "
                  f"cand_mean={statistics.mean(cb):>10,.0f}  diff={mean_d:>+9,.0f} "
                  f"(se {se:,.0f}, t={mean_d/se if se else 0:.2f})  better on {better}/{len(diffs)} seeds")
        result["baseline"] = base_res

    print(f"\nelapsed {time.time() - t0:.0f}s")
    if args.out:
        os.makedirs(os.path.dirname(args.out), exist_ok=True)
        json.dump(result, open(args.out, "w"), indent=1)
        print("wrote", args.out)


if __name__ == "__main__":
    main()
