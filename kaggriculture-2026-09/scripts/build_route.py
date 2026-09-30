#!/usr/bin/env python
"""Force the champion onto one fixed route tape (router override).

The champion's `_router` picks a route id from the shop-tuple tables
(`_R108_SHOP_ROUTES` / `_R110_OLD_SHOPS`).  This builder appends a one-line
override of `_IMPL.chassis.router` so a chosen route id is replayed for the whole
game, which is how we test whether the router is leaving a better tape on the
table for a given town draw.  `--route -1` (default) leaves the champion untouched.

Usage: python scripts/build_route.py --route 7 [--out-root data/route]
"""
import argparse
import hashlib
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
CHAMPION = ROOT / "data" / "tapeopt" / "rgcs" / "main.py"


def build(route, out_root=None, name=None, from_step=0, to_step=100000):
    """Force `route` for steps in [from_step, to_step); everything else uses the
    champion's own router.  The cell window is 144..647 (the router reads the day-6
    shop tuple at step 144 and switches to route 2 at step 648), so defaulting to the
    whole game would confound the cell decision with the opening and the end-game."""
    src = CHAMPION.read_text()
    name = name or (f"r{route}" if not from_step and to_step > 1000 else f"r{route}_{from_step}_{to_step}")
    if route is not None and route >= 0:
        src = src.rstrip("\n") + f"""

# route force (scripts/build_route.py): replay route {route} for steps
# [{from_step}, {to_step}); every other step keeps the champion's own router.
_ROUTE_ORIG = _IMPL.chassis.router


def _route_override(observation, step, state, _r={route}, _a={from_step}, _b={to_step}):
    if _a <= step < _b:
        return _r
    return _ROUTE_ORIG(observation, step, state)


_IMPL.chassis.router = _route_override
"""
    compile(src, "route_main.py", "exec")
    root = Path(out_root) if out_root else ROOT / "data" / "route"
    d = root / name
    d.mkdir(parents=True, exist_ok=True)
    target = d / "main.py"
    target.write_text(src)
    print(f"built {target} sha256 {hashlib.sha256(src.encode()).hexdigest()[:12]} route={route}")
    return target


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--route", type=int, default=-1)
    ap.add_argument("--out-root", default=None)
    ap.add_argument("--name", default=None)
    ap.add_argument("--from-step", type=int, default=0)
    ap.add_argument("--to-step", type=int, default=100000)
    a = ap.parse_args()
    build(a.route, a.out_root, a.name, a.from_step, a.to_step)
