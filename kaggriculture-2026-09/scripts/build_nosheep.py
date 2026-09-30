#!/usr/bin/env python
"""Build a "no sheep" tape variant: drop the SHEEP purchases entirely.

Why
---
The rank-1 team runs cows only (scripts/profile_top.py: animals COW:9, no sheep,
no geese) and beats us 116,557 - 95,028 with WATER 1,313 vs 1,100, FERTILIZE 177
vs 104 and PASS 58 vs 483.  Sheep look like the worst line in our tapes:

  * WOOL finishes at 1 coin (base 200) in most of our games -- the wool drain is
    one YARN_STORE (12/day) against two players making ~7/day each, so the price
    floors (see REPORT-ongoing-crop-gap.md section 10);
  * every sheep eats 1 WHEAT a day, and wheat is worth 21-31 coins, so 11 sheep
    burn ~275 coins/day of feed to produce ~7 wool worth ~7 coins;
  * the sheep cost 5,500 coins up front.

Removing the BUY_ANIMAL SHEEP orders is a pure market-order edit: the tape's
PLACE/FEED/CARE actions for those tiles become silent no-ops (FEED on an empty
pasture consumes nothing), and the wheat that used to be eaten stays in the shed
and is sold by the tape's own sell plan.

Usage:
  python scripts/build_nosheep.py --out data/tapeopt/nosheep [--keep-goose]
"""
import argparse
import base64
import copy
import json
import re
import zlib
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
BASE = (ROOT / "data" / "league" /
        "ahmedberatozer_kaggriculture-v42-production-that-fits-the-marke" / "main.py")


def load(path=BASE):
    src = Path(path).read_text()
    m = re.search(r"b85decode\('([^']+)'\)", src)
    data = json.loads(zlib.decompress(base64.b85decode(m.group(1))))
    return src, m, data


def dump(data):
    return base64.b85encode(zlib.compress(
        json.dumps(data, separators=(",", ":")).encode(), 9)).decode()


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default="data/tapeopt/nosheep")
    ap.add_argument("--drop", default="SHEEP", help="comma list of animals to not buy")
    ap.add_argument("--no-feed-buy", action="store_true",
                    help="also drop BUY_PRODUCT WHEAT (its only purpose is feeding)")
    args = ap.parse_args()
    drop = {a.strip() for a in args.drop.split(",") if a.strip()}
    src, m, data = load()
    actions, routes = data["actions"], data["routes"]
    changed = 0
    for rid, idxs in routes.items():
        for pos, ai in enumerate(idxs):
            a = actions[ai]
            mkt = a.get("market") or []
            hit = any(isinstance(o, list) and len(o) >= 3 and o[0] == "BUY_ANIMAL"
                      and o[1] in drop for o in mkt)
            if args.no_feed_buy:
                hit = hit or any(isinstance(o, list) and len(o) >= 3
                                 and o[0] == "BUY_PRODUCT" and o[1] == "WHEAT"
                                 for o in mkt)
            if not hit:
                continue
            new = copy.deepcopy(a)
            new["market"] = [o for o in mkt
                             if not (isinstance(o, list) and len(o) >= 3
                                     and o[0] == "BUY_ANIMAL" and o[1] in drop)
                             and not (args.no_feed_buy and isinstance(o, list)
                                      and len(o) >= 3 and o[0] == "BUY_PRODUCT"
                                      and o[1] == "WHEAT")]
            actions.append(new)
            routes[rid][pos] = len(actions) - 1
            changed += 1
    out = src[:m.start(1)] + dump(data) + src[m.end(1):]
    d = ROOT / args.out
    d.mkdir(parents=True, exist_ok=True)
    (d / "main.py").write_text(out)
    print(f"dropped {changed} BUY_ANIMAL orders for {sorted(drop)}; "
          f"actions {len(actions)}, wrote {d/'main.py'} ({len(out):,} bytes)")


if __name__ == "__main__":
    main()
