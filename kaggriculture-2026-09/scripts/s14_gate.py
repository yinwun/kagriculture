#!/usr/bin/env python
"""S1.4 gate: per-seed θ agents (multiset vs ordered cash-gated market) vs the champion.

Fixes a Task-11 flaw: the panel spanned four towns but every agent used θ compiled from
seed 9000 only, so for the other towns the unit actions came from a foreign trace.  Here
each town gets an agent compiled from its OWN trace, which is the correct test of the
representation.

Usage: .venv/bin/python scripts/s14_gate.py --modes hybrid cg --seeds 9000-9003
"""
from __future__ import annotations

import argparse
import importlib.util
import json
import statistics as st
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))
import compile_plan  # noqa: E402
import plan_runtime  # noqa: E402

_spec = importlib.util.spec_from_file_location("daygap", ROOT / "scripts" / "day_gap.py")
daygap = importlib.util.module_from_spec(_spec)
sys.modules["daygap"] = daygap
_spec.loader.exec_module(daygap)

CH = str(ROOT / "data" / "tapeopt" / "rgcs" / "main.py")


def _agent(path):
    ns = {"__name__": "s14_" + Path(path).parent.name}
    exec(compile(Path(path).read_text(), str(path), "exec"), ns)
    return ns["agent"]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--modes", nargs="+", default=["hybrid", "cg"])
    ap.add_argument("--seeds", default="9000-9003")
    ap.add_argument("--out", default=str(ROOT / "data" / "plan" / "s14-gate.json"))
    a = ap.parse_args()
    lo, _, hi = a.seeds.partition("-")
    seeds = list(range(int(lo), int(hi) + 1))
    from kaggle_environments import make
    base = _agent(CH)
    results = {}
    for mode in a.modes:
        rows = []
        for seed in seeds:
            trace = ROOT / "data" / "trace" / f"wool_drain1_outerprem-{seed}"
            theta_path = ROOT / "data" / "plan" / f"theta-{seed}.json"
            if not theta_path.exists():
                theta_path.write_text(json.dumps(compile_plan.compile_trace(str(trace))))
            agent_path = plan_runtime.build(str(theta_path), mode, str(trace),
                                            ROOT / "data" / "plan" / "agents" /
                                            f"{mode}-{seed}.py")
            cand = _agent(str(agent_path))
            for seat in (0, 1):
                env = make("kaggriculture", configuration={"episodeSteps": 720, "seed": seed})
                env.run([cand, base] if seat == 0 else [base, cand])
                tr = []
                for t, step in enumerate(env.steps):
                    if t % 24 != 23 and t != len(env.steps) - 1:
                        continue
                    obs = step[0]["observation"]
                    tr.append((t // 24, daygap._worth(obs, seat) - daygap._worth(obs, 1 - seat)))
                rows.append({"seed": seed, "seat": seat, "trace": tr,
                             "final": env.steps[-1][seat]["reward"] - env.steps[-1][1 - seat]["reward"]})
        days = sorted({d for r in rows for d, _ in r["trace"]})
        curve = []
        for d in days:
            vals = [dict(r["trace"])[d] for r in rows if d in dict(r["trace"])]
            curve.append({"day": d, "delta": st.mean(vals),
                          "sd": st.stdev(vals) if len(vals) > 1 else 0.0,
                          "pos": sum(1 for v in vals if v > 0), "n": len(vals)})
        first = next((r["day"] for r in curve if r["delta"] < 0 and r["sd"] > 0
                      and abs(r["delta"]) > r["sd"] / max(1, r["n"]) ** 0.5), None)
        final = st.mean([r["final"] for r in rows])
        results[mode] = {"curve": curve, "final": final, "first_loss_day": first,
                         "games": len(rows)}
        print(f"=== mode {mode}: {len(rows)} games, final {final:+,.0f}, first real deficit day {first}")
        for r in curve:
            if r["day"] <= 12:
                print(f"   day {r['day']:2d} delta {r['delta']:>10,.0f} sd {r['sd']:>8,.0f} "
                      f"pos {r['pos']}/{r['n']}")
    Path(a.out).write_text(json.dumps(results, indent=1))
    print("wrote", a.out)
    return 0


if __name__ == "__main__":
    sys.exit(main())
