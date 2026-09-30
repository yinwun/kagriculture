#!/usr/bin/env python
"""Tape generator: insert on-route WATER turns into a route's free budget.

This does NOT copy anyone's tape. It takes our existing routes and re-plans each
worker's *walk between its commitments* so the worker stops and waters the crops
it walks over.

Why this is safe by construction:
  * commitments (PLANT/HARVEST/PICKUP/DROP/PLACE/FEED/CARE/COLLECT_FERTILIZER/
    WATER/BUILD_*) keep their exact step and tile -- only walking is re-planned;
  * the re-planned segment has the SAME length as the original, so every later
    commitment is still reached on time;
  * WATER on a non-plant tile is a silent no-op in the engine, and PASS is a
    no-op too -- so a failed assumption degrades to today's behaviour.

Free budget per segment = trailing PASS turns + (moves beyond the Manhattan
distance between the two commitments).

Usage:
  python scripts/tape_gen.py --routes all --out data/tapeopt/gen_all
  python scripts/tape_gen.py --routes 105 --out data/tapeopt/gen105
"""
import argparse
import base64
import copy
import json
import re
import zlib
from collections import defaultdict, deque
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
BASE = (ROOT / "data" / "league" /
        "ahmedberatozer_kaggriculture-v42-production-that-fits-the-marke" / "main.py")

MOVES = {"NORTH": (0, -1), "SOUTH": (0, 1), "EAST": (1, 0), "WEST": (-1, 0)}
COMMIT = {"PICKUP", "DROP", "PLANT", "HARVEST", "BUILD_COOP", "BUILD_PASTURE",
          "PLACE", "FEED", "CARE", "COLLECT_FERTILIZER", "DIG", "WATER", "FERTILIZE"}
BOARD = 10

# engine crop table (kaggriculture.py CROPS)
CROPS = {
    "WHEAT":      {"first_yield_day": 2, "max_yield_day": 4,  "max_yield": 6, "ongoing": False},
    "CARROT":     {"first_yield_day": 2, "max_yield_day": 3,  "max_yield": 4, "ongoing": False},
    "TOMATO":     {"first_yield_day": 8, "max_yield_day": 8,  "max_yield": 4, "ongoing": True},
    "STRAWBERRY": {"first_yield_day": 10, "max_yield_day": 10, "max_yield": 4, "ongoing": True},
    "MELON":      {"first_yield_day": 10, "max_yield_day": 12, "max_yield": 6, "ongoing": False},
}


def load_blob(path=BASE):
    src = Path(path).read_text()
    m = re.search(r"b85decode\('([^']+)'\)", src)
    data = json.loads(zlib.decompress(base64.b85decode(m.group(1))))
    return src, m, data


def dump_blob(data):
    raw = zlib.compress(json.dumps(data, separators=(",", ":")).encode(), 9)
    return base64.b85encode(raw).decode()


def cmd_of(action, k):
    if not isinstance(action, dict):
        return None
    cmds = [action.get("farmer") or ["PASS"]] + list(action.get("hands") or [])
    return cmds[k] if k < len(cmds) else None


def simulate(tape, nhand):
    """traj[k] = list of (step, (x,y), cmd)"""
    traj = {}
    for k in range(nhand + 1):
        p = [4, 4]
        rows = []
        for step, a in enumerate(tape):
            c = cmd_of(a, k)
            if isinstance(c, list) and c and c[0] in MOVES:
                dx, dy = MOVES[c[0]]
                p = [p[0] + dx, p[1] + dy]
            rows.append((step, tuple(p), c))
        traj[k] = rows
    return traj


def crop_timeline(tape, traj, nhand):
    """(x,y) -> list of [start_step, end_step, crop] where a plant exists."""
    iv = defaultdict(list)
    for k in range(nhand + 1):
        for step, pos, c in traj[k]:
            if not (isinstance(c, list) and c):
                continue
            if c[0] == "PLANT":
                crop = c[1] if len(c) > 1 else None
                iv[pos].append([step, None, crop])
            elif c[0] == "HARVEST":
                for e in reversed(iv.get(pos, [])):
                    if e[1] is None:
                        e[1] = step
                        break
    for pos, lst in iv.items():
        for e in lst:
            if e[1] is None:
                e[1] = 10 ** 9
    return iv


def crop_at(iv, pos, step):
    for s, e, crop in iv.get(pos, ()):
        if s <= step < e:
            return (s, e, crop)
    return None


def is_crop(iv, pos, step):
    return crop_at(iv, pos, step) is not None


def watered_tiledays(tape, traj, nhand):
    """(pos, day) pairs the tape itself already waters."""
    seen = set()
    for k in range(nhand + 1):
        for step, pos, c in traj[k]:
            if isinstance(c, list) and c and c[0] == "WATER":
                seen.add((pos, step // 24))
    return seen


def bfs_path(start, goal, blocked, limit):
    if start == goal:
        return []
    q = deque([start])
    prev = {start: None}
    while q:
        cur = q.popleft()
        for op, (dx, dy) in MOVES.items():
            nxt = (cur[0] + dx, cur[1] + dy)
            if not (0 <= nxt[0] < BOARD and 0 <= nxt[1] < BOARD):
                continue
            if blocked[nxt[1]][nxt[0]] or nxt in prev:
                continue
            prev[nxt] = (cur, op)
            if nxt == goal:
                path = []
                node = nxt
                while prev[node] is not None:
                    pnode, pop = prev[node]
                    path.append(pop)
                    node = pnode
                path.reverse()
                return path if len(path) <= limit else None
            q.append(nxt)
    return None


def useful_water(iv, pos, day_start, day):
    """Engine-accurate: can a WATER on this tile now actually add yield?

    Non-ongoing crops gain inside [ (max_yield_day+1)//2, max_yield_day ] of their
    age, once per tile-day, capped at max_yield. Ongoing crops get their unit at
    the day rollover, so any water during the day helps.
    """
    hit = crop_at(iv, pos, day_start)
    if hit is None:
        return False, None
    s, e, crop = hit
    data = CROPS.get(crop)
    if data is None:
        return False, None
    planted_day = s // 24
    age = day - planted_day
    if data["ongoing"]:
        return True, crop
    window_start = (data["max_yield_day"] + 1) // 2
    if window_start <= age <= data["max_yield_day"]:
        return True, crop
    return False, crop


def enhance_route(actions, routes, rid, max_detour=3, verbose=True, engine_aware=True):
    """Return the re-planned tape for one route (list of action dicts)."""
    tape = [copy.deepcopy(actions[i]) for i in routes[str(rid)]]
    nhand = max(len(a.get("hands") or []) for a in tape if isinstance(a, dict))
    traj = simulate(tape, nhand)
    iv = crop_timeline(tape, traj, nhand)
    already = watered_tiledays(tape, traj, nhand) if engine_aware else set()
    blocked = [[False] * BOARD for _ in range(BOARD)]

    inserted = skipped = 0
    for k in range(nhand + 1):
        rows = traj[k]
        commits = [r for r in rows if isinstance(r[2], list) and r[2] and r[2][0] in COMMIT]
        for (s1, p1, _), (s2, p2, _) in zip(commits, commits[1:]):
            seg_start, seg_end = s1 + 1, s2
            L = seg_end - seg_start
            if L <= 0:
                continue
            path = bfs_path(p1, p2, blocked, L)
            if path is None:
                continue
            budget = L - len(path)
            if budget <= 0:
                continue

            def try_water(plan, cur):
                """Append a WATER here if it is both useful and affordable.

                The worker executes ``plan[i]`` at step ``seg_start + i``, so the
                step of the next action is always ``seg_start + len(plan)``.
                """
                nonlocal budget, inserted, skipped
                if budget <= 0:
                    return
                t = seg_start + len(plan)
                day = t // 24
                if (cur, day) in already:
                    return
                if engine_aware:
                    ok, _crop = useful_water(iv, cur, t, day)
                    if not ok:
                        skipped += 1
                        return
                elif not is_crop(iv, cur, t):
                    return
                plan.append("WATER")
                already.add((cur, day))
                inserted += 1
                budget -= 1

            plan = []
            cur = p1
            try_water(plan, cur)
            for mv in path:
                try_water(plan, cur)      # water the tile we are standing on
                plan.append(mv)
                dx, dy = MOVES[mv]
                cur = (cur[0] + dx, cur[1] + dy)
            try_water(plan, cur)
            if len(plan) > L:
                continue
            plan.extend(["PASS"] * (L - len(plan)))
            assert len(plan) == L, (len(plan), L)
            for off, op in enumerate(plan):
                step = seg_start + off
                a = copy.deepcopy(tape[step])
                if k == 0:
                    a["farmer"] = [op]
                else:
                    hands = list(a.get("hands") or [])
                    while len(hands) < k:
                        hands.append(["PASS"])
                    hands[k - 1] = [op]
                    a["hands"] = hands
                tape[step] = a

    if verbose:
        print(f"  route {rid}: {len(tape)} steps, {nhand} hands, "
              f"{sum(len(v) for v in iv.values())} plant intervals on {len(iv)} tiles, "
              f"+{inserted} WATER (skipped {skipped} useless)")
    return tape, inserted


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--routes", default="105", help="'all', one id, or a comma list")
    ap.add_argument("--out", default="data/tapeopt/gen105")
    ap.add_argument("--max-detour", type=int, default=3)
    ap.add_argument("--legacy", action="store_true", help="skip engine-aware gating")
    args = ap.parse_args()

    src, m, data = load_blob()
    actions, routes = data["actions"], data["routes"]
    rids = sorted(int(k) for k in routes) if args.routes == "all" else \
        [int(x) for x in args.routes.split(",")]

    index_of = {}
    for i, a in enumerate(actions):
        index_of.setdefault(json.dumps(a, sort_keys=True), i)

    total = 0
    for rid in rids:
        tape, n = enhance_route(actions, routes, rid, args.max_detour,
                                engine_aware=not args.legacy)
        for a in tape:
            key = json.dumps(a, sort_keys=True)
            if key not in index_of:
                index_of[key] = len(actions)
                actions.append(a)
        routes[str(rid)] = [index_of[json.dumps(a, sort_keys=True)] for a in tape]
        total += n

    out_src = src[: m.start(1)] + dump_blob(data) + src[m.end(1):]
    d = ROOT / args.out
    d.mkdir(parents=True, exist_ok=True)
    (d / "main.py").write_text(out_src)
    print(f"inserted {total} WATER turns over {len(rids)} routes; "
          f"actions {len(actions)}, wrote {d/'main.py'} ({len(out_src):,} bytes)")


if __name__ == "__main__":
    main()
