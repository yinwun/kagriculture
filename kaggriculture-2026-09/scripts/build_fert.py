#!/usr/bin/env python
"""Build the "fertilizer hand" variant: spend the fertilizer instead of dumping it.

The market finding this comes from
---------------------------------
Reconciling every coin of our replays (scripts/audit_market.py) shows we finish
games with FERTILIZER at **1 coin** (base 100) and WOOL at 1 coin (base 200),
because we dump everything into a shared market whose shops can only drain
12-30 units/day, while MILK/EGG stay above base (243 vs 160) because their drain
is larger.  Selling fertilizer is therefore worth ~nothing; using it is worth a
lot:

  engine: bonus = 2 if tile["fertilized_until_day"] >= day else 1
          yield_units = min(max_yield, yield_units + bonus)   # on a WATER

  so one FERTILIZE (covers day, day+1, day+2) placed on the first day of a
  crop's effective window doubles the yield of every watering inside it:
  WHEAT 3.67 -> up to 6 units, CARROT 2.79 -> 4, MELON already capped.

Measured on episode-109299436: wheat is fertilized on only ~15% of its tile-days
(73.6 tile-days of ~495 possible) while 377 fertilizer are collected and dumped.

The layer (tape untouched, same pattern as build_svc12/build_scale)
------------------------------------------------------------------
* hires ONE extra hand per day (hours >= 7, after the tape's own hires, so the
  tape's hand slots keep their mapping);
* that hand keeps FERTILIZER in its own inventory (PICKUP from the shed, which is
  already overflowing with it) and walks the non-ongoing crop tiles, applying
  FERTILIZE on the first day of each tile's effective window;
* nothing else is touched: no path is re-planned, no tape action is rewritten.

Usage:
  python scripts/build_fert.py --out data/tapeopt/fert
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

# ============================= fertilizer layer ==============================
# Our own addition: one extra day-laborer that spends the fertilizer the tape is
# dumping at 1 coin on the crops whose windows are not fertilized yet.  Engine:
# a watered day inside the effective window gives +2 instead of +1 when
# fertilized_until_day >= day, and one FERTILIZE covers three days.
_F_TARGETS = {
    "WHEAT":  {"first": 2, "max_day": 4},
    "CARROT": {"first": 2, "max_day": 3},
    "MELON":  {"first": 10, "max_day": 12},
}
_F_SHED = [(4, 4), (5, 4), (4, 5), (5, 5)]
_F_STATE = {"day": -1, "hired": False, "n": 0, "fert": 0, "pick": 0, "walk": 0}
_F_CARRY = 12
_F_BASE = agent


def _f_cells(farm, day, pos):
    """Crop tiles that want fertilizer today: first day of the window, no bonus."""
    hits = []
    tiles = farm.get("tiles") or []
    for y in range(len(tiles)):
        for x in range(len(tiles[y])):
            t = tiles[y][x]
            if not isinstance(t, dict) or t.get("kind") != "PLANT":
                continue
            info = _F_TARGETS.get(t.get("crop"))
            if info is None:
                continue
            age = day - t.get("planted_day", day)
            ws = (info["max_day"] + 1) // 2
            # any day still inside the effective window is worth a FERTILIZE:
            # one application covers day, day+1, day+2, so a later application
            # still doubles the waterings that remain in the window.
            if not (ws <= age <= info["max_day"]):
                continue
            if (t.get("fertilized_until_day", -1) or -1) >= day:
                continue
            hits.append((x, y))
    if not hits:
        return None, None
    tgt = min(hits, key=lambda c: abs(c[0] - pos[0]) + abs(c[1] - pos[1]))
    return tgt, abs(tgt[0] - pos[0]) + abs(tgt[1] - pos[1])


def _f_step(pos, tgt):
    dx, dy = tgt[0] - pos[0], tgt[1] - pos[1]
    if dx:
        return ["EAST" if dx > 0 else "WEST"]
    if dy:
        return ["SOUTH" if dy > 0 else "NORTH"]
    return None


def _f_act(farm, pos, inv, shed, day):
    if inv.get("FERTILIZER", 0) > 0:
        tgt, _d = _f_cells(farm, day, pos)
        if tgt is not None:
            if tuple(tgt) == tuple(pos):
                _F_STATE["fert"] += 1
                return ["FERTILIZE"]
            step = _f_step(pos, tgt)
            if step:
                _F_STATE["walk"] += 1
                return step
        return ["PASS"]
    # out of fertilizer: go reload from the shed (which is dumping it anyway)
    if (shed.get("FERTILIZER", 0) or 0) <= 0:
        return ["PASS"]
    if tuple(pos) in _F_SHED:
        _F_STATE["pick"] += 1
        return ["PICKUP", "FERTILIZER", _F_CARRY]
    tgt = min(_F_SHED, key=lambda c: abs(c[0] - pos[0]) + abs(c[1] - pos[1]))
    step = _f_step(pos, tgt)
    return step or ["PASS"]


def agent(observation, configuration=None):
    action = _F_BASE(observation, configuration)
    try:
        player = int(observation["player"])
        step = int(observation["step"])
        day, hour = divmod(step, 24)
        if day != _F_STATE["day"]:
            _F_STATE.update(day=day, hired=False)
        farm = observation["farms"][player]
        private = observation.get("private") or {}
        shed = private.get("shed") or {}
        invs = private.get("inventories") or [{}]
        mkt = list(action.get("market") or [])
        live = list(farm.get("hands") or [])
        if not _F_STATE["hired"] and hour >= _F_MIN_HOUR and len(mkt) < 10:
            mkt.append(["HIRE"])
            _F_STATE["hired"] = True
            action["market"] = mkt
            return action
        if not _F_STATE["hired"] or not live:
            return action
        k = len(live) - 1
        hands = list(action.get("hands") or [])
        while len(hands) <= k:
            hands.append(["PASS"])
        inv = invs[k + 1] if k + 1 < len(invs) else {}
        hands[k] = _f_act(farm, tuple(live[k]), inv, shed, day)
        action["hands"] = hands
    except Exception:
        import os, traceback
        _f = os.environ.get("FERT_DEBUG")
        if _f:
            with open(_f, "a") as fh:
                fh.write(traceback.format_exc() + "\n")
    return action


agent.telemetry = getattr(_F_BASE, "telemetry", {})
agent.fert_state = _F_STATE
'''


def load_blob(path=BASE):
    src = Path(path).read_text()
    m = re.search(r"b85decode\('([^']+)'\)", src)
    data = json.loads(zlib.decompress(base64.b85decode(m.group(1))))
    return src, m, data


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default="data/tapeopt/fert")
    ap.add_argument("--min-hour", type=int, default=7)
    ap.add_argument("--carry", type=int, default=12)
    args = ap.parse_args()
    src, m, data = load_blob()
    layer = (LAYER.replace("_F_MIN_HOUR", str(args.min_hour))
                  .replace("_F_CARRY = 12", f"_F_CARRY = {args.carry}"))
    out_src = src + layer
    d = ROOT / args.out
    d.mkdir(parents=True, exist_ok=True)
    (d / "main.py").write_text(out_src)
    print(f"wrote {d/'main.py'} ({len(out_src):,} bytes); min_hour={args.min_hour} "
          f"carry={args.carry}; tape untouched")


if __name__ == "__main__":
    main()
