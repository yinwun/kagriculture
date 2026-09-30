#!/usr/bin/env python
"""Extract a PLAN SPEC from a replay: what the agent does, not the keystrokes.

A recorded action sequence cannot be replayed (its moves are positional and the
market/opponent/RNG differ), but the *plan* behind it can be re-derived: which
tiles are planted when, how often each crop is watered and fertilised at each
age, how many workers are busy, when land and animals are bought.  That spec is
what we can implement generically with our own closed-loop executor.

Usage:
  python scripts/plan_spec.py data/top/episode-109149804-replay.json --player 0
  python scripts/plan_spec.py data/replays/episode-109299436-replay.json --player 0
"""
import argparse
import collections
import json
from pathlib import Path

CROPS = {"WHEAT": 4, "CARROT": 3, "MELON": 12, "TOMATO": 8, "STRAWBERRY": 10}
ANIMALS = ("GOOSE", "COW", "SHEEP")


def spec(path, player, label=None):
    steps = json.loads(Path(path).read_text())["steps"]
    n = len(steps)
    planted = collections.Counter()          # crop -> count
    plant_day = collections.Counter()        # day -> plants
    alive_day = collections.defaultdict(collections.Counter)
    water_by_age = collections.Counter()     # (crop, age) -> waters
    fert_by_age = collections.Counter()
    opps_by_age = collections.Counter()      # (crop, age) -> days alive
    harvests = collections.Counter()
    units_harvested = 0
    animals_placed = collections.Counter()
    ops_by_day = collections.Counter()
    ops_total = collections.Counter()
    live = {}
    seen_animals = set()
    land_days = []
    prev_quad = None
    prev_units = 0

    for t in range(n):
        ent = steps[t][player]
        obs = ent.get("observation")
        act = ent.get("action") or {}
        if not obs:
            continue
        farm = obs["farms"][player]
        tiles = farm["tiles"]
        day = obs.get("day", t // 24)
        quads = len(farm.get("unlocked_quadrants") or [])
        if prev_quad is None:
            prev_quad = quads
        elif quads != prev_quad:
            land_days.append((day, quads))
            prev_quad = quads
        cmds = [act.get("farmer")] + list(act.get("hands") or [])
        for c in cmds:
            if isinstance(c, list) and c:
                ops_total[c[0]] += 1
                ops_by_day[(day, c[0])] += 1
        # animals placed
        for a in ANIMALS:
            cnt = sum(1 for row in tiles for x in row
                      if isinstance(x, dict) and x.get("animal") == a)
            animals_placed[a] = max(animals_placed[a], cnt)
        for y in range(len(tiles)):
            for x in range(len(tiles[y])):
                cur = tiles[y][x]
                key = (x, y)
                rec = live.get(key)
                if isinstance(cur, dict) and cur.get("kind") == "PLANT":
                    crop = cur.get("crop")
                    if rec is None or rec[0] != crop:
                        live[key] = [crop, cur.get("planted_day", day)]
                        planted[crop] += 1
                        plant_day[day] += 1
                    else:
                        age = day - live[key][1]
                        opps_by_age[(crop, age)] += 1
                        alive_day[day][crop] += 1
                        if cur.get("watered_today"):
                            water_by_age[(crop, age)] += 1
                        if (cur.get("fertilized_until_day", -1) or -1) >= day:
                            fert_by_age[(crop, age)] += 1
                        if (cur.get("yield_units") or 0) > 0 and not rec[2:]:
                            pass
                        if len(live[key]) == 2:
                            live[key].append(cur.get("yield_units") or 0)
                        else:
                            prev_u = live[key][2]
                            u = cur.get("yield_units") or 0
                            if u == 0 and prev_u > 0:
                                units_harvested += prev_u
                                harvests[crop] += 1
                            live[key][2] = u
                else:
                    if rec is not None:
                        if len(rec) > 2 and rec[2] > 0:
                            units_harvested += rec[2]
                            harvests[rec[0]] += 1
                        live.pop(key, None)

    print(f"\n=== PLAN SPEC: {label or Path(path).stem} player {player} ===")
    print(f"plants total {sum(planted.values())}  by crop "
          f"{dict(planted)}   units harvested ~{units_harvested}")
    print(f"animals (peak alive) {dict(animals_placed)}")
    print(f"land unlocks {land_days}")
    print(f"ops total: " + "  ".join(f"{k}:{v}" for k, v in ops_total.most_common(14)))
    # per-unit busiest day: PASS share
    tot = sum(ops_total.values())
    print(f"PASS share {100.0*ops_total.get('PASS',0)/max(1,tot):.1f}%  "
          f"WATER {ops_total.get('WATER',0)}  FERTILIZE {ops_total.get('FERTILIZE',0)}  "
          f"HARVEST {ops_total.get('HARVEST',0)}  PLANT {ops_total.get('PLANT',0)}")
    print("watering coverage by crop age (waters / crop-days alive):")
    for crop in CROPS:
        ages = sorted(a for (c, a) in opps_by_age if c == crop)
        if not ages:
            continue
        row = " ".join(f"d{a}:{water_by_age.get((crop,a),0)}/{opps_by_age[(crop,a)]}"
                       for a in ages[:8])
        print(f"   {crop:11} {row}")
    print("fertilised coverage by crop age (fert days / crop-days alive):")
    for crop in CROPS:
        ages = sorted(a for (c, a) in opps_by_age if c == crop)
        if not ages:
            continue
        row = " ".join(f"d{a}:{fert_by_age.get((crop,a),0)}/{opps_by_age[(crop,a)]}"
                       for a in ages[:8])
        print(f"   {crop:11} {row}")
    print("plants per day (first 12 days with planting): "
          + " ".join(f"d{d}:{c}" for d, c in sorted(plant_day.items())[:12]))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("replay")
    ap.add_argument("--player", type=int, default=0)
    ap.add_argument("--label", default=None)
    args = ap.parse_args()
    spec(args.replay, args.player, args.label)


if __name__ == "__main__":
    main()
