#!/usr/bin/env python
"""Build the "scale" variant: buy the 4th quadrant and staff it with 2 new hands.

Why this and not more watering
------------------------------
The crop audit showed the tape is already at 92-100% of the per-crop ceiling
(wheat 3.67/4 units, melon 6/6, strawberry 94% of its 4-production-event max),
0 crops starved, 0 animals escaped, all 75 unlocked tiles in use.  What is NOT
used: the 4th quadrant (SE, 25 tiles, 4000 coins) is never bought even though the
farm ends the game with ~99,000 unspent coins.

Crop choice is driven by the market, not by taste:
  * the town drains the shared inventory only through unlocked shops
    (``townShopSellInterval`` = 4 steps; each shop consumes 1 unit of each of its
    products, 2 units if it sells a single product);
  * MELON turns out to be unsellable-by-design (no shop lists it, so only the
    town centre drains it 1/day) and its price curve above I0 is quadratic
    (``above_func: sq``, target 3.6) -- planting 150 melons would floor the price;
  * STRAWBERRY is the best scale crop: base 120, linear price curve above I0, and
    up to 4 shop instances (BRUNCH_SPOT / ICE_CREAM_SHOP / SMOOTHIE_SHOP /
    FARMERS_MARKET) giving up to ~24 units/day of drain.
  ``--crop auto`` scores every crop from the shops actually unlocked this game.

The tape itself is untouched; like scripts/build_svc12.py this is a runtime layer
that reads real positions from the observation (no position model needed) and
only drives the two hand slots it hires itself.

Usage:
  python scripts/build_scale.py --out data/tapeopt/scale --crop auto
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

# ============================== scale layer ==================================
# Our own addition: unlock the 4th quadrant (SE) and farm it with two extra
# day-laborers running plant -> water -> harvest -> drop cycles.  The tape is
# byte-identical to production; this layer only touches the two hand slots it
# hires itself and the market orders it appends.
_S_CROPS = {
    "WHEAT":      {"first": 2,  "max_day": 4,  "max_yield": 6,  "seed": 10,  "base": 25,  "cycle": 5,  "units": 4},
    "CARROT":     {"first": 2,  "max_day": 3,  "max_yield": 4,  "seed": 20,  "base": 35,  "cycle": 4,  "units": 3},
    "TOMATO":     {"first": 8,  "max_day": 8,  "max_yield": 4,  "seed": 50,  "base": 60,  "cycle": 12, "units": 4, "ongoing": True, "interval": 1},
    "STRAWBERRY": {"first": 10, "max_day": 10, "max_yield": 4,  "seed": 100, "base": 120, "cycle": 18, "units": 8, "ongoing": True, "interval": 2},
    "MELON":      {"first": 10, "max_day": 12, "max_yield": 6,  "seed": 80,  "base": 250, "cycle": 13, "units": 6},
}
_S_CROP_SHOPS = {
    "WHEAT":      ["BAKERY", "PIZZA_SHOP", "BRUNCH_SPOT", "ICE_CREAM_SHOP", "FARMERS_MARKET"],
    "CARROT":     ["PET_CAFE", "FARMERS_MARKET"],
    "TOMATO":     ["PIZZA_SHOP", "FARMERS_MARKET"],
    "STRAWBERRY": ["BRUNCH_SPOT", "ICE_CREAM_SHOP", "SMOOTHIE_SHOP", "FARMERS_MARKET"],
    "MELON":      [],
}
_S_PRODUCTS = ["WHEAT", "CARROT", "TOMATO", "STRAWBERRY", "MELON",
               "EGG", "MILK", "WOOL", "FERTILIZER"]
_S_SHED = [(4, 4), (5, 4), (4, 5), (5, 5)]
_S_SE = lambda x, y: x >= 5 and y >= 5
_S_STATE = {"day": -1, "hired": False, "bought": False, "crop": None, "n": 0,
            "harv": 0, "water": 0, "plant": 0, "drop": 0}
_S_BASE = agent


def _s_score(shops, day):
    """Best crop now: coins per tile-day over the days actually left.

    An unplanted tile earns nothing, so a crop whose first yield lands after
    day 29 is worth nothing, and re-planting crops lose the days they spend as
    seedlings.  Ongoing crops keep producing from one planting, which is why
    they dominate whenever a shop buys them.
    """
    left = max(0, 30 - day)
    out = {}
    for crop, info in _S_CROPS.items():
        n = sum(1 for s in shops if s in _S_CROP_SHOPS.get(crop, []))
        if n == 0 or left <= info["first"]:
            out[crop] = 0.0
            continue
        cycles = 1 if info.get("ongoing") else max(1, (left - info["first"]) // info["cycle"])
        usable = min(cycles, 1) if info.get("ongoing") else cycles
        total = info["units"] * usable * info["base"]
        out[crop] = total / float(max(1, left)) * (1.0 + 0.1 * n)
    return out


def _s_cells(farm, want, day):
    """Tiles of ours in the SE quadrant. want in {'empty','mature','thirsty'}."""
    hits = []
    tiles = farm.get("tiles") or []
    crop = _S_STATE["crop"]
    for y in range(len(tiles)):
        for x in range(len(tiles[y])):
            if not _S_SE(x, y):
                continue
            t = tiles[y][x]
            if want == "empty":
                if t is None:
                    hits.append((x, y))
                continue
            if want == "weedy":
                if t == "WEED":
                    hits.append((x, y))
                continue
            if not isinstance(t, dict) or t.get("kind") != "PLANT" or t.get("crop") != crop:
                continue
            age = day - t.get("planted_day", day)
            info = _S_CROPS[crop]
            if want == "mature":
                if (t.get("yield_units") or 0) > 0 and age >= info["first"]:
                    hits.append((x, y))
            elif want == "thirsty" and not t.get("watered_today"):
                # ENGINE: two consecutive unwatered days turn the plant into a
                # WEED, and the planting day already counts as unwatered, so a
                # keep-alive water is mandatory; the window only adds yield.
                if (t.get("consecutive_unwatered") or 0) >= 1:
                    hits.append((x, y))
                elif not info.get("ongoing"):
                    ws = (info["max_day"] + 1) // 2
                    if ws <= age <= info["max_day"]:
                        hits.append((x, y))
    return hits


def _s_nearest(cells, pos):
    if not cells:
        return None
    return min(cells, key=lambda c: abs(c[0] - pos[0]) + abs(c[1] - pos[1]))


def _s_step(pos, tgt):
    dx, dy = tgt[0] - pos[0], tgt[1] - pos[1]
    if dx:
        return ["EAST" if dx > 0 else "WEST"]
    if dy:
        return ["SOUTH" if dy > 0 else "NORTH"]
    return None


def _s_fert_cells(farm, day):
    """Our tiles whose production fires today but are not fertilized yet."""
    hits = []
    crop = _S_STATE["crop"]
    info = _S_CROPS.get(crop) or {}
    tiles = farm.get("tiles") or []
    for y in range(len(tiles)):
        for x in range(len(tiles[y])):
            if not _S_SE(x, y):
                continue
            t = tiles[y][x]
            if not isinstance(t, dict) or t.get("kind") != "PLANT" or t.get("crop") != crop:
                continue
            if (t.get("fertilized_until_day", -1) or -1) >= day:
                continue
            since = day - t.get("planted_day", day) - info.get("first", 0)
            if since < 0:
                continue
            if since % max(1, info.get("interval", 1)) == 0:
                hits.append((x, y))
    return hits


def _s_animal_cells(farm):
    """Animal tiles that still have fertilizer to collect today."""
    hits = []
    tiles = farm.get("tiles") or []
    for y in range(len(tiles)):
        for x in range(len(tiles[y])):
            t = tiles[y][x]
            if isinstance(t, dict) and "animal" in t and t.get("fertilizer_available"):
                hits.append((x, y))
    return hits


def _s_act(farm, pos, inv, day, hour):
    """One farm hand's action."""
    carry = sum(inv.get(p, 0) for p in _S_PRODUCTS)
    if carry >= 3:
        if tuple(pos) in _S_SHED:
            _S_STATE["drop"] += 1
            return ["DROP"]
        tgt = _s_nearest(_S_SHED, pos)
        return _s_step(pos, tgt) or ["PASS"]
    # fertilize BEFORE watering: the bonus needs both on the same day
    fert = _s_fert_cells(farm, day)
    if fert:
        if inv.get("FERTILIZER", 0) > 0:
            tgt = _s_nearest(fert, pos)
            if tuple(tgt) == tuple(pos):
                _S_STATE["fert"] = _S_STATE.get("fert", 0) + 1
                return ["FERTILIZE"]
            step = _s_step(pos, tgt)
            if step:
                return step
        else:
            src = _s_animal_cells(farm)
            tgt = _s_nearest(src, pos)
            if tgt is not None:
                if tuple(tgt) == tuple(pos):
                    _S_STATE["coll"] = _S_STATE.get("coll", 0) + 1
                    return ["COLLECT_FERTILIZER"]
                step = _s_step(pos, tgt)
                if step:
                    return step
    for want, op in (("mature", "HARVEST"), ("thirsty", "WATER"),
                     ("weedy", "DIG")):
        cells = _s_cells(farm, want, day)
        if not cells:
            continue
        tgt = _s_nearest(cells, pos)
        if tuple(tgt) == tuple(pos):
            if op == "WATER":
                _S_STATE["water"] += 1
            elif op == "DIG":
                _S_STATE["dig"] = _S_STATE.get("dig", 0) + 1
            else:
                _S_STATE["harv"] += 1
            return [op]
        return _s_step(pos, tgt) or ["PASS"]
    empty = _s_cells(farm, "empty", day)
    if empty and _S_STATE["crop"] and hour <= _S_PLANT_HOUR:
        tgt = _s_nearest(empty, pos)
        if tuple(tgt) == tuple(pos):
            _S_STATE["plant"] += 1
            return ["PLANT", _S_STATE["crop"]]
        return _s_step(pos, tgt) or ["PASS"]
    return ["PASS"]


def agent(observation, configuration=None):
    action = _S_BASE(observation, configuration)
    try:
        player = int(observation["player"])
        step = int(observation["step"])
        day, hour = divmod(step, 24)
        if day != _S_STATE["day"]:
            _S_STATE.update(day=day, hired=False)
        farm = observation["farms"][player]
        private = observation.get("private") or {}
        invs = private.get("inventories") or [{}]
        seeds = private.get("seeds") or {}
        mkt = list(action.get("market") or [])
        live = list(farm.get("hands") or [])
        changed = False

        # 1. unlock the 4th quadrant when the farm can afford it
        if (not _S_STATE["bought"] and day >= _S_LAND_DAY and len(mkt) < 10
                and len(farm.get("unlocked_quadrants") or []) < 4
                and float(farm.get("money") or 0) >= _S_LAND_CASH):
            mkt.append(["BUY_LAND"])
            _S_STATE["bought"] = True
            changed = True

        # 2. pick the crop from the shops this town actually unlocked
        if _S_STATE["plant"] == 0 and day <= _S_CROP_DEADLINE:
            shops = (observation.get("town") or {}).get("unlocked_shops") or []
            if _S_STATE["plant"] == 0 and shops:
                score = _s_score(shops, day)
                best = max(score, key=lambda k: score[k])
                if score[best] > 0:
                    _S_STATE["crop"] = best

        # 3. keep seeds in the pool
        crop = _S_STATE["crop"]
        if (seeds.get(crop, 0) < 3 and len(mkt) < 10
                and float(farm.get("money") or 0) >= 1500):
            mkt.append(["BUY_SEED", crop, 3])
            changed = True

        # 4. hire our two hands after the tape's own morning hires (hours 0-6)
        if not _S_STATE["hired"] and hour >= _S_MIN_HOUR and len(mkt) <= 8:
            for _ in range(_S_HANDS):
                mkt.append(["HIRE"])
            _S_STATE["hired"] = True
            changed = True

        if changed:
            action["market"] = mkt
            return action
        if not _S_STATE["hired"] or len(live) < _S_HANDS:
            return action

        hands = list(action.get("hands") or [])
        ks = list(range(len(live) - _S_HANDS, len(live)))
        while len(hands) <= ks[-1]:
            hands.append(["PASS"])
        for k in ks:
            try:
                inv = invs[k + 1] if k + 1 < len(invs) else {}
            except Exception:
                inv = {}
            hands[k] = _s_act(farm, tuple(live[k]), inv, day, hour)
        action["hands"] = hands
    except Exception:
        import os, traceback
        _f = os.environ.get("SCALE_DEBUG")
        if _f:
            with open(_f, "a") as fh:
                fh.write(traceback.format_exc() + "\n")
    return action


agent.telemetry = getattr(_S_BASE, "telemetry", {})
agent.scale_state = _S_STATE
'''


def load_blob(path=BASE):
    src = Path(path).read_text()
    m = re.search(r"b85decode\('([^']+)'\)", src)
    data = json.loads(zlib.decompress(base64.b85decode(m.group(1))))
    return src, m, data


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default="data/tapeopt/scale")
    ap.add_argument("--crop", default="auto")
    ap.add_argument("--min-hour", type=int, default=7)
    ap.add_argument("--land-day", type=int, default=8)
    ap.add_argument("--land-cash", type=float, default=6000.0)
    ap.add_argument("--crop-deadline", type=int, default=14)
    ap.add_argument("--hands", type=int, default=1)
    ap.add_argument("--plant-hour", type=int, default=18)
    args = ap.parse_args()

    src, m, data = load_blob()
    layer = (LAYER.replace("_S_MIN_HOUR", str(args.min_hour))
                  .replace("_S_CROP_DEADLINE", str(args.crop_deadline))
                  .replace("_S_HANDS", str(args.hands))
                  .replace("_S_PLANT_HOUR", str(args.plant_hour))
                  .replace("_S_LAND_DAY", str(args.land_day))
                  .replace("_S_LAND_CASH", str(args.land_cash)))
    if args.crop != "auto":
        layer = layer.replace('_S_STATE["crop"] = best',
                              f'_S_STATE["crop"] = {args.crop!r}')
    out_src = src + layer
    d = ROOT / args.out
    d.mkdir(parents=True, exist_ok=True)
    (d / "main.py").write_text(out_src)
    print(f"wrote {d/'main.py'} ({len(out_src):,} bytes); crop={args.crop} "
          f"min_hour={args.min_hour} land day>={args.land_day} cash>={args.land_cash:g}")


if __name__ == "__main__":
    main()
