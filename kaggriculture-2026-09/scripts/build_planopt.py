#!/usr/bin/env python
"""Package plan_v0 as a standalone agent main.py (so it can be A/B'd and submitted).

plan_v0 lives in scripts/plan_v0.py: a needs-driven day scheduler with 25+ knobs.
The decision instrument (scripts/ab_duel.py) and the ladder both need a single
self-contained main.py exposing `agent(observation, configuration=None)`, so this
builder concatenates the scheduler with a baked-in parameter set and a thin agent
wrapper -- no imports beyond the standard library, no file reads.

Usage:
  python scripts/build_planopt.py --out data/planopt/v0 --preset best
  python scripts/build_planopt.py --out data/planopt/t1 --set hire_mult=3.8 --set sell_batch=20
"""
import argparse
import hashlib
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SRC = ROOT / "scripts" / "plan_v0.py"

# the parameter set that won the sweeps (see REPORT-tape-replan-methodology.md §15-16)
BEST = {
    "claim_slack": 8, "age_div": 4, "hire_mult": 3.2, "zone_penalty": 2,
    "sell_batch": 20, "plant_scale": 1.2, "strip_penalty": 4,
    "preempt_max_prio": -1, "place_phase_hours": 0, "pen_min_dist": 1,
    "herd_cash_gate": 1, "herd_reserve": 400, "seed_ahead": 1,
    "price_floor_frac": 0.5, "liquidate_day": 99,
}

HEADER = '''"""plan_v0 packaged agent -- needs-driven day scheduler (self-contained)."""
'''

FOOTER = '''

# ---------------------------------------------------------------- agent wrapper
_PLAN = PlanV0(params=PARAMS)


def agent(observation, configuration=None):
    return _PLAN.act(observation)
'''


def build(out, params):
    src = SRC.read_text()
    # drop the CLI / selftest tail (the ladder only needs the class + the wrapper)
    cut = src.find("# ------------------------------------------------------------------ selftest")
    if cut == -1:
        raise SystemExit("selftest marker not found in plan_v0.py")
    body = src[:cut]
    # the module docstring mentions imports we no longer need; keep them, they are
    # all standard library and harmless, but drop the argparse-only tail entirely.
    body = body.replace("import argparse\n", "")
    text = HEADER + body + "\nPARAMS = " + json.dumps(params, sort_keys=True) + "\n" + FOOTER
    out = Path(out)
    out.mkdir(parents=True, exist_ok=True)
    (out / "main.py").write_text(text)
    # smoke check: the file must compile and expose a callable agent
    ns = {"__name__": "packaged"}
    exec(compile(text, str(out / "main.py"), "exec"), ns)
    assert callable(ns.get("agent")), "packaged agent is not callable"
    print(f"wrote {out/'main.py'} ({len(text):,} bytes, "
          f"sha256 {hashlib.sha256(text.encode()).hexdigest()[:12]}, "
          f"{len(params)} params)")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default=str(ROOT / "data" / "planopt" / "v0"))
    ap.add_argument("--preset", default="best", choices=["best"])
    ap.add_argument("--set", action="append", default=[])
    args = ap.parse_args()
    params = dict(BEST)
    for item in args.set:
        k, _, v = item.partition("=")
        if v in ("True", "False"):
            params[k] = v == "True"
        else:
            try:
                params[k] = int(v)
            except ValueError:
                try:
                    params[k] = float(v)
                except ValueError:
                    params[k] = v
    build(args.out, params)
    return 0


if __name__ == "__main__":
    sys.exit(main())
