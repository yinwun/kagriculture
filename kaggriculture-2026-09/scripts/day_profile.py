#!/usr/bin/env python
"""Day-by-day profile of a farm: the instrument for re-planning a tape.

Answers "where do we fall behind rank-1" at the resolution that matters: per
in-game day, the *mechanistic* work profile (jobs completed, work left undone,
movement/idle share, portfolio state) plus a normalised money track.  Cash alone
is a low-dimensional lagging projection (70k cash + 30k goods is not the same farm
as 100k cash + 0 goods), and the two agents never play the same town, so the money
track is reported two ways: mark-to-market net worth, and net worth relative to
that game's opponent.

Usage:
  python scripts/day_profile.py --teams Majkel1337 nickyl
  python scripts/day_profile.py --teams Majkel1337 --per-hour
"""
import argparse
import collections
import glob
import json
import statistics
from pathlib import Path

from kaggle_environments.envs.kaggriculture.kaggriculture import CROPS

MOVE = {"NORTH", "SOUTH", "EAST", "WEST"}
JOBS = ("WATER", "HARVEST", "PLANT", "FEED", "CARE", "COLLECT_FERTILIZER",
        "FERTILIZE", "PICKUP", "PLACE", "DIG", "DROP", "BUILD_PASTURE", "BUILD_COOP")


def net_worth(obs, p):
    farm = obs["farms"][p]
    prices = obs["market"]["prices"]
    shed = (obs.get("private") or {}).get("shed") or {}
    inv = (obs.get("private") or {}).get("inventories") or []
    value = 0.0
    for src in [shed] + [dict(x or {}) for x in inv]:
        for item, n in src.items():
            value += max(0, int(n)) * prices.get(item, 0)
    return float(farm["money"]) + value


def profile(path, p):
    d = json.loads(Path(path).read_text())
    steps = d["steps"]
    per_day = collections.defaultdict(collections.Counter)
    per_hour = collections.defaultdict(collections.Counter)
    money_day, nw_day, opp_nw_day = {}, {}, {}
    undone = collections.defaultdict(collections.Counter)
    portfolio = {}
    for t, entry in enumerate(steps):
        if p >= len(entry):
            continue
        obs = entry[p].get("observation")
        a = entry[p].get("action") or {}
        if not obs:
            continue
        day, hour = obs.get("day", t // 24), t % 24
        for cmd in [a.get("farmer") or []] + list(a.get("hands") or []):
            if not (isinstance(cmd, list) and cmd):
                continue
            v = cmd[0]
            if v in MOVE:
                per_day[day]["MOVE"] += 1
                per_hour[hour]["MOVE"] += 1
            elif v == "PASS":
                per_day[day]["PASS"] += 1
            else:
                per_day[day][v] += 1
                per_hour[hour][v] += 1
            per_day[day]["CMD"] += 1
        # state census at the last step of the day
        if hour == 23 or t == len(steps) - 1:
            money_day[day] = float(obs["farms"][p]["money"])
            nw_day[day] = net_worth(obs, p)
            q = 1 - p
            try:
                opp_nw_day[day] = net_worth(obs, q)
            except Exception:
                opp_nw_day[day] = None
            cnt = collections.Counter()
            for row in obs["farms"][p]["tiles"]:
                for cell in row:
                    if not isinstance(cell, dict):
                        continue
                    if cell.get("animal"):
                        cnt["A_" + cell["animal"]] += 1
                    elif cell.get("crop"):
                        cnt["C_" + cell["crop"]] += 1
                        cd = CROPS.get(cell["crop"])
                        if cd:
                            age = day - cell.get("planted_day", day)
                            if (not cd["ongoing"] and cell.get("yield_units", 0) < cd["max_yield"]
                                    and (cd["max_yield_day"] + 1) // 2 <= age <= cd["max_yield_day"]
                                    and not cell.get("watered_today")):
                                undone[day]["miss_water"] += 1
                    elif cell.get("kind") == "WEED":
                        cnt["WEED"] += 1
                    if isinstance(cell, dict) and cell.get("animal"):
                        if not cell.get("cared_today"):
                            undone[day]["miss_care"] += 1
                        if cell.get("fertilizer_available"):
                            undone[day]["miss_fert"] += 1
            portfolio[day] = dict(cnt)
    return {"episode": d["info"]["EpisodeId"], "team": d["info"]["TeamNames"][p],
            "per_day": {k: dict(v) for k, v in per_day.items()},
            "per_hour": {k: dict(v) for k, v in per_hour.items()},
            "money": money_day, "nw": nw_day, "opp_nw": opp_nw_day,
            "undone": {k: dict(v) for k, v in undone.items()},
            "portfolio": portfolio,
            "reward": d["rewards"][p]}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--teams", nargs="+", default=["Majkel1337", "nickyl"])
    ap.add_argument("--glob", default="data/top/episode-*.json,data/replays/episode-*.json")
    ap.add_argument("--per-hour", action="store_true")
    ap.add_argument("--out", default="data/day_profile.json")
    args = ap.parse_args()

    paths = []
    for g in args.glob.split(","):
        paths.extend(sorted(glob.glob(g)))
    by_team = collections.defaultdict(list)
    for path in paths:
        d = json.loads(Path(path).read_text())
        for p, team in enumerate(d.get("info", {}).get("TeamNames", [])):
            if team in args.teams:
                by_team[team].append(profile(path, p))
    for team, recs in by_team.items():
        print(f"{team}: {len(recs)} games")

    days = range(30)

    def mean_of(team, fn):
        out = {}
        for day in days:
            vals = [fn(r, day) for r in by_team[team]]
            vals = [v for v in vals if v is not None]
            out[day] = statistics.mean(vals) if vals else None
        return out

    print("\n=== money / net worth at each day boundary (mean over games) ===")
    hdr = f"{'day':>3s}"
    for team in args.teams:
        hdr += f" | {team[:9]:>9s} cash  {'nw':>9s}"
    print(hdr)
    cash = {t: mean_of(t, lambda r, d: r["money"].get(d)) for t in args.teams}
    nw = {t: mean_of(t, lambda r, d: r["nw"].get(d)) for t in args.teams}
    for day in days:
        if day % 2 and day not in (29,):
            continue
        line = f"{day:3d}"
        for t in args.teams:
            line += f" | {cash[t][day]:9,.0f} {nw[t][day]:9,.0f}"
        print(line)
    if len(args.teams) >= 2:
        a, b = args.teams[0], args.teams[1]
        print(f"\ngap (nw {a} - {b}) by day:")
        for day in days:
            g = nw[a][day] - nw[b][day]
            print(f"   day {day:2d}: {g:+10,.0f}" + ("   <-- first sustained gap"
                                                     if day and abs(g) > 3000 and
                                                     abs(nw[a][day - 1] - nw[b][day - 1]) <= 3000
                                                     else ""))

    print("\n=== work profile per day (mean commands) ===")
    for day in (0, 5, 10, 15, 20, 25, 29):
        print(f"day {day:2d}")
        for t in args.teams:
            c = collections.Counter()
            for r in by_team[t]:
                c.update(r["per_day"].get(day, {}))
            n = len(by_team[t])
            tot = max(1, c.get("CMD", 0))
            print(f"   {t:12s} " + " ".join(f"{k}:{c[k]//n}" for k in JOBS if c[k]) +
                  f"   | MOVE {c['MOVE']//n} PASS {c['PASS']//n} idle {100*c['PASS']/tot:.1f}%"
                  f" move_share {100*c['MOVE']/max(1,c['MOVE']+tot):.1f}%")

    print("\n=== work left undone at day end (mean tiles) ===")
    for t in args.teams:
        print(f"  {t:12s}", end="")
        for key in ("miss_water", "miss_care", "miss_fert"):
            v = mean_of(t, lambda r, d, k=key: r["undone"].get(d, {}).get(k, 0))
            print(f"   {key}={statistics.mean(x for x in v.values() if x is not None):6.1f}", end="")
        print()

    if args.per_hour:
        print("\n=== command share by hour of day (all days pooled) ===")
        for t in args.teams:
            print(f"  {t}")
            for h in range(24):
                c = collections.Counter()
                for r in by_team[t]:
                    c.update(r["per_hour"].get(h, {}))
                n = len(by_team[t])
                print(f"    h{h:02d} WATER {c['WATER']//n:3d} PLANT {c['PLANT']//n:3d} "
                      f"HARV {c['HARVEST']//n:3d} FEED {c['FEED']//n:3d} "
                      f"COLLECT {c['COLLECT_FERTILIZER']//n:3d} MOVE {c['MOVE']//n:3d}")

    Path(args.out).write_text(json.dumps({t: recs for t, recs in by_team.items()},
                                         indent=1, default=str))
    print(f"\nwrote {args.out}")


if __name__ == "__main__":
    main()
