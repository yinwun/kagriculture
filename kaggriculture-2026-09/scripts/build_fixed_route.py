#!/usr/bin/env python
"""Force one tape for the whole game (replaces the source _router in place).

The route sweep (scripts/route_sweep.py) measures each of our 41 tapes on
identical towns; route 101 had the best mean wallet over 8 towns (+2.6% vs
route 0).  This builder makes that a testable agent: day-6 decision replaced by
a constant, day-27 switch kept.

Usage: python scripts/build_fixed_route.py --route 101 --out data/tapeopt/fixed101
"""
import argparse
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
BASE = (ROOT / "data" / "league" /
        "ahmedberatozer_kaggriculture-v42-production-that-fits-the-marke" / "main.py")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--route", type=int, default=101)
    ap.add_argument("--out", default="data/tapeopt/fixed101")
    args = ap.parse_args()
    src = BASE.read_text()
    pat = re.compile(r"def _router\(observation,step,state\):.*?(?=\n_R42_OPENING)", re.S)
    if not pat.search(src):
        raise SystemExit("could not find _router")
    new = ("def _router(observation, step, state):\n"
           "    if step >= 648 and not state.get('day27'):\n"
           "        state['route'] = 2\n"
           "        state['day27'] = True\n"
           "        return 2\n"
           f"    return state.get('route') or {args.route}\n")
    out = pat.sub(new + "\n", src, count=1)
    d = ROOT / args.out
    d.mkdir(parents=True, exist_ok=True)
    (d / "main.py").write_text(out)
    print(f"route forced to {args.route}; wrote {d/'main.py'} ({len(out):,} bytes)")


if __name__ == "__main__":
    main()
