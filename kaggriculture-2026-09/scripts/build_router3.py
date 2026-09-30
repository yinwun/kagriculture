#!/usr/bin/env python
"""Build the drain-aware router by REPLACING the source _router function.

scripts/build_router2.py patched the chassis instance at import time
(``_IMPL.chassis.router = ...``), which the ladder rejected with
SubmissionStatus.ERROR even though it ran fine in 14 local games.  This builder
instead rewrites the tape's own ``_router(observation, step, state)`` -- the
function the chassis is constructed with -- so nothing is monkey-patched and the
agent's import path is identical to the production submission that is COMPLETE.

Criterion (see REPORT-ongoing-crop-gap.md section 10): shops drain a FIXED
quantity per day, so any product whose output exceeds that drain accumulates
inventory without bound and its price falls to the floor.  Score each of our
tapes by

    sum over animal products of  own_output/day <= half the drain
                                 ? own_output/day * price : 0

where the drain comes from the shops unlocked so far plus the expected drain of
the shops still to come, and keep the stock decision timing (day 6 once, day 27
switch to tape 2).

Usage:
  python scripts/build_router3.py --out data/tapeopt/router3
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

NEW_ROUTER = '''_RT3_SHOPS = {
    "BAKERY":         ["EGG", "WHEAT"],
    "PIZZA_SHOP":     ["MILK", "TOMATO", "WHEAT"],
    "BRUNCH_SPOT":    ["EGG", "WHEAT", "STRAWBERRY"],
    "YARN_STORE":     ["WOOL"],
    "ICE_CREAM_SHOP": ["STRAWBERRY", "MILK", "WHEAT"],
    "PET_CAFE":       ["CARROT"],
    "SMOOTHIE_SHOP":  ["STRAWBERRY", "MILK"],
    "FARMERS_MARKET": ["WHEAT", "CARROT", "TOMATO", "STRAWBERRY"],
}
_RT3_ANIMAL = {"COW": ("MILK", 1.0), "GOOSE": ("EGG", 2.0), "SHEEP": ("WOOL", 0.667)}
_RT3_MAX_SHOPS = 8


def _rt3_pick(observation):
    """Best tape for the shops the town has: never flood a product."""
    shops = _get(_get(observation, "town", {}), "unlocked_shops", []) or []
    if not shops:
        return None
    drain = {}
    for name in shops:
        items = _RT3_SHOPS.get(name)
        if not items:
            continue
        mult = 2 if len(items) == 1 else 1
        for it in items:
            drain[it] = drain.get(it, 0.0) + mult * 6.0        # 24/4 steps a day
    extra = max(0, _RT3_MAX_SHOPS - len(shops))
    for items in _RT3_SHOPS.values():
        mult = 2 if len(items) == 1 else 1
        for it in items:
            drain[it] = drain.get(it, 0.0) + mult * 6.0 * extra / 8.0
    prices = _get(_get(observation, "market", {}), "prices", {}) or {}
    best, best_v = None, -1.0
    for rid, mix in _RT3_TAPES.items():
        v = 0.0
        for animal, n in mix.items():
            item, rate = _RT3_ANIMAL.get(animal, (None, 0.0))
            if item is None or not n:
                continue
            own = n * rate
            if own <= 0.5 * drain.get(item, 0.0):
                v += own * float(prices.get(item, 0) or 0)
        if v > best_v:
            best_v, best = v, rid
    return best


def _router(observation, step, state):
    if step >= 648 and not state.get('day27'):
        state['route'] = 2
        state['day27'] = True
    elif step >= 144 and not state.get('day6'):
        try:
            rid = _rt3_pick(observation)
        except Exception:
            rid = None
        state['route'] = rid if rid is not None else 0
        state['day6'] = True
    return state.get('route', 0)
'''


def load(path=BASE):
    src = Path(path).read_text()
    m = re.search(r"b85decode\('([^']+)'\)", src)
    data = json.loads(zlib.decompress(base64.b85decode(m.group(1))))
    return src, m, data


def tape_mixes(data):
    out = {}
    for rid in sorted(int(k) for k in data["routes"]):
        mix = collections.Counter()
        for i in data["routes"][str(rid)]:
            for od in (data["actions"][i].get("market") or []):
                if isinstance(od, list) and len(od) >= 3 and od[0] == "BUY_ANIMAL":
                    mix[od[1]] += int(od[2] or 0)
        out[rid] = dict(mix)
    return {int(k): v for k, v in out.items()}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default="data/tapeopt/router3")
    args = ap.parse_args()
    src, m, data = load()
    mixes = tape_mixes(data)
    tables = ("_RT3_TAPES = {int(k): v for k, v in "
              + json.dumps({str(k): v for k, v in mixes.items()}, sort_keys=True)
              + ".items()}\n\n\n")
    # replace the source router wholesale, keeping its decision timing
    pat = re.compile(r"def _router\(observation,step,state\):.*?(?=\n_R42_OPENING)", re.S)
    if not pat.search(src):
        raise SystemExit("could not find the source _router to replace")
    out = pat.sub(tables + NEW_ROUTER + "\n", src, count=1)
    d = ROOT / args.out
    d.mkdir(parents=True, exist_ok=True)
    (d / "main.py").write_text(out)
    print(f"replaced _router in place; wrote {d/'main.py'} ({len(out):,} bytes); "
          f"{len(mixes)} tapes, {len({json.dumps(v, sort_keys=True) for v in mixes.values()})} mixes")


if __name__ == "__main__":
    main()
