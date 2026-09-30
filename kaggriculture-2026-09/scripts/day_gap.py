#!/usr/bin/env python
"""Per-day net-worth gap between two agents, to answer "from which day do we lose".

Liquid net worth at the end of each in-game day = money + shed stock + hand cargo +
seeds, all marked to the day's market prices.  Standing crops and animals are NOT
counted (they are not yet sellable), so read this as "the day the cash/goods track
starts diverging", not as a full valuation.

Usage:
  python scripts/day_gap.py --cand data/cand/the-2945-farm-96-vs-the-top-10-public-bots/main.py \
      --base data/tapeopt/rgcs/main.py --seeds 9000-9009 --out data/day-gap-frontier.json
"""
import argparse
import importlib.util
import json
import multiprocessing as mp
import statistics as st
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SEEDCOST = {"WHEAT": 5, "CARROT": 8, "TOMATO": 12, "STRAWBERRY": 20, "MELON": 40}


def _load(path):
    name = "dg_" + Path(path).parent.name.replace("-", "_")[:24]
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec)
    sys.modules[name] = mod
    spec.loader.exec_module(mod)
    return mod.agent


def _worth(obs, p):
    farm = list(obs["farms"])[p]
    prices = dict(obs["market"]["prices"])
    priv = obs.get("private") or {}
    v = float(farm.get("money", 0.0) or 0.0)
    for item, qty in (priv.get("shed") or {}).items():
        v += max(0, int(qty)) * float(prices.get(item, 0) or 0)
    for inv in (priv.get("inventories") or []):
        for item, qty in (inv or {}).items():
            v += max(0, int(qty)) * float(prices.get(item, 0) or 0)
    for crop, qty in (priv.get("seeds") or {}).items():
        v += max(0, int(qty)) * SEEDCOST.get(crop, 0)
    return v


def _job(arg):
    cand_path, base_path, seeds = arg
    from kaggle_environments import make
    cand, base = _load(cand_path), _load(base_path)
    out = []
    for seed in seeds:
        for seat in (0, 1):
            env = make("kaggriculture", configuration={"episodeSteps": 720, "seed": seed})
            env.run([cand, base] if seat == 0 else [base, cand])
            trace = []
            for t, step in enumerate(env.steps):
                if t % 24 != 23 and t != len(env.steps) - 1:
                    continue
                obs = step[0]["observation"]
                c = _worth(obs, seat)
                b = _worth(obs, 1 - seat)
                trace.append((t // 24, c - b, c, b))
            out.append({"seed": seed, "seat": seat, "trace": trace,
                        "final": env.steps[-1][seat]["reward"] - env.steps[-1][1 - seat]["reward"]})
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--cand", required=True)
    ap.add_argument("--base", required=True)
    ap.add_argument("--seeds", default="9000-9009")
    ap.add_argument("--procs", type=int, default=10)
    ap.add_argument("--out", default="data/day-gap.json")
    args = ap.parse_args()
    lo, hi = args.seeds.split("-")
    seeds = list(range(int(lo), int(hi) + 1))
    groups = [seeds[i::args.procs] for i in range(args.procs)]
    jobs = [(args.cand, args.base, g) for g in groups if g]
    with mp.Pool(args.procs) as pool:
        res = pool.map(_job, jobs)
    rows = [r for sub in res for r in sub]

    days = sorted({d for r in rows for d, _, _, _ in r["trace"]})
    print(f"{len(rows)} games; per-day liquid net-worth delta (cand - base), mean +- stdev")
    print(f"{'day':>4} {'delta':>10} {'sd':>9} {'positive':>9} {'cand':>10} {'base':>10}")
    curve = []
    for d in days:
        vals, c, b = [], [], []
        for r in rows:
            m = {y[0]: y for y in r["trace"]}
            if d in m:
                vals.append(m[d][1])
                c.append(m[d][2])
                b.append(m[d][3])
        sd = st.stdev(vals) if len(vals) > 1 else 0.0
        row = {"day": d, "delta": st.mean(vals), "sd": sd,
               "pos": sum(1 for v in vals if v > 0), "n": len(vals),
               "cand": st.mean(c) if c else 0.0, "base": st.mean(b) if b else 0.0}
        curve.append(row)
        print(f"{d:>4} {row['delta']:>10,.0f} {sd:>9,.0f} {row['pos']:>4}/{row['n']:<4} "
              f"{row['cand']:>10,.0f} {row['base']:>10,.0f}")
    # first day the deficit is both negative and beyond one standard error
    first = None
    for row in curve:
        if row["delta"] < 0 and row["sd"] > 0 and abs(row["delta"]) > row["sd"] / max(1, row["n"]) ** 0.5:
            first = row["day"]
            break
    fin = st.mean([r["final"] for r in rows])
    print(f"\nfinal wallet delta (cand - base): {fin:+,.0f}")
    print(f"first day the net-worth deficit is statistically real: day {first}")
    Path(args.out).write_text(json.dumps({"cand": args.cand, "base": args.base,
                                          "games": len(rows), "curve": curve,
                                          "final": fin, "first_loss_day": first}, indent=1))
    print(f"wrote {args.out}")


if __name__ == "__main__":
    sys.exit(main())
