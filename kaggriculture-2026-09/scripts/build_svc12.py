#!/usr/bin/env python
"""Build the "service hand" variant: V42 tape untouched + our own runtime layer.

Why a runtime layer instead of tape surgery
-------------------------------------------
Hands in kaggriculture are day-laborers: HIRE appends to farm["hands"] and the
list is cleared at every day rollover, so action slot k means "the k-th hand
hired *today*".  A tape edit that re-plans a slot's path therefore hits a
different physical worker on different days (that is why the static generator
landed only 15 of 308 waters).  A runtime layer reads the real positions from
the observation, so no position model is needed.

What the layer does
-------------------
* hires ONE extra hand per day, at the first step with hour >= 7 whose market
  queue still has room (all of the tape's own hires happen at hours 0-6, so this
  hand is always the last one hired that day and the tape's slot mapping is
  untouched);
* drives that one hand only: walk to the nearest unwatered ongoing crop
  (STRAWBERRY / TOMATO) and WATER it, all day.

Engine fact this exploits: for ongoing crops the daily production is +1 no
matter what, but ``fertilized = was_watered and fertilized_until_day >= day``
makes it +2.  So a water on a fertilized day is worth one extra unit of a
120-coin crop, while our tape leaves ~50% of ongoing-crop days unwatered.

Usage:
  python scripts/build_svc12.py --out data/tapeopt/svc12 --crops STRAWBERRY,TOMATO
"""
import argparse
import base64
import json
import re
import zlib
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
BASE = (ROOT / "data" / "league" /
        "ahmedberatozer_kaggriculture-v42-production-that-fits-the-marke" / "main.py")

LAYER = r'''

# ============================ service-hand layer =============================
# Our own addition: one extra day-laborer that only services ongoing crops
# (water on fertilized days is worth a full extra unit; see the module docstring
# of scripts/build_svc12.py).  The tape itself is byte-identical to production.
_SVC_CROPS = __CROPS__
_SVC_MIN_HOUR = __MIN_HOUR__
_SVC_MAX_ORDERS = 10
_SVC_STATE = {"day": -1, "mine": False, "hired_at": None, "waters": 0}
_SVC_BASE = agent


def _svc_pick(farm, pos):
    """Nearest unwatered ongoing-crop tile (Manhattan)."""
    best = None
    bd = None
    tiles = farm.get("tiles") or []
    for y, row in enumerate(tiles):
        for x, t in enumerate(row):
            if not isinstance(t, dict) or t.get("kind") != "PLANT":
                continue
            if t.get("crop") not in _SVC_CROPS or t.get("watered_today"):
                continue
            d = abs(x - pos[0]) + abs(y - pos[1])
            if bd is None or d < bd:
                bd = d
                best = (x, y)
    return best, bd


def agent(observation, configuration=None):
    action = _SVC_BASE(observation, configuration)
    try:
        player = int(observation["player"])
        step = int(observation["step"])
        day, hour = divmod(step, 24)
        if day != _SVC_STATE["day"]:
            _SVC_STATE.update(day=day, mine=False, hired_at=None)
        farm = observation["farms"][player]
        live = list(farm.get("hands") or [])
        mkt = list(action.get("market") or [])
        if not _SVC_STATE["mine"] and hour >= _SVC_MIN_HOUR and len(mkt) < _SVC_MAX_ORDERS:
            mkt.append(["HIRE"])
            _SVC_STATE.update(mine=True, hired_at=step)
            action["market"] = mkt
            return action
        if not _SVC_STATE["mine"] or not live:
            return action
        k = len(live) - 1                     # our hand is the last one hired
        if step <= (_SVC_STATE["hired_at"] or -1):
            return action
        hands = list(action.get("hands") or [])
        while len(hands) <= k:
            hands.append(["PASS"])
        pos = tuple(live[k])
        tgt, dist = _svc_pick(farm, pos)
        if tgt is not None:
            if dist == 0:
                hands[k] = ["WATER"]
                _SVC_STATE["waters"] += 1
            else:
                dx = tgt[0] - pos[0]
                dy = tgt[1] - pos[1]
                if dx:
                    hands[k] = ["EAST" if dx > 0 else "WEST"]
                else:
                    hands[k] = ["SOUTH" if dy > 0 else "NORTH"]
        action["hands"] = hands
    except Exception:
        pass
    return action


agent.telemetry = getattr(_SVC_BASE, "telemetry", {})
'''


def load_blob(path=BASE):
    src = Path(path).read_text()
    m = re.search(r"b85decode\('([^']+)'\)", src)
    data = json.loads(zlib.decompress(base64.b85decode(m.group(1))))
    return src, m, data


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default="data/tapeopt/svc12")
    ap.add_argument("--crops", default="STRAWBERRY,TOMATO")
    ap.add_argument("--min-hour", type=int, default=7)
    args = ap.parse_args()

    src, m, data = load_blob()
    crops = [c.strip() for c in args.crops.split(",") if c.strip()]
    layer = LAYER.replace("__CROPS__", repr(tuple(crops))).replace(
        "__MIN_HOUR__", str(args.min_hour))

    out_src = src + layer
    d = ROOT / args.out
    d.mkdir(parents=True, exist_ok=True)
    (d / "main.py").write_text(out_src)
    print(f"wrote {d/'main.py'} ({len(out_src):,} bytes); crops={crops} "
          f"min_hour={args.min_hour}; tape untouched "
          f"({len(data['routes'])} routes, {len(data['actions'])} actions)")


if __name__ == "__main__":
    main()
