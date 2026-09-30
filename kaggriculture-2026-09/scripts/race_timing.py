#!/usr/bin/env python
"""Per-step wall-clock of a built agent over a full game (the ladder's cost measure).

Reports mean / median / p95 / worst single step of the WHOLE agent call, plus the
race layer's evaluation count, so a widened search can be judged against the ladder's
per-step limit rather than against a delta alone.

Usage: .venv/bin/python scripts/race_timing.py --cand <main.py> [--base <main.py>]
"""
from __future__ import annotations

import argparse
import statistics
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def load(path, name):
    ns = {"__name__": name}
    exec(compile(Path(path).read_text(), str(path), "exec"), ns)
    return ns


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--cand", required=True)
    ap.add_argument("--base", default=str(ROOT / "data" / "tapeopt" / "rgcs" / "main.py"))
    ap.add_argument("--seed", type=int, default=9000)
    a = ap.parse_args()
    from kaggle_environments import make

    rows = []
    for role, path in (("cand", a.cand), ("base", a.base)):
        ns = load(path, "t_" + role)
        times = []

        def wrap(obs, *args, **kw):
            t0 = time.perf_counter()
            act = ns["agent"](obs)
            times.append(time.perf_counter() - t0)
            return act

        env = make("kaggriculture", configuration={"episodeSteps": 720, "seed": a.seed})
        env.run([wrap, ns["agent"]])
        d = ns["_IMPL"].chassis.diagnostics
        g = lambda k: d.get(k) or 0
        q = statistics.quantiles(times, n=20)[-1] if len(times) > 20 else max(times)
        print(f"{role:4s} {Path(path).parent.name:20s} steps {len(times)} "
              f"mean {1000*statistics.mean(times):7.1f} ms  median {1000*statistics.median(times):7.1f} ms  "
              f"p95 {1000*q:7.1f} ms  worst {1000*max(times):7.1f} ms  "
              f"| race tried {g('race_tried')} evals {g('race_eval')} reorders {g('race_reorders')} "
              f"errors {g('race_errors')} fb {g('layer_fallbacks')}")
        rows.append((role, times))
    return 0


if __name__ == "__main__":
    sys.exit(main())
