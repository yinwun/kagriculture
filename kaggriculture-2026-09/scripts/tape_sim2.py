#!/usr/bin/env python
"""Day-aware tape simulator + validator against real replays.

Hands are day-laborers: HIRE appends to farm["hands"], and the list is cleared at
every day rollover.  Index k of the action's hands list addresses the k-th hand
hired *today*, so hand identity resets each day.  A new hand spawns on the first
free shed-access tile in NWSE order (ties by min occupancy), which is exactly
reproducible, so the whole day can be simulated exactly.

  python scripts/tape_sim2.py --replay data/replays/episode-X-replay.json --player 0
      -> prints which route the player actually replayed (best position match)

  python scripts/tape_sim2.py --route 105          -> prints per-day hand census
"""
import argparse
import base64
import json
import re
import zlib
from collections import deque
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
BASE = (ROOT / "data" / "league" /
        "ahmedberatozer_kaggriculture-v42-production-that-fits-the-marke" / "main.py")

MOVES = {"NORTH": (0, -1), "SOUTH": (0, 1), "EAST": (1, 0), "WEST": (-1, 0)}
COMMIT = {"PICKUP", "DROP", "PLANT", "HARVEST", "BUILD_COOP", "BUILD_PASTURE",
          "PLACE", "FEED", "CARE", "COLLECT_FERTILIZER", "DIG", "WATER", "FERTILIZE"}
BOARD = 10
SHED_ACCESS = [(4, 4), (5, 4), (4, 5), (5, 5)]   # NWSE order, board 10


def load_blob(path=BASE):
    src = Path(path).read_text()
    m = re.search(r"b85decode\('([^']+)'\)", src)
    data = json.loads(zlib.decompress(base64.b85decode(m.group(1))))
    return src, m, data


def cmd_of(action, k):
    if not isinstance(action, dict):
        return None
    cmds = [action.get("farmer") or ["PASS"]] + list(action.get("hands") or [])
    return cmds[k] if k < len(cmds) else None


def nhands(tape):
    return max(len(a.get("hands") or []) for a in tape if isinstance(a, dict))


def spawn_tile(positions):
    """First free shed-access tile in NWSE order; ties by min occupancy."""
    occ = {t: 0 for t in SHED_ACCESS}
    for p in positions:
        if p in occ:
            occ[p] += 1
    best = sorted(occ.items(), key=lambda kv: (kv[1], SHED_ACCESS.index(kv[0])))
    return best[0][0]


def simulate(tape, keep=None):
    """Return rows[k] = list of (step, pos, cmd) for unit k (0 = farmer).

    Positions reset every day: the farmer spawns at (4,4), each hand spawns when
    its HIRE order resolves.
    """
    nh = nhands(tape)
    rows = {k: [] for k in range(nh + 1)}
    live = {}
    for step, a in enumerate(tape):
        if step % 24 == 0:
            live = {0: (4, 4)}          # farmer respawns on the NW shed tile
            hired = 0
        for o in (a.get("market") or []):
            if isinstance(o, list) and o and o[0] == "HIRE":
                hired += 1
                if hired <= nh:
                    live[hired] = spawn_tile([p for p in live.values() if p])
        for k in range(nh + 1):
            c = cmd_of(a, k)
            p = live.get(k)
            if isinstance(c, list) and c and c[0] in MOVES and p is not None:
                dx, dy = MOVES[c[0]]
                q = (p[0] + dx, p[1] + dy)
                if 0 <= q[0] < BOARD and 0 <= q[1] < BOARD:
                    live[k] = q
            rows[k].append((step, live.get(k), c))
    return rows


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--replay")
    ap.add_argument("--player", type=int, default=0)
    ap.add_argument("--route", type=int)
    args = ap.parse_args()

    src, m, data = load_blob()
    actions, routes = data["actions"], data["routes"]

    if args.replay:
        steps = json.loads(Path(args.replay).read_text())["steps"]
        obs_seq = []
        for t in range(len(steps)):
            o = steps[t][args.player].get("observation")
            if not o:
                continue
            farm = o["farms"][args.player]
            obs_seq.append((o.get("step", t),
                            tuple(farm.get("farmer") or (0, 0)),
                            [tuple(h) for h in (farm.get("hands") or [])]))
        print(f"{len(obs_seq)} observed turns")
        scored = []
        for rid in sorted(int(k) for k in routes):
            tape = [actions[i] for i in routes[str(rid)]]
            rows = simulate(tape)
            hit = tot = 0
            for step, fpos, hpos in obs_seq:
                if step >= len(tape):
                    continue
                if rows[0][step][1] == fpos:
                    hit += 1
                tot += 1
                for i, hp in enumerate(hpos):
                    if i + 1 in rows and rows[i + 1][step][1] == hp:
                        hit += 1
                    tot += 1
            scored.append((hit / max(1, tot), rid, hit, tot))
        scored.sort(reverse=True)
        for rate, rid, hit, tot in scored[:4]:
            print(f"  route {rid:>3}: position match {100*rate:5.1f}%  ({hit}/{tot})")
        print(f"  worst: route {scored[-1][1]} {100*scored[-1][0]:.1f}%")
        return

    rid = args.route if args.route is not None else 105
    tape = [actions[i] for i in routes[str(rid)]]
    rows = simulate(tape)
    nh = nhands(tape)
    print(f"route {rid}: {len(tape)} steps, {nh} hand slots")
    hires = [sum(1 for o in (a.get("market") or [])
                 if isinstance(o, list) and o and o[0] == "HIRE") for a in tape]
    for day in range(30):
        seg = hires[day * 24:(day + 1) * 24]
        live = max((sum(seg[:h + 1]) for h in range(len(seg))), default=0)
        print(f"  day {day:2d}: hires {sum(seg):2d} peak live {live:2d}")
    # free windows between commitments, per unit per day
    tot_win = 0
    for k in range(nh + 1):
        for day in range(30):
            dayrows = [(s, p, c) for (s, p, c) in rows[k] if s // 24 == day and p is not None]
            cm = [r for r in dayrows if isinstance(r[2], list) and r[2] and r[2][0] in COMMIT]
            for (s1, p1, _), (s2, p2, _) in zip(cm, cm[1:]):
                if s2 - s1 > 1:
                    tot_win += (s2 - s1 - 1)
    print(f"  total free turns between commitments (all units, all days): {tot_win}")


if __name__ == "__main__":
    main()
