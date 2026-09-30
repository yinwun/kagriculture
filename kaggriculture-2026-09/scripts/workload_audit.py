#!/usr/bin/env python
"""Workload vs crew capacity, per day, from a replay.

The re-planning question is not "copy rank-1's actions" but "what is the daily job
list and can the crew service it".  This audit attributes every command to the tile
the unit is standing on (the replay records unit positions each step), so it can
price the farm's daily demand:

  workload   : tiles that could use water today (one-shot crop in the bonus window,
               yield below max), animal-days needing feed / care / fertiliser,
               ripe crops, and the plants/places the plan wants
  delivered  : commands of each kind actually issued to those tiles
  capacity   : units x steps in the day, split into work and movement

Usage:
  python scripts/workload_audit.py --team Majkel1337
  python scripts/workload_audit.py --team nickyl --days 0,5,10,15,20,25,29
"""
import argparse
import collections
import glob
import json
import statistics
from pathlib import Path

from kaggle_environments.envs.kaggriculture.kaggriculture import CROPS

MOVE = {"NORTH", "SOUTH", "EAST", "WEST"}


def audit(path, p):
    d = json.loads(Path(path).read_text())
    steps = d["steps"]
    daily = collections.defaultdict(collections.Counter)
    seen_water = set()   # (day, tile) already counted as workload
    seen_animal = set()
    for t, entry in enumerate(steps):
        if p >= len(entry):
            continue
        obs = entry[p].get("observation")
        a = entry[p].get("action") or {}
        if not obs:
            continue
        day, hour = obs.get("day", t // 24), t % 24
        farm = obs["farms"][p]
        tiles = farm["tiles"]
        jobs = [a.get("farmer") or ["PASS"]] + list(a.get("hands") or [])
        pos = [farm.get("farmer")] + [list(x) for x in (farm.get("hands") or [])]
        for i, cmd in enumerate(jobs):
            if not (isinstance(cmd, list) and cmd):
                continue
            v = cmd[0]
            daily[day]["CMD"] += 1
            if v in MOVE:
                daily[day]["MOVE"] += 1
            elif v == "PASS":
                daily[day]["PASS"] += 1
            else:
                daily[day][v] += 1
                # attribute to the tile the unit stands on
                if i < len(pos) and isinstance(pos[i], (list, tuple)) and len(pos[i]) >= 2:
                    try:
                        cell = tiles[pos[i][1]][pos[i][0]]
                    except Exception:
                        cell = None
                    if isinstance(cell, dict):
                        cd = CROPS.get(cell.get("crop") or "")
                        if v == "WATER" and cd:
                            daily[day]["water_delivered"] += 1
                        if v in ("FEED", "CARE", "COLLECT_FERTILIZER") and cell.get("animal"):
                            daily[day]["animal_delivered"] += 1
                        if v == "HARVEST" and cell.get("yield_units", 0) > 0:
                            daily[day]["harv_delivered"] += 1
        # workload: one-shot crop tiles that could use water today
        for y, row in enumerate(tiles):
            for x, cell in enumerate(row):
                if not isinstance(cell, dict):
                    continue
                if cell.get("crop"):
                    cd = CROPS.get(cell["crop"])
                    if not cd:
                        continue
                    age = day - cell.get("planted_day", day)
                    if (not cd["ongoing"] and cell.get("yield_units", 0) < cd["max_yield"]
                            and (cd["max_yield_day"] + 1) // 2 <= age <= cd["max_yield_day"]):
                        key = (day, x, y)
                        if key not in seen_water:
                            seen_water.add(key)
                            daily[day]["water_workload"] += 1
                if cell.get("animal"):
                    key = (day, x, y)
                    if key not in seen_animal:
                        seen_animal.add(key)
                        daily[day]["animal_workload"] += 3  # feed + care + fertiliser
        daily[day]["units"] = max(daily[day]["units"], len(pos))
    return daily


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--team", default="Majkel1337")
    ap.add_argument("--other", default="nickyl")
    ap.add_argument("--glob", default="data/top/episode-*.json,data/replays/episode-*.json")
    ap.add_argument("--days", default="0,3,5,10,15,20,25,29")
    args = ap.parse_args()
    days = [int(x) for x in args.days.split(",")]

    paths = []
    for g in args.glob.split(","):
        paths.extend(sorted(glob.glob(g)))
    teams = (args.team, args.other)
    data = {t: [] for t in teams}
    for path in paths:
        d = json.loads(Path(path).read_text())
        for p, team in enumerate(d.get("info", {}).get("TeamNames", [])):
            if team in data:
                data[team].append(audit(path, p))

    for t in teams:
        print(f"{t}: {len(data[t])} games")
    print(f"\n{'day':>3s} | " + " | ".join(f"{t[:9]:>9s} workload/deliv idl%" for t in teams))
    for day in days:
        row = f"{day:3d} | "
        parts = []
        for t in teams:
            recs = data[t]
            wl = statistics.mean(r.get(day, {}).get("water_workload", 0) for r in recs)
            wd = statistics.mean(r.get(day, {}).get("water_delivered", 0) for r in recs)
            aw = statistics.mean(r.get(day, {}).get("animal_workload", 0) for r in recs)
            ad = statistics.mean(r.get(day, {}).get("animal_delivered", 0) for r in recs)
            cmd = statistics.mean(r.get(day, {}).get("CMD", 0) for r in recs)
            pas = statistics.mean(r.get(day, {}).get("PASS", 0) for r in recs)
            mv = statistics.mean(r.get(day, {}).get("MOVE", 0) for r in recs)
            units = statistics.mean(r.get(day, {}).get("units", 0) for r in recs)
            cap = units * 24
            parts.append(f"w{wl:5.1f}/{wd:5.1f} a{aw:5.1f}/{ad:5.1f} "
                         f"mv{mv:5.1f} idl{100*pas/max(1,cmd):4.1f}% cap{cap:5.0f}")
        print(row + " | ".join(parts))
    print("\nw = water workload/delivered tiles, a = animal workload(3 per animal-day)/delivered")
    print("cap = units x 24 steps (the whole daily budget, moves included)")


if __name__ == "__main__":
    main()
