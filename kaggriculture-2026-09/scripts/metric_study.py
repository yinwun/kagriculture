#!/usr/bin/env python
"""Which local metric actually predicts the ladder?

We have six agents whose *ladder* outcome is already known, and we have been
burned twice by trusting a local metric that did not transfer (front_run won
92.5% locally and lost ~170 rating; V40 crushed the previous champion 40:0 and
still landed lower than it).

This script measures a battery of local metrics for each of those agents against
fixed opponents, then correlates them with the known ladder results.

Usage: python scripts/metric_study.py --seeds 20
"""
import argparse
import json
import os
import statistics
import time
from pathlib import Path

from kaggle_environments import make

ROOT = Path(__file__).resolve().parent.parent

# candidates with KNOWN ladder outcomes (final public score while tracked)
KNOWN = {
    "v37base":      ("data/nb_build/main.py", 2632.1),
    "v37clamp":     ("data/variants/on_clamp_sells/main.py", 2674.2),
    "v40":          ("data/league/ahmedberatozer_kaggriculture-v40-plans-that-fit-the-marke/main.py", 2572.1),
    "v40clamp":     ("data/v40clamp/on_clamp_sells/main.py", 2587.9),
    "fr":           ("data/enh/fr/main.py", 2493.5),
    "frsort":       ("data/enh/fr_sort/main.py", 2242.8),
}

OPPONENTS = {
    "starter": "starter",
    "v42base": "data/league/ahmedberatozer_kaggriculture-v42-production-that-fits-the-marke/main.py",
    "v41": "data/league/ahmedberatozer_kaggriculture-v41-review-candidate/main.py",
    "aurax7v5": "data/league/aurax7_kaggriculture-shop-router-reactive-v5/main.py",
}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--seeds", type=int, default=20)
    ap.add_argument("--start", type=int, default=400000)
    ap.add_argument("--out", default="data/metric_study.json")
    args = ap.parse_args()

    metrics = {}
    t0 = time.time()
    for name, (path, ladder) in KNOWN.items():
        p = os.path.abspath(ROOT / path)
        if not os.path.exists(p):
            print(f"!! missing {name}")
            continue
        row = {"ladder": ladder}
        for oname, opath in OPPONENTS.items():
            opp = opath if opath in ("starter", "random", "pass") else os.path.abspath(ROOT / opath)
            banks, margins, wins = [], [], 0
            for i in range(args.seeds):
                seed = args.start + i
                env = make("kaggriculture", configuration={"episodeSteps": 720, "seed": seed})
                env.run([p, opp])
                f = env.steps[-1]
                banks.append(f[0]["reward"])
                margins.append(f[0]["reward"] - f[1]["reward"])
                wins += f[0]["reward"] > f[1]["reward"]
            row[f"bank_{oname}"] = statistics.mean(banks)
            row[f"margin_{oname}"] = statistics.mean(margins)
            row[f"win_{oname}"] = wins / args.seeds
        # self-play vs the strongest local reference: margin vs v42base is often
        # too saturated, so also record spread
        metrics[name] = row
        print(f"  {name:<10} ladder={ladder:>7.1f}  "
              f"bank_starter={row['bank_starter']:>9,.0f}  bank_v42base={row['bank_v42base']:>9,.0f}  "
              f"win_v42base={row['win_v42base']*100:>5.1f}%  margin_v42base={row['margin_v42base']:>+8,.0f}", flush=True)

    # correlation of each local metric with the known ladder score
    print("\n=== 本地指标与天梯分数的相关性(n=6)===")
    names = list(metrics)
    ladder = [metrics[n]["ladder"] for n in names]
    keys = [k for k in metrics[names[0]] if k != "ladder"]
    def pearson(a, b):
        ma, mb = statistics.mean(a), statistics.mean(b)
        num = sum((x - ma) * (y - mb) for x, y in zip(a, b))
        den = (sum((x - ma) ** 2 for x in a) * sum((y - mb) ** 2 for y in b)) ** 0.5
        return num / den if den else 0.0
    ranked = sorted(((pearson([metrics[n][k] for n in names], ladder), k) for k in keys), reverse=True)
    for r, k in ranked:
        print(f"  {k:<22} r = {r:+.3f}")

    json.dump({"metrics": metrics, "correlations": {k: r for r, k in ranked}},
              open(ROOT / args.out, "w"), indent=1)
    print(f"\nwrote {args.out}  ({(time.time()-t0)/60:.1f} min)")


if __name__ == "__main__":
    main()
