#!/usr/bin/env python
"""Feature table across our own replays: what differs when we win vs lose?

Per replay and player: final wallet, reconciled revenue/spend, animal mix
(geese are the best ROI in the game: 300 coins, +2 EGG/day at 50 coins with
feed+c CARE), and the sheep/cow count.  Printed side by side so win/loss
patterns are visible instead of guessed.

Usage:
  python scripts/game_features.py data/replays/*.json
"""
import argparse
import collections
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from audit_market import analyse  # noqa: E402


def animal_mix(obs, player):
    tiles = obs["farms"][player]["tiles"]
    mix = collections.Counter()
    for row in tiles:
        for t in row:
            if isinstance(t, dict) and "animal" in t:
                mix[t["animal"]] += 1
    return mix


def features(path, player):
    steps = json.loads(Path(path).read_text())["steps"]
    obs = [steps[t][player].get("observation") for t in range(len(steps))]
    obs = [o for o in obs if o]
    last = obs[-1]
    series = []
    # revenue/spend by reconciliation (mirrors scripts/audit_market.py)
    from audit_market import CROPS, ANIMALS, LAND_PRICES, hire_cost
    rev = spend = 0.0
    for i in range(1, len(obs)):
        prev, cur = obs[i - 1], obs[i]
        act = steps[i - 1][player].get("action") or {}
        s = 0.0
        hires = 0
        for od in (act.get("market") or []):
            if not isinstance(od, list) or not od:
                continue
            op = od[0]
            if op == "BUY_SEED" and len(od) > 2:
                s += CROPS.get(od[1], 0) * int(od[2] or 0)
            elif op == "BUY_ANIMAL" and len(od) > 2:
                s += ANIMALS.get(od[1], 0) * int(od[2] or 0)
            elif op == "BUY_LAND":
                n = len(prev["farms"][player].get("unlocked_quadrants") or []) - 1
                if 0 <= n < len(LAND_PRICES):
                    s += LAND_PRICES[n]
            elif op == "HIRE":
                s += hire_cost(int(prev["farms"][player].get("hires_today") or 0) + hires)
                hires += 1
        rev += float(cur["farms"][player]["money"]) - float(prev["farms"][player]["money"]) + s
        spend += s
    return {
        "wallet": float(last["farms"][player]["money"]),
        "revenue": rev,
        "spend": spend,
        "animals": animal_mix(last, player),
        "quadrants": len(last["farms"][player]["unlocked_quadrants"]),
    }


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("replays", nargs="+")
    args = ap.parse_args()
    print(f"{'episode':12}{'P':>2}{'wallet':>9}{'revenue':>10}{'spend':>9}"
          f"{'ROI':>6}{'land':>5}  animals")
    for path in sorted(args.replays):
        d = json.loads(Path(path).read_text())
        n = len(d["steps"][0])
        ep = Path(path).stem.split("-")[1]
        for p in range(n):
            f = features(path, p)
            mix = ",".join(f"{k}:{v}" for k, v in sorted(f["animals"].items()))
            roi = f["revenue"] / max(1.0, f["spend"])
            print(f"{ep:12}{p:>2}{f['wallet']:9.0f}{f['revenue']:10.0f}{f['spend']:9.0f}"
                  f"{roi:6.2f}{f['quadrants']:5d}  {mix}")


if __name__ == "__main__":
    main()
