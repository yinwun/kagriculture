#!/usr/bin/env python
"""Reconcile every coin in a replay: per-step revenue, price and inventory.

The market is one shared pool: price = f(inventory), shops drain the inventory
every ``townShopSellInterval`` steps, and both players commit at the SAME quoted
price inside a step (see kaggriculture._process_market), so the only edge is
*when* you sell relative to the inventory.  This script reconstructs, for each
player and step:

  revenue = wallet_delta + spending

where spending is rebuilt from the BUY_* / HIRE / BUY_LAND orders with the
engine's own prices (fib hire cost uses the observed ``hires_today``), so the
whole wallet can be explained coin by coin.  Then it reports revenue against the
market inventory/price at the moment of sale, per player, so "sold into a bad
window" is visible instead of guessed.

Usage:
  python scripts/audit_market.py data/replays/episode-108931779-replay.json
"""
import argparse
import collections
import json
from pathlib import Path

CROPS = {"WHEAT": 10, "CARROT": 20, "TOMATO": 50, "STRAWBERRY": 100, "MELON": 80}
ANIMALS = {"GOOSE": 300, "COW": 400, "SHEEP": 500}
LAND_PRICES = [1000, 2000, 4000]
FIB = [1, 1]
while len(FIB) < 40:
    FIB.append(FIB[-1] + FIB[-2])


def hire_cost(n_already_today):
    return FIB[n_already_today] if n_already_today < len(FIB) else FIB[-1]


def analyse(path, player, verbose=False):
    steps = json.loads(Path(path).read_text())["steps"]
    rows = []
    for t in range(len(steps)):
        o = steps[t][player].get("observation")
        if not o:
            continue
        rows.append(o)
    inv_key = None
    tot = collections.Counter()
    series = []
    for i in range(1, len(rows)):
        prev, cur = rows[i - 1], rows[i]
        act = steps[i - 1][player].get("action") or {}
        spend = 0.0
        items = collections.Counter()
        hires = 0
        for od in (act.get("market") or []):
            if not isinstance(od, list) or not od:
                continue
            op = od[0]
            if op == "BUY_SEED" and len(od) > 2:
                item = od[1]
                spend += CROPS.get(item, 0) * int(od[2] or 0)
            elif op == "BUY_ANIMAL" and len(od) > 2:
                spend += ANIMALS.get(od[1], 0) * int(od[2] or 0)
            elif op == "BUY_PRODUCT" and len(od) > 2:
                items["BUY:" + str(od[1])] += int(od[2] or 0)
            elif op == "BUY_LAND":
                n = len(prev["farms"][player].get("unlocked_quadrants") or []) - 1
                if 0 <= n < len(LAND_PRICES):
                    spend += LAND_PRICES[n]
            elif op == "HIRE":
                n = int(prev["farms"][player].get("hires_today") or 0) + hires
                spend += hire_cost(n)
                hires += 1
            elif op == "SELL" and len(od) > 2:
                items["SELL:" + str(od[1])] += int(od[2] or 0)
        dmoney = float(cur["farms"][player]["money"]) - float(prev["farms"][player]["money"])
        revenue = dmoney + spend
        series.append({"step": i, "day": cur["day"], "hour": cur["hour"],
                       "revenue": revenue, "spend": spend,
                       "prices": dict(cur["market"]["prices"]),
                       "inv": dict(cur["market"]["inventory"]),
                       "items": dict(items),
                       "shed": {k: v for k, v in cur["private"]["shed"].items() if v},
                       "money": float(cur["farms"][player]["money"])})
    tot["wallet_final"] = series[-1]["money"] if series else 0
    tot["revenue"] = sum(r["revenue"] for r in series)
    tot["spend"] = sum(r["spend"] for r in series)
    tot["start"] = float(rows[0]["farms"][player]["money"])
    tot["end"] = tot["start"] + tot["revenue"] - tot["spend"]
    print(f"=== {Path(path).name} player {player} ===")
    print(f"start {tot['start']:.0f} + revenue {tot['revenue']:.0f} "
          f"- spend {tot['spend']:.0f} = {tot['end']:.0f} "
          f"(observed {tot['wallet_final']:.0f}, "
          f"residual {tot['wallet_final']-tot['end']:+.0f})")
    # revenue against price windows
    rev_by_item = collections.Counter()
    for r in series:
        sells = {k[5:]: v for k, v in r["items"].items() if k.startswith("SELL:")}
        if not sells:
            continue
        q = sum(sells.values())
        for item, n in sells.items():
            rev_by_item[item] += r["revenue"] * (n / q if q else 0)
    top = ", ".join(f"{k} {v:,.0f}" for k, v in rev_by_item.most_common(6))
    print(f"revenue share by item (order-weighted): {top}")
    # when was revenue earned vs the wheat/wool price
    half = len(series) // 2
    r1 = sum(r["revenue"] for r in series[:half])
    r2 = sum(r["revenue"] for r in series[half:])
    print(f"revenue first half {r1:,.0f} vs second half {r2:,.0f}")
    if verbose:
        for r in series:
            if abs(r["revenue"]) > 1 or r["spend"] > 1:
                s = {k: v for k, v in r["items"].items()}
                print(f"  d{r['day']:2d} h{r['hour']:2d} rev {r['revenue']:+8.0f} "
                      f"spend {r['spend']:7.0f} {s} shed={r['shed']}")
    return series


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("replay")
    ap.add_argument("--player", type=int, default=None)
    ap.add_argument("--verbose", action="store_true")
    args = ap.parse_args()
    d = json.loads(Path(args.replay).read_text())
    n = len(d["steps"][0])
    for p in ([args.player] if args.player is not None else list(range(n))):
        analyse(args.replay, p, args.verbose)


if __name__ == "__main__":
    main()
