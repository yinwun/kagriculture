#!/usr/bin/env python
"""Missed-work audit from replays: what a farm left undone, per game.

Counts per game, from the recorded states (not the actions), the tile-days where
work was available and not done:

  miss_water   PLANT in the watering bonus window with yield < max, still unwatered
               at the last step of the day  (each one is a lost yield unit)
  miss_feed    animal still unfed at day end (a second miss makes it escape)
  miss_care    animal uncared at day end (halves/removes its output bonus)
  miss_fert    fertilizer_available at day end (it does not roll over)
  miss_harv    ripe crop (done growing) with yield > 0 at day end

Comparing the champion against rank-1's replays says which work is being dropped,
which is what the next layer has to fix.

Usage:
  python scripts/missed_work.py --a Majkel1337 --b nickyl
"""
import argparse
import collections
import glob
import json
import statistics
from pathlib import Path

from kaggle_environments.envs.kaggriculture.kaggriculture import CROPS


def game_counters(path, player):
    d = json.loads(Path(path).read_text())
    steps = d["steps"]
    c = collections.Counter()
    last_day = None
    for t, entry in enumerate(steps):
        if player >= len(entry):
            continue
        obs = entry[player].get("observation")
        if not obs:
            continue
        day = obs.get("day", t // 24)
        last_of_day = (t % 24 == 23) or t == len(steps) - 1
        for row in obs["farms"][player]["tiles"]:
            for cell in row:
                if not isinstance(cell, dict):
                    continue
                kind = cell.get("kind")
                if kind == "PLANT":
                    cd = CROPS.get(cell.get("crop"))
                    if not cd:
                        continue
                    age = day - cell.get("planted_day", day)
                    units = cell.get("yield_units", 0)
                    in_window = (not cd["ongoing"] and units < cd["max_yield"]
                                 and (cd["max_yield_day"] + 1) // 2 <= age <= cd["max_yield_day"])
                    if in_window and not cell.get("watered_today"):
                        c["water_opp"] += 1
                        if last_of_day:
                            c["miss_water"] += 1
                    ripe = units > 0 and (age >= cd["first_yield_day"] if cd["ongoing"]
                                          else age >= cd["max_yield_day"] or units >= cd["max_yield"])
                    if ripe and last_of_day:
                        c["miss_harv"] += 1
                elif kind in ("PASTURE", "COOP") and cell.get("animal"):
                    if last_of_day:
                        if not cell.get("fed_today"):
                            c["miss_feed"] += 1
                        if not cell.get("cared_today"):
                            c["miss_care"] += 1
                        if cell.get("fertilizer_available"):
                            c["miss_fert"] += 1
        c["steps"] += 1
    return c


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--a", default="Majkel1337")
    ap.add_argument("--b", default="nickyl")
    ap.add_argument("--glob", default="data/top/episode-*.json,data/replays/episode-*.json")
    args = ap.parse_args()

    paths = []
    for g in args.glob.split(","):
        paths.extend(sorted(glob.glob(g)))
    agg = {args.a: [], args.b: []}
    for path in paths:
        d = json.loads(Path(path).read_text())
        for p, team in enumerate(d.get("info", {}).get("TeamNames", [])):
            if team in agg:
                agg[team].append((Path(path).name, game_counters(path, p)))

    keys = ("miss_water", "water_opp", "miss_harv", "miss_feed", "miss_care", "miss_fert")
    print(f"{'team':12s} {'games':>5s} " + " ".join(f"{k:>11s}" for k in keys))
    for team, rows in agg.items():
        if not rows:
            continue
        means = {k: statistics.mean(r[k] / max(1, r["steps"] / 720) for _, r in rows) for k in keys}
        print(f"{team:12s} {len(rows):5d} " + " ".join(f"{means[k]:11.1f}" for k in keys))
    print("\nmiss_* = tile-days of available work left undone at the end of a day (per game).")
    print("water_opp = tile-days (any time of day) where a bonus-window watering was still pending.")


if __name__ == "__main__":
    main()
