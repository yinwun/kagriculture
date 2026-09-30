#!/usr/bin/env python
"""Build the "drain-aware router" variant: pick the tape whose output the town can absorb.

The market finding this comes from
---------------------------------
Auditing final prices across our replays (scripts/audit_market.py + the price
table) shows a systematic loss: we sell FERTILIZER and WOOL at **1 coin**
(base 100 / 200) while MILK stays at 243 (base 160).  The reason is that the
market is shared: price = f(inventory), and the town only drains the shared
inventory through the shops it has unlocked --

    every townShopSellInterval (=4) steps, each unlocked shop consumes 1 unit of
    each product it sells (2 units if it lists a single product)

so a product is only worth producing if the *sum of both players' output* stays
under that drain.  Our 41 tapes differ only in their animal mix (crop seeds are
identical across all of them), and the stock router picks between them by which
shops are present rather than by how much they can absorb:

    episode 109299436 town: 4x ICE_CREAM_SHOP + BAKERY + PIZZA_SHOP + YARN_STORE
      -> MILK drain 30/day, WOOL drain 12/day
      -> it picked the COW6+SHEEP11 (wool) tape, both players made ~7 wool/day,
         the price floored at 1, and revenue came in 38% below our other games.

What this layer does
--------------------
Wraps the chassis' router: each step it scores every tape by
``sum over animal products of min(tape output/day, half the town drain) * price``
and returns the best one, falling back to the original router whenever the town
has no shops yet.  The tape data itself is untouched.

Usage:
  python scripts/build_router.py --out data/tapeopt/router
"""
import argparse
import base64
import collections
import json
import re
import zlib
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
BASE = (ROOT / "data" / "league" /
        "ahmedberatozer_kaggriculture-v42-production-that-fits-the-marke" / "main.py")

LAYER = r'''

# ========================= drain-aware router layer ==========================
# Our own addition: choose between our tapes by how much of their output the
# town's unlocked shops can actually absorb (shared market, price = f(inventory)).
_RT_SHOPS = {
    "BAKERY":         ["EGG", "WHEAT"],
    "PIZZA_SHOP":     ["MILK", "TOMATO", "WHEAT"],
    "BRUNCH_SPOT":    ["EGG", "WHEAT", "STRAWBERRY"],
    "YARN_STORE":     ["WOOL"],
    "ICE_CREAM_SHOP": ["STRAWBERRY", "MILK", "WHEAT"],
    "PET_CAFE":       ["CARROT"],
    "SMOOTHIE_SHOP":  ["STRAWBERRY", "MILK"],
    "FARMERS_MARKET": ["WHEAT", "CARROT", "TOMATO", "STRAWBERRY"],
}
# units/day each animal produces once cared for (interval + care bonus)
_RT_ANIMAL = {"COW": ("MILK", 1.0), "GOOSE": ("EGG", 2.0), "SHEEP": ("WOOL", 0.667)}
_RT_TAPE = {int(k): v for k, v in __TAPES__.items()}   # route id -> animal counts
_RT_STATE = {"route": None, "day": -1, "switches": 0}
_RT_BASE_ROUTER = _IMPL.chassis.router


def _rt_pick(observation):
    town = observation.get("town") or {}
    shops = town.get("unlocked_shops") or []
    if not shops:
        return None
    drain = collections.Counter() if False else {}
    for name in shops:
        items = _RT_SHOPS.get(name)
        if not items:
            continue
        mult = 2 if len(items) == 1 else 1
        for it in items:
            drain[it] = drain.get(it, 0) + mult * 6      # 24/4 steps per day
    prices = (observation.get("market") or {}).get("prices") or {}
    best, best_v = None, -1.0
    for rid, mix in _RT_TAPE.items():
        v = 0.0
        for animal, n in mix.items():
            item, rate = _RT_ANIMAL.get(animal, (None, 0.0))
            if item is None or not n:
                continue
            # both players sell into the same pool: we can only count on half
            v += min(n * rate, 0.5 * drain.get(item, 0)) * float(prices.get(item, 0) or 0)
        if v > best_v:
            best_v, best = v, rid
    return best


def _rt_router(observation, step, state):
    try:
        rid = _rt_pick(observation)
        if rid is not None and rid in _IMPL.chassis.routes:
            if rid != _RT_STATE["route"]:
                _RT_STATE["switches"] += 1
                _RT_STATE["route"] = rid
            return rid
    except Exception:
        pass
    return _RT_BASE_ROUTER(observation, step, state)


_IMPL.chassis.router = _rt_router
if hasattr(_IMPL, "chassis"):
    try:
        _IMPL.chassis.router_state = {}
    except Exception:
        pass
agent.router_state_report = _RT_STATE
'''


def load_blob(path=BASE):
    src = Path(path).read_text()
    m = re.search(r"b85decode\('([^']+)'\)", src)
    data = json.loads(zlib.decompress(base64.b85decode(m.group(1))))
    return src, m, data


def tape_mixes(data):
    out = {}
    for rid in sorted(int(k) for k in data["routes"]):
        tape = [data["actions"][i] for i in data["routes"][str(rid)]]
        mix = collections.Counter()
        for act in tape:
            for od in (act.get("market") or []):
                if isinstance(od, list) and len(od) >= 3 and od[0] == "BUY_ANIMAL":
                    mix[od[1]] += int(od[2] or 0)
        out[rid] = dict(mix)
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default="data/tapeopt/router")
    args = ap.parse_args()
    src, m, data = load_blob()
    mixes = tape_mixes(data)
    layer = LAYER.replace("__TAPES__", json.dumps(mixes, sort_keys=True))
    out_src = src + layer
    d = ROOT / args.out
    d.mkdir(parents=True, exist_ok=True)
    (d / "main.py").write_text(out_src)
    print(f"wrote {d/'main.py'} ({len(out_src):,} bytes); {len(mixes)} tapes, "
          f"{len({json.dumps(v, sort_keys=True) for v in mixes.values()})} distinct animal mixes")


if __name__ == "__main__":
    main()
