#!/usr/bin/env python
"""Audit every crop in a replay from engine state transitions only.

Per crop we recover: waterings, days inside the engine's effective window that
were missed, peak yield, yield actually harvested, and how the crop ended:

  harvested    tile -> None while carrying units
  starved      tile -> WEED because it went 2 consecutive days unwatered
  decayed      tile -> WEED because it sat past max_lifespan_step
  replaced     tile became a different plant (dug / replanted)
  built        tile became a structure
  alive        still a plant when the game ended

Usage:
  python scripts/audit_crops.py data/replays/episode-109299436-replay.json
"""
import argparse
import collections
import json
from pathlib import Path

CROPS = {
    "WHEAT":      {"max_yield_day": 4,  "max_yield": 6, "ongoing": False},
    "CARROT":     {"max_yield_day": 3,  "max_yield": 4, "ongoing": False},
    "TOMATO":     {"max_yield_day": 8,  "max_yield": 4, "ongoing": True},
    "STRAWBERRY": {"max_yield_day": 10, "max_yield": 4, "ongoing": True},
    "MELON":      {"max_yield_day": 12, "max_yield": 6, "ongoing": False},
}
STRUCTS = {"COOP", "PASTURE"}


def in_window(crop, age):
    d = CROPS.get(crop)
    if not d:
        return False
    if d["ongoing"]:
        return age >= 0
    return (d["max_yield_day"] + 1) // 2 <= age <= d["max_yield_day"]


def audit(path, player, verbose=False):
    steps = json.loads(Path(path).read_text())["steps"]
    last = {}
    done = []

    def close(rec, how, day):
        rec["end"] = how
        rec["end_day"] = day
        done.append(rec)

    for t in range(len(steps)):
        turn = steps[t]
        if player >= len(turn):
            continue
        obs = turn[player].get("observation")
        if not obs:
            continue
        farm = obs["farms"][player]
        tiles = farm["tiles"]
        day = obs.get("day", t // 24)
        for y in range(len(tiles)):
            for x in range(len(tiles[y])):
                cur = tiles[y][x]
                key = (x, y)
                rec = last.get(key)
                is_plant = isinstance(cur, dict) and cur.get("kind") == "PLANT"
                if is_plant:
                    if rec is None or rec["crop"] != cur.get("crop"):
                        if rec is not None:
                            close(rec, "replaced", day)
                        rec = {"tile": key, "crop": cur.get("crop"),
                               "planted_day": cur.get("planted_day", day),
                               "day_watered": {}, "day_window": {},
                               "peak": 0, "last_units": 0, "onharv": 0,
                               "age_at_end": 0}
                        last[key] = rec
                    u = cur.get("yield_units", 0) or 0
                    if u == 0 and rec.get("last_units", 0) > 0:
                        rec["onharv"] = rec.get("onharv", 0) + rec["last_units"]
                    rec["peak"] = max(rec["peak"], u)
                    rec["last_units"] = u
                    rec["age_at_end"] = day - rec["planted_day"]
                    # day-level: a day counts as watered if the flag was ever
                    # True during that day (it flips back at the rollover)
                    rec["day_watered"][day] = (rec["day_watered"].get(day, False)
                                               or bool(cur.get("watered_today")))
                    if in_window(rec["crop"], day - rec["planted_day"]):
                        rec["day_window"][day] = True
                else:
                    if rec is None:
                        continue
                    last.pop(key, None)
                    if cur is None:
                        close(rec, "harvested", day)
                    elif isinstance(cur, str) and cur == "WEED":
                        misses = {d for d, ok in rec["day_window"].items()
                                  if not rec["day_watered"].get(d)}
                        starved = len(misses) >= 2 and obs.get("hour") == 0
                        close(rec, "starved" if starved else "decayed", day)
                    elif isinstance(cur, dict) and cur.get("kind") in STRUCTS:
                        close(rec, "built", day)
                    else:
                        close(rec, "gone", day)
    for key, rec in list(last.items()):
        close(rec, "alive", 29)

    bycrop = collections.defaultdict(collections.Counter)
    for r in done:
        v = bycrop[r["crop"]]
        v["crops"] += 1
        v[r["end"]] += 1
        wd = {d for d, ok in r["day_watered"].items() if ok}
        r["waters"] = wd
        r["missed"] = {d for d in r["day_window"] if d not in wd}
        v["waters"] += len(wd)
        v["window"] += len(r["day_window"])
        v["missed"] += len(r["missed"])
        v["peak"] += r["peak"]
        v["onharv"] += r.get("onharv", 0)
        v["age"] += r["age_at_end"]
        if r["end"] == "harvested":
            v["units"] += r["last_units"] + r.get("onharv", 0)
            v["harvests"] += 1
            if r["last_units"] >= CROPS.get(r["crop"], {}).get("max_yield", 0):
                v["at_max"] += 1

    print(f"=== {Path(path).name}  player {player} ===")
    print(f"{'crop':11}{'crops':>6}{'harv':>5}{'starve':>7}{'decay':>6}{'repl':>5}"
          f"{'alive':>6}{'units':>7}{'u/h':>6}{'peak':>6}{'atmax':>6}"
          f"{'water':>6}{'win':>5}{'miss':>5}{'miss%':>7}{'onh':>5}")
    T = collections.Counter()
    for c, v in sorted(bycrop.items(), key=lambda kv: -kv[1]["crops"]):
        h = v["harvests"] or 1
        print(f"{str(c):11}{v['crops']:6d}{v['harvests']:5d}{v['starved']:7d}"
              f"{v['decayed']:6d}{v['replaced']:5d}{v['alive']:6d}{v['units']:7d}"
              f"{v['units']/h:6.2f}{v['peak']:6d}{v['at_max']:6d}{v['waters']:6d}"
              f"{v['window']:5d}{v['missed']:5d}"
              f"{100.0*v['missed']/max(1,v['window']):6.1f}%{v['onharv']:5d}")
        for k in ("crops", "harvests", "starved", "decayed", "replaced", "alive",
                  "units", "onharv", "peak", "at_max", "waters", "window", "missed"):
            T[k] += v[k]
    print(f"{'TOTAL':11}{T['crops']:6d}{T['harvests']:5d}{T['starved']:7d}"
          f"{T['decayed']:6d}{T['replaced']:5d}{T['alive']:6d}{T['units']:7d}"
          f"{T['units']/(T['harvests'] or 1):6.2f}{T['peak']:6d}{T['at_max']:6d}"
          f"{T['waters']:6d}{T['window']:5d}{T['missed']:5d}"
          f"{100.0*T['missed']/max(1,T['window']):6.1f}%{T['onharv']:5d}")
    pot = sum(CROPS[r['crop']]['max_yield'] for r in done
              if r['end'] == 'harvested' and r['crop'] in CROPS)
    print(f"harvested {T['units']} units vs {pot} crop-max potential "
          f"({100.0*T['units']/max(1,pot):.1f}%); peak-observed total {T['peak']}; "
          f"leakage {T['peak']-T['units']} units; starved {T['starved']}")
    if verbose:
        for r in sorted(done, key=lambda r: (r["crop"], r["planted_day"])):
            print(f"   {r['crop']:11} tile {r['tile']} planted d{r['planted_day']:2d} "
                  f"end {r['end']:9} d{r['end_day']:2d} peak {r['peak']} "
                  f"last {r['last_units']} waters {sorted(r['waters'])} "
                  f"missed {sorted(r.get('missed', []))}")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("replay")
    ap.add_argument("--player", type=int, default=None)
    ap.add_argument("--verbose", action="store_true")
    args = ap.parse_args()
    d = json.loads(Path(args.replay).read_text())
    n = len(d["steps"][0])
    for p in ([args.player] if args.player is not None else list(range(n))):
        audit(args.replay, p, args.verbose)


if __name__ == "__main__":
    main()
