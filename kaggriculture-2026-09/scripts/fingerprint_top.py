#!/usr/bin/env python
"""Fingerprint a top agent's *algorithm* from replays alone.

Question: is rank-1 a fixed tape, a state-machine script, a closed-loop
planner/scheduler, or a learned policy?  Discriminators computed here:

  1. layout_jaccard : for a given day, the set of (tile -> plant) pairs, compared
                      across that agent's games in different towns.  A fixed
                      script reuses a layout; a planner re-derives it per town.
  2. plan_consistency: fraction of steps where the *normalised* action at the
                      same (day, step-in-day) is identical across games.
                      A tape is ~1.0; a reactive policy is low.
  3. reactivity     : does the market/sell behaviour depend on realised state
                      (own inventory, wallet, price) rather than on time?
                      Measured as accuracy of a "time-only" predictor vs a
                      "state" predictor over the agent's own decisions.
  4. structure      : hand curve, land-buy days, animal-buy days, crop mix,
                      harvest cadence -- to compare against our own tape.

Usage:
  python scripts/fingerprint_top.py data/top/episode-*.json --team Majkel1337
  python scripts/fingerprint_top.py data/top/episode-*.json            # all seats
"""
import argparse
import collections
import glob
import itertools
import json
from pathlib import Path


def load(path):
    d = json.loads(Path(path).read_text())
    teams = d.get("info", {}).get("TeamNames", [])
    return d, teams


def norm_action(a):
    if not a:
        return ()
    f = tuple(a.get("farmer") or ())
    h = tuple(tuple(x) for x in (a.get("hands") or []))
    m = tuple(tuple(x) for x in (a.get("market") or ()))
    return (f, h, m)


def crop_layout(obs, p):
    out = {}
    tiles = obs["farms"][p]["tiles"]
    for r, row in enumerate(tiles):
        for c, cell in enumerate(row):
            if isinstance(cell, dict):
                plant = cell.get("plant")
                if plant:
                    crop = plant[0] if isinstance(plant, list) else plant
                    out[(r, c)] = str(crop)
    return out


def profile(path, p):
    d, teams = load(path)
    steps = d["steps"]
    rec = {
        "path": Path(path).name,
        "team": teams[p] if p < len(teams) else f"seat{p}",
        "seat": p,
        "reward": d["rewards"][p],
        "seed": d.get("info", {}).get("seed"),
        "acts": {},
        "layouts": {},
        "hands": {},
        "money": {},
        "crops_harvested": collections.Counter(),
        "market_ops": collections.Counter(),
        "verb": collections.Counter(),
        "land_days": [],
        "animal_days": collections.defaultdict(list),
        "hands_by_day": {},
        "sells_by_day": collections.Counter(),
        "buys_by_day": collections.Counter(),
    }
    prev_quad = None
    for t, entry in enumerate(steps):
        if p >= len(entry):
            break
        e = entry[p]
        obs = e.get("observation")
        if not obs:
            continue
        farm = obs["farms"][p]
        day = obs.get("day", t // 24)
        rec["acts"][t] = norm_action(e.get("action"))
        rec["money"][day] = farm.get("money")
        rec["hands_by_day"][day] = len(farm.get("hands") or [])
        quads = len(farm.get("unlocked_quadrants") or [])
        if prev_quad is None:
            prev_quad = quads
        elif quads != prev_quad:
            rec["land_days"].append((day, quads))
            prev_quad = quads
        if t % 24 == 12:  # mid-day snapshot of the layout
            rec["layouts"][day] = crop_layout(obs, p)
        # animals present
        for r, row in enumerate(farm["tiles"]):
            for c, cell in enumerate(row):
                if isinstance(cell, dict) and cell.get("animal"):
                    rec["animal_days"][str(cell["animal"])].append(day)
        a = e.get("action") or {}
        for cmd in [a.get("farmer") or []] + list(a.get("hands") or []):
            if isinstance(cmd, list) and cmd:
                rec["verb"][cmd[0]] += 1
        for m in (a.get("market") or []):
            if isinstance(m, list) and m:
                rec["market_ops"][m[0]] += 1
                (rec["sells_by_day"] if m[0].startswith("SELL") else rec["buys_by_day"])[day] += 1
    return rec


def layout_jaccard(recs, days=(5, 10, 15, 20, 25, 28)):
    rows = []
    for day in days:
        sets = []
        for r in recs:
            lay = r["layouts"].get(day) or {}
            sets.append(set(lay.items()))
        if len(sets) < 2:
            continue
        js = []
        for a, b in itertools.combinations(sets, 2):
            u = len(a | b)
            js.append(len(a & b) / u if u else 0.0)
        sizes = [len(s) for s in sets]
        rows.append((day, sum(js) / len(js) if js else 0.0, sizes))
    return rows


def plan_consistency(recs):
    """Fraction of time indices where all games show the same normalised action
    skeleton (ignoring coordinates, which depend on town) and the same verb."""
    def skel(a):
        f, h, m = a
        return (tuple(sorted(x[0] for x in h if x)),
                tuple(sorted(x[0] for x in m if x)))
    common = set(recs[0]["acts"])
    for r in recs[1:]:
        common &= set(r["acts"])
    same = 0
    both_nonzero = 0
    for t in sorted(common):
        ss = {skel(r["acts"][t]) for r in recs}
        if len(ss) == 1:
            same += 1
        if any(r["acts"][t][1] or r["acts"][t][2] for r in recs):
            if len(ss) == 1:
                both_nonzero += 1
    bus = sum(1 for t in common if any(r["acts"][t][1] or r["acts"][t][2] for r in recs))
    return same / len(common) if common else 0, both_nonzero / bus if bus else 0, len(common)


def verb_entropy(rec):
    tot = sum(rec["verb"].values())
    if not tot:
        return 0.0
    import math
    return -sum((c / tot) * math.log2(c / tot) for c in rec["verb"].values() if c)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("paths", nargs="+")
    ap.add_argument("--team", default=None)
    args = ap.parse_args()

    paths = []
    for p in args.paths:
        paths.extend(sorted(glob.glob(p)))
    recs = []
    for path in paths:
        d, teams = load(path)
        for p in range(len(teams)):
            if args.team and teams[p] != args.team:
                continue
            recs.append(profile(path, p))

    by_team = collections.defaultdict(list)
    for r in recs:
        by_team[r["team"]].append(r)

    print("=" * 78)
    for team, rs in sorted(by_team.items(), key=lambda kv: -len(kv[1])):
        print(f"{team}: {len(rs)} game(s)  rewards={[int(r['reward']) for r in rs]}")
        for r in rs:
            print(f"   {r['path']:44s} seed={r['seed']}  hands/day(avg)="
                  f"{sum(r['hands_by_day'].values())/max(1,len(r['hands_by_day'])):.2f}"
                  f"  land={r['land_days']}"
                  f"  verbs={dict(r['verb'])}")

    print("=" * 78)
    print("LAYOUT JACCARD across an agent's games (1.0 = identical tile->crop map)")
    for team, rs in by_team.items():
        if len(rs) < 2:
            continue
        print(f"  {team}:")
        for day, j, sizes in layout_jaccard(rs):
            print(f"    day {day:2d}  jaccard={j:.3f}  plants/game={sizes}")

    print("=" * 78)
    print("PLAN CONSISTENCY (same action skeleton at same (day,slot) across games)")
    for team, rs in by_team.items():
        if len(rs) < 2:
            continue
        s, snz, n = plan_consistency(rs)
        print(f"  {team}: overall={s:.3f}  active-steps={snz:.3f}  (n={n})")

    print("=" * 78)
    print("STRUCTURE")
    for team, rs in by_team.items():
        r = rs[0]
        print(f"  {team}: verbs={dict(r['verb'])}")
        print(f"     market={dict(r['market_ops'])}")
        print(f"     hands/day={dict(sorted(r['hands_by_day'].items()))}")
        print(f"     land={r['land_days']}")
        an = {k: (min(v), max(v)) for k, v in r["animal_days"].items()}
        print(f"     animals(first,last day)={an}")
        print(f"     money day0/10/20/29="
              f"{r['money'].get(0)},{r['money'].get(10)},{r['money'].get(20)},{r['money'].get(29)}")


if __name__ == "__main__":
    main()
