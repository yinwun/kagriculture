#!/usr/bin/env python
"""Build the hybrid: the champion's market layer + plan_v0's labour scheduler.

Split rationale, from the measurements:

  * the champion tape's *market* behaviour is tuned and hard to re-derive: its
    realised prices are wheat 94 (base 25), strawberry 138, melon 239, milk 75,
    fertilizer 72, because it buys feed to drain the wheat pool and meters its
    premium sales.  Every market policy we tried from scratch (dumping, metering,
    holding, price floors, endgame liquidation -- ~12 configs) lost 4x against it.
  * the champion tape's *labour* layer is where we measured it weakest: 7.6% idle
    unit-turns against our scheduler's 2.8%, and a daily watering coverage of ~0.75
    against our 0.80-0.96.

So keep the tape's market orders verbatim (hire/buy/sell schedule) and replace only
the farmer/hands commands with the needs-driven scheduler's plan.  The generated
file is self-contained: plan_v0's source is embedded as a string and exec'd into its
own namespace, so no name collides with the champion's module.

Usage:
  python scripts/build_hybrid.py --out data/hybrid/v0
  python scripts/build_hybrid.py --out data/hybrid/t1 --set hire_mult=3.8
"""
import argparse
import hashlib
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
BASE = ROOT / "data" / "tapeopt" / "rgcs" / "main.py"
PLAN = ROOT / "scripts" / "plan_v0.py"

BEST = {
    "claim_slack": 8, "age_div": 4, "hire_mult": 3.2, "zone_penalty": 2,
    "sell_batch": 20, "plant_scale": 1.2, "strip_penalty": 4,
    "preempt_max_prio": -1, "place_phase_hours": 0, "pen_min_dist": 1,
    "herd_cash_gate": 1, "herd_reserve": 400, "seed_ahead": 1,
    "price_floor_frac": 0.0, "liquidate_day": 99, "sell_order": "ratio",
}

WRAPPER = '''

# ============================ hybrid labour layer ============================
_TAPE_AGENT = agent          # the final agent the module defined above
# The champion's market orders are kept as they are; only the farmer/hands work is
# replaced by the needs-driven scheduler (see scripts/build_hybrid.py for why).
import base64 as _b64
_PLAN_SRC = _b64.b64decode("__PLAN_B64__").decode()
_PLAN_NS = {}
exec(compile(_PLAN_SRC, "<plan_v0>", "exec"), _PLAN_NS)
_HYB = _PLAN_NS["PlanV0"](params=__PARAMS__)
_HYB_ERRORS = [0]


def agent(observation, configuration=None):
    action = _TAPE_AGENT(observation, configuration)
    try:
        plan_action = _HYB.act(observation)
        if isinstance(plan_action, dict) and plan_action.get("farmer"):
            action["farmer"] = plan_action["farmer"]
            action["hands"] = list(plan_action.get("hands") or [])
    except Exception:
        _HYB_ERRORS[0] += 1
    return action
'''


def build(out, params):
    src = BASE.read_text()
    # rename the tape agent so the hybrid can call it, then append the wrapper
    # the champion's file defines `agent` several times, chaining through
    # `_SHOP_PARENT = agent; del agent; def agent(...)`.  Do not rename anything:
    # append a wrapper that captures the module's FINAL agent, then shadows the name.
    assert "def agent(observation, configuration=None):" in src
    plan_src = PLAN.read_text()
    cut = plan_src.find("# ------------------------------------------------------------------ selftest")
    plan_src = plan_src[:cut].replace("import argparse\n", "")
    import base64
    wrapper = (WRAPPER.replace("__PLAN_B64__", base64.b64encode(plan_src.encode()).decode())
                      .replace("__PARAMS__", json.dumps(params, sort_keys=True)))
    text = src + wrapper
    out = Path(out)
    out.mkdir(parents=True, exist_ok=True)
    (out / "main.py").write_text(text)
    ns = {"__name__": "hybrid_check"}
    exec(compile(text, str(out / "main.py"), "exec"), ns)
    assert callable(ns.get("agent")), "hybrid agent is not callable"
    print(f"wrote {out/'main.py'} ({len(text):,} bytes, "
          f"sha256 {hashlib.sha256(text.encode()).hexdigest()[:12]})")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default=str(ROOT / "data" / "hybrid" / "v0"))
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
