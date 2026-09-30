#!/usr/bin/env python
"""Build the "drain-cliff" router: keep the stock decision timing, fix the criterion.

Why
---
The stock router decides ONCE at day 6 from the first two unlocked shops:

    shops = tuple(unlocked_shops[:2]); use_new = shops.count('YARN_STORE') <= 0
    route = _R108_SHOP_ROUTES.get(shops, 100) if use_new else _R110_OLD_SHOPS.get(shops, 0)

so a town whose first two shops are (YARN_STORE, BAKERY) is locked onto the
wool-heavy tape even when it later unlocks four ICE_CREAM_SHOPS (MILK drain
30/day).  Episode 109299436 is exactly that case: 11 sheep, wool drained only
12/day, both players made ~7 wool/day, and WOOL finished at **1 coin** while our
other games finished at 139k-152k instead of 99k.

The criterion this layer uses
----------------------------
Shops drain the shared inventory by a FIXED quantity per day, so an item whose
total output exceeds that drain accumulates inventory without bound and its
price falls to the floor -- a cliff, not a slope.  So for each tape we score

    sum over animal products of  (own output/day <= half the drain)
                                 ? own output/day * price : 0

using the drain from the shops unlocked so far plus the expected drain of the
shops still to come (uniform over the 8 shop types).  The timing follows the
stock router (decide once at day 6, switch to tape 2 at day 27), so the animal
plan is never switched out from under the tape mid-game -- that was what made
the first attempt (scripts/build_router.py) lose.

Usage:
  python scripts/build_router2.py --out data/tapeopt/router2
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

# ======================== drain-cliff router layer ===========================
# Our own addition: same one-shot decision timing as the stock router, but the
# criterion is "can the town's shops absorb this tape's animal output at all".
_RT2_SHOPS = {
    "BAKERY":         ["EGG", "WHEAT"],
    "PIZZA_SHOP":     ["MILK", "TOMATO", "WHEAT"],
    "BRUNCH_SPOT":    ["EGG", "WHEAT", "STRAWBERRY"],
    "YARN_STORE":     ["WOOL"],
    "ICE_CREAM_SHOP": ["STRAWBERRY", "MILK", "WHEAT"],
    "PET_CAFE":       ["CARROT"],
    "SMOOTHIE_SHOP":  ["STRAWBERRY", "MILK"],
    "FARMERS_MARKET": ["WHEAT", "CARROT", "TOMATO", "STRAWBERRY"],
}
_RT2_ANIMAL = {"COW": ("MILK", 1.0), "GOOSE": ("EGG", 2.0), "SHEEP": ("WOOL", 0.667)}
_RT2_TAPES = {int(k): v for k, v in __TAPES__.items()}
_RT2_MAX_SHOPS = 8
_RT2_STATE = {"route": None, "picks": 0}


def _rt2_expected_shop(items):
    """Units/day one random shop instance drains, times its chance of appearing."""
    mult = 2 if len(items) == 1 else 1
    p = 1.0 / len(_RT2_SHOPS)
    return {it: mult * 6 * p for it in items}


def _rt2_drain(observation):
    shops = (observation.get("town") or {}).get("unlocked_shops") or []
    drain = {}
    for name in shops:
        items = _RT2_SHOPS.get(name)
        if not items:
            continue
        mult = 2 if len(items) == 1 else 1
        for it in items:
            drain[it] = drain.get(it, 0.0) + mult * 6
    for items in _RT2_SHOPS.values():
        for it, v in _rt2_expected_shop(items).items():
            drain[it] = drain.get(it, 0.0) + v * max(0, _RT2_MAX_SHOPS - len(shops))
    return drain


def _rt2_pick(observation):
    shops = (observation.get("town") or {}).get("unlocked_shops") or []
    if not shops:
        return None
    drain = _rt2_drain(observation)
    prices = (observation.get("market") or {}).get("prices") or {}
    best, best_v = None, -1.0
    for rid, mix in _RT2_TAPES.items():
        v = 0.0
        for animal, n in mix.items():
            item, rate = _RT2_ANIMAL.get(animal, (None, 0.0))
            if item is None or not n:
                continue
            own = n * rate
            cap = 0.5 * drain.get(item, 0.0)          # both players share the drain
            if own <= cap:
                v += own * float(prices.get(item, 0) or 0)
            # else: this product floods the market and ends at the price floor
        if v > best_v:
            best_v, best = v, rid
    return best


def _rt2_router(observation, step, state):
    if step >= 648:
        return 2
    if step < 144:
        return state.get("route", 0)
    if not state.get("rt2_fixed"):
        rid = None
        try:
            rid = _rt2_pick(observation)
        except Exception:
            rid = None
        if rid is not None and rid in _IMPL.chassis.routes:
            state["route"] = rid
            _RT2_STATE["route"] = rid
            _RT2_STATE["picks"] += 1
        state["rt2_fixed"] = True
    return state.get("route", 0)


_IMPL.chassis.router = _rt2_router
agent.router2_report = _RT2_STATE
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
    ap.add_argument("--out", default="data/tapeopt/router2")
    args = ap.parse_args()
    src, m, data = load_blob()
    layer = LAYER.replace("__TAPES__", json.dumps(tape_mixes(data), sort_keys=True))
    out_src = src + layer
    d = ROOT / args.out
    d.mkdir(parents=True, exist_ok=True)
    (d / "main.py").write_text(out_src)
    print(f"wrote {d/'main.py'} ({len(out_src):,} bytes); drain-cliff router installed")


if __name__ == "__main__":
    main()
