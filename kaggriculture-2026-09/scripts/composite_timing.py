#!/usr/bin/env python
"""Per-step runtime of a composite-derived agent, against the engine's actTimeout.

The kaggriculture configuration is `actTimeout: 1` -- one second per step, per seat.
A layer that pushes a step past it is not a candidate however good its wallet is, so
every variant is measured here: wall time per `agent()` call (mean / p50 / p95 / p99 /
max), how many calls exceed 250/500/1000 ms, and the slowest steps.

Usage: python scripts/composite_timing.py --agents A B --seed 9000
"""
import argparse
import json
import statistics as st
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def load(path):
    ns = {"__name__": "timing_mod"}
    exec(compile(Path(path).read_text(), path, "exec"), ns)
    return ns["agent"]


def timed(inner, rec):
    def wrap(obs, *a, **k):                      # 2-arg safe: kaggle may pass config
        t0 = time.perf_counter()
        r = inner(obs, *a, **k)
        rec.append((time.perf_counter() - t0) * 1000.0)
        return r
    return wrap


def measure(path, seed, steps=720):
    from kaggle_environments import make
    inner = load(path)
    rec = []
    a = timed(inner, rec)
    env = make("kaggriculture", configuration={"episodeSteps": steps, "seed": seed})
    t0 = time.perf_counter()
    env.run([a, a])
    wall = time.perf_counter() - t0
    rec_sorted = sorted(rec)
    q = lambda p: rec_sorted[min(len(rec_sorted) - 1, int(p * len(rec_sorted)))]  # noqa: E731
    out = {"agent": str(path), "calls": len(rec), "game_wall_s": wall,
           "mean_ms": st.mean(rec), "p50_ms": q(0.50), "p95_ms": q(0.95),
           "p99_ms": q(0.99), "max_ms": rec_sorted[-1],
           "over_250ms": sum(1 for x in rec if x > 250),
           "over_500ms": sum(1 for x in rec if x > 500),
           "over_1000ms": sum(1 for x in rec if x > 1000),
           "rewards": [env.steps[-1][i]["reward"] for i in (0, 1)],
           "status": [str(env.steps[-1][i]["status"]) for i in (0, 1)]}
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--agents", nargs="+", required=True)
    ap.add_argument("--seed", type=int, default=9000)
    ap.add_argument("--out", default=str(ROOT / "data" / "composite" / "timing.json"))
    args = ap.parse_args()
    res = []
    print(f"actTimeout = 1 s/step (engine default); machine-dependent, so compare ratios")
    print(f"{'agent':46} {'calls':>5} {'mean':>7} {'p95':>7} {'p99':>7} {'max':>8} "
          f"{'>250':>5} {'>500':>5} {'>1s':>4} {'game s':>7}")
    for p in args.agents:
        r = measure(p, args.seed)
        res.append(r)
        name = str(p).replace("data/", "").replace("/main.py", "")[:46]
        print(f"{name:46} {r['calls']:>5} {r['mean_ms']:>6.1f} {r['p95_ms']:>7.1f} "
              f"{r['p99_ms']:>7.1f} {r['max_ms']:>8.1f} {r['over_250ms']:>5} "
              f"{r['over_500ms']:>5} {r['over_1000ms']:>4} {r['game_wall_s']:>7.1f}")
    base = res[0]["mean_ms"]
    for r in res[1:]:
        print(f"  ratio vs first: {Path(r['agent']).parent.name:14} "
              f"mean x{r['mean_ms']/base:.2f}  max {r['max_ms']/res[0]['max_ms']:.2f}")
    Path(args.out).write_text(json.dumps(res, indent=1))
    print(f"wrote {args.out}")


if __name__ == "__main__":
    main()
