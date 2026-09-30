#!/usr/bin/env python
"""Audit animal tiles in a replay: feed/care coverage, production, escapes, loss.

Engine rules (kaggriculture._daily_refresh_animals):
  * production fires every ``interval`` days after ``first_yield_day`` and adds
    ``1 + pending_care_bonus`` units, capped at ``max_held``;
  * the care bonus only accrues on a day that is BOTH cared and fed, and is
    consumed on the next fed production day;
  * two consecutive unfed days -> the animal escapes (structure stays, animal
    and its 300-500 coin purchase are gone).

Usage:
  python scripts/audit_animals.py data/replays/episode-X-replay.json
"""
import argparse
import collections
import json
from pathlib import Path

ANIMALS = {
    "GOOSE": {"first_yield_day": 4, "interval": 1, "max_held": 4, "product": "EGG", "cost": 300},
    "COW":   {"first_yield_day": 8, "interval": 2, "max_held": 6, "product": "MILK", "cost": 400},
    "SHEEP": {"first_yield_day": 6, "interval": 3, "max_held": 6, "product": "WOOL", "cost": 500},
}
STRUCTS = {"COOP", "PASTURE"}


def audit(path, player):
    steps = json.loads(Path(path).read_text())["steps"]
    live = {}
    done = []
    for t in range(len(steps)):
        turn = steps[t]
        if player >= len(turn):
            continue
        obs = turn[player].get("observation")
        if not obs:
            continue
        tiles = obs["farms"][player]["tiles"]
        day = obs.get("day", t // 24)
        for y in range(len(tiles)):
            for x in range(len(tiles[y])):
                cur = tiles[y][x]
                key = (x, y)
                rec = live.get(key)
                if isinstance(cur, dict) and "animal" in cur:
                    if rec is None or rec["animal"] != cur["animal"]:
                        rec = {"animal": cur["animal"], "placed_day": cur.get("placed_day", day),
                               "fed": set(), "cared": set(), "produced": 0,
                               "collected": 0, "peak": 0, "last": 0,
                               "unfed_streak": 0, "max_streak": 0}
                        live[key] = rec
                    u = cur.get("yield_units", 0) or 0
                    if u < rec["last"]:
                        rec["collected"] += rec["last"] - u
                    rec["last"] = u
                    rec["peak"] = max(rec["peak"], u)
                    if cur.get("fed_today"):
                        rec["fed"].add(day)
                        rec["unfed_streak"] = 0
                    else:
                        rec["unfed_streak"] += 1
                        rec["max_streak"] = max(rec["max_streak"], rec["unfed_streak"])
                    if cur.get("cared_today"):
                        rec["cared"].add(day)
                elif rec is not None:
                    live.pop(key, None)
                    rec["end"] = "structure" if cur in STRUCTS else str(cur)
                    rec["end_day"] = day
                    if isinstance(cur, dict) and cur.get("kind") in STRUCTS:
                        rec["end"] = "escaped" if rec["max_streak"] >= 2 else "collected_out"
                    done.append(rec)
    for key, rec in list(live.items()):
        rec["end"] = "alive"
        rec["end_day"] = 29
        done.append(rec)

    bya = collections.defaultdict(collections.Counter)
    for r in done:
        v = bya[r["animal"]]
        v["n"] += 1
        v["fed"] += len(r["fed"])
        v["cared"] += len(r["cared"])
        v["collected"] += r["collected"]
        v["days"] += r["end_day"] - r["placed_day"] + 1
        v[r["end"]] += 1
        if r["max_streak"] >= 2:
            v["starved_risk"] += 1
    print(f"=== {Path(path).name} player {player} — animals ===")
    print(f"{'animal':8}{'n':>3}{'days':>6}{'fed%':>7}{'cared%':>8}{'collected':>10}"
          f"{'per-day':>9}{'escape':>7}{'alive':>6}{'peak':>5}")
    T = collections.Counter()
    for a, v in sorted(bya.items()):
        d = max(1, v["days"])
        print(f"{a:8}{v['n']:3d}{v['days']:6d}{100.0*v['fed']/d:6.1f}%"
              f"{100.0*v['cared']/d:7.1f}%{v['collected']:10d}"
              f"{v['collected']/d:9.2f}{v['escaped']:7d}{v['alive']:6d}"
              f"{ANIMALS[a]['max_held']:5d}")
        for k in ("n", "days", "fed", "cared", "collected", "escaped", "alive"):
            T[k] += v[k]
    d = max(1, T["days"])
    print(f"{'TOTAL':8}{T['n']:3d}{T['days']:6d}{100.0*T['fed']/d:6.1f}%"
          f"{100.0*T['cared']/d:7.1f}%{T['collected']:10d}{T['collected']/d:9.2f}"
          f"{T['escaped']:7d}{T['alive']:6d}")
    lost = sum(ANIMALS[r["animal"]]["cost"] for r in done if r["end"] == "escaped")
    print(f"escaped animals cost {lost} coins to replace; "
          f"collected units {T['collected']}")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("replay")
    ap.add_argument("--player", type=int, default=None)
    args = ap.parse_args()
    d = json.loads(Path(args.replay).read_text())
    n = len(d["steps"][0])
    for p in ([args.player] if args.player is not None else list(range(n))):
        audit(args.replay, p)


if __name__ == "__main__":
    main()
