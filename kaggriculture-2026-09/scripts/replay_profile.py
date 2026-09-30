#!/usr/bin/env python
"""Profile a kaggriculture replay: what did each agent actually do?

Usage:
    python scripts/replay_profile.py <replay.json> [<replay.json> ...]

Prints per agent: final money, money curve checkpoints, farmer/hand op mix,
market op mix by product, land/hire timeline, crop & animal build-up.
"""
import json
import sys
from collections import Counter, defaultdict
from pathlib import Path

FARMER_OPS = {
    "PASS", "NORTH", "SOUTH", "EAST", "WEST", "PLANT", "WATER", "HARVEST",
    "FERTILIZE", "DIG", "BUILD_COOP", "BUILD_PASTURE", "PLACE", "PICKUP",
    "DROP", "FEED", "COLLECT_FERTILIZER", "CARE",
}


def op_of(action):
    if isinstance(action, list) and action:
        return str(action[0])
    if isinstance(action, str):
        return action
    return None


def profile(path, top_n=12):
    d = json.loads(Path(path).read_text())
    steps = d["steps"]
    names = [a["Name"] for a in d["info"]["Agents"]]
    n = len(steps[0])
    farmer = [Counter() for _ in range(n)]
    market = [Counter() for _ in range(n)]
    market_items = [Counter() for _ in range(n)]
    money = [[] for _ in range(n)]
    sells_by_day = [defaultdict(int) for _ in range(n)]
    crops_planted = [Counter() for _ in range(n)]
    animals_built = [Counter() for _ in range(n)]
    quadrants = [[] for _ in range(n)]
    hires = [Counter() for _ in range(n)]

    for si, step in enumerate(steps):
        day = None
        for p, agent in enumerate(step):
            obs = agent.get("observation") or {}
            day = obs.get("day", day)
            act = agent.get("action")
            if isinstance(act, dict):
                farmer[p][op_of(act.get("farmer"))] += 1
                for h in act.get("hands") or []:
                    farmer[p][op_of(h)] += 1
                for order in act.get("market") or []:
                    op = op_of(order)
                    market[p][op] += 1
                    if op == "SELL" and len(order) > 1:
                        market_items[p][f"SELL {order[1]}"] += 1
                        sells_by_day[p][day] += int(order[2]) if len(order) > 2 else 0
                    elif op == "BUY_SEED" and len(order) > 1:
                        market_items[p][f"BUY_SEED {order[1]}"] += 1
                    elif op == "BUY_ANIMAL" and len(order) > 1:
                        market_items[p][f"BUY_ANIMAL {order[1]}"] += 1
                        animals_built[p][str(order[1])] += 1
                    elif op == "BUY_LAND":
                        market_items[p]["BUY_LAND"] += 1
                    elif op == "HIRE":
                        hires[p][day] += 1
                if op_of(act.get("farmer")) == "PLANT" and len(act["farmer"]) > 1:
                    crops_planted[p][str(act["farmer"][1])] += 1
            farms = obs.get("farms") or []
            if p < len(farms):
                money[p].append(farms[p].get("money", 0))
                uq = farms[p].get("unlocked_quadrants")
                if uq is not None and (not quadrants[p] or quadrants[p][-1][1] != uq):
                    quadrants[p].append((obs.get("day"), uq))

    print("=" * 78)
    print(f"{Path(path).name}  ({len(steps)} steps)")
    for p in range(n):
        m = money[p]
        print("-" * 78)
        print(f"[{p}] {names[p]:<18} final money={m[-1]:>9,.0f} "
              f"(peak {max(m):>9,.0f})")
        marks = [m[min(i, len(m) - 1)] for i in (0, 120, 240, 360, 480, 600, 719)]
        print(f"    money curve  d0={marks[0]:,.0f} d5={marks[1]:,.0f} d10={marks[2]:,.0f} "
              f"d15={marks[3]:,.0f} d20={marks[4]:,.0f} d25={marks[5]:,.0f} d30={marks[6]:,.0f}")
        tot = sum(farmer[p].values()) or 1
        top = ", ".join(f"{k}:{v * 100 // tot}%" for k, v in farmer[p].most_common(8))
        print(f"    farmer ops   {top}")
        print(f"    market ops   {dict(market[p].most_common(8))}")
        print(f"    market items {dict(market_items[p].most_common(top_n))}")
        print(f"    crops planted {dict(crops_planted[p].most_common())}")
        print(f"    animals       {dict(animals_built[p].most_common())}")
        print(f"    quadrants     {quadrants[p]}")
        print(f"    hires by day  {dict(sorted(hires[p].items())[:12])} (total {sum(hires[p].values())})")
        sdays = sorted(sells_by_day[p].items())
        print(f"    units sold/day {[(d, v) for d, v in sdays if v][:14]}")
    return d


if __name__ == "__main__":
    for arg in sys.argv[1:]:
        profile(arg)
