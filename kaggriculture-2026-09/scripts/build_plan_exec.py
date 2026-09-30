#!/usr/bin/env python
"""Build OUR OWN scheduler/executor agent on top of the tape's agronomic plan.

What is borrowed and what is ours (stated plainly):
  * borrowed: the production notebook's chassis/controller and its market plan
    (the tape's HIRE/BUY/SELL schedule), plus the agronomic plan extracted from
    its tapes (which tile grows which crop on which day);
  * ours: the daily task scheduler and the closed-loop executor.  The tape told
    units where to walk, step by step, and burned 8-10% of its unit-turns idling
    (rank 1: 0.8%).  We keep the plan and re-derive the walking from the live
    observation every turn, so units go where the work is -- including a
    fertilizer round (the tape collects 377 fertilizer and then dumps them at 1
    coin each).

Usage:
  python scripts/build_plan_exec.py --out data/tapeopt/planexec
"""
import argparse
import base64
import collections
import json
import sys
import zlib
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))
from tape_sim2 import load_blob, simulate  # noqa: E402

LAYER = r'''

import collections as _collections_mod

# ================== our scheduler + closed-loop executor =====================
# PLAN[route] = {"p": [[x,y,day,crop]], "h": [[x,y,day]], "a": [[x,y,day,kind]],
#                "s": [[x,y,day,kind]]}   (plants, planned harvests, animals,
#                                          structures)
_CROPS = {"WHEAT": (2, 4, 6), "CARROT": (2, 3, 4), "MELON": (10, 12, 6),
          "TOMATO": (8, 8, 4), "STRAWBERRY": (10, 10, 4)}
_ONGOING = ("TOMATO", "STRAWBERRY")
_SHED = [(4, 4), (5, 4), (4, 5), (5, 5)]
_PROD = ["WHEAT", "CARROT", "TOMATO", "STRAWBERRY", "MELON", "EGG", "MILK",
         "WOOL", "FERTILIZER"]
_BASE_AGENT = agent
_EXEC = {}


def _day_plan(route, day):
    """Tasks the plan asks for on this day (and anything overdue)."""
    pl = _PLAN.get(str(route)) or _PLAN.get(route)
    if not pl:
        return None, None, None
    due_p = [p for p in pl["p"] if p[2] <= day]
    due_h = set()
    for x, y, d in pl["h"]:
        if d == day:
            due_h.add((x, y))
    return due_p, due_h, pl


def _tile(tiles, pos):
    y, x = pos[1], pos[0]
    if 0 <= y < len(tiles) and 0 <= x < len(tiles[y]):
        return tiles[y][x]
    return None


def _build_tasks(obs, player, day, hour, route):
    farm = obs["farms"][player]
    tiles = farm["tiles"]
    priv = obs.get("private") or {}
    shed = priv.get("shed") or {}
    seeds = priv.get("seeds") or {}
    invs = priv.get("inventories") or [{}]
    due_p, due_h, pl = _day_plan(route, day)
    tasks = _collections_mod.defaultdict(list)
    fert_avail = (shed.get("FERTILIZER", 0) or 0)
    for y, row in enumerate(tiles):
        for x, t in enumerate(row):
            if not isinstance(t, dict):
                continue
            if t.get("kind") == "PLANT":
                crop = t.get("crop")
                info = _CROPS.get(crop)
                if not info:
                    continue
                first, maxd, maxy = info
                age = day - t.get("planted_day", day)
                units = t.get("yield_units") or 0
                ripe = units > 0 and age >= first and (
                    units >= 2 or age >= maxd) if crop in _ONGOING else (
                    units > 0 and age >= first and (age >= maxd or units >= maxy))
                if ripe and (x, y) in (due_h or set()) or (ripe and not due_h):
                    tasks["HARVEST"].append((x, y))
                    continue
                if not t.get("watered_today") and (
                        (t.get("consecutive_unwatered") or 0) >= 1
                        or (crop not in _ONGOING and (maxd + 1) // 2 <= age <= maxd)
                        or (crop in _ONGOING and age >= 0)):
                    tasks["WATER"].append((x, y))
                if fert_avail > 0 and (t.get("fertilized_until_day", -1) or -1) < day:
                    if crop in _ONGOING or (maxd + 1) // 2 <= age <= maxd:
                        tasks["FERTILIZE"].append((x, y))
                        fert_avail -= 1
            elif "animal" in t:
                if (t.get("yield_units") or 0) > 0:
                    tasks["HARVEST"].append((x, y))
                if not t.get("fed_today"):
                    tasks["FEED"].append((x, y))
                if not t.get("cared_today"):
                    tasks["CARE"].append((x, y))
                if t.get("fertilizer_available") and (shed.get("FERTILIZER", 0) or 0) < 25:
                    tasks["COLLECT"].append((x, y))
    # animals: build the planned structures and place what the shed holds
    if pl.get("s"):
        free_homes = {}
        for row_y, row in enumerate(tiles):
            for col_x, t in enumerate(row):
                if isinstance(t, dict) and t.get("kind") in ("COOP", "PASTURE") \
                        and "animal" not in t:
                    free_homes.setdefault(t["kind"], []).append((col_x, row_y))
        want = []
        for x, y, d, kind in pl["s"]:
            if d <= day and _tile(tiles, (x, y)) is None:
                want.append((x, y, kind))
        if want and hour <= 16:
            tasks["BUILD"].extend(want[:2])
        for animal in ("COW", "SHEEP", "GOOSE"):
            n = (shed.get(animal, 0) or 0)
            kind = "PASTURE" if animal in ("COW", "SHEEP") else "COOP"
            homes = free_homes.get(kind) or []
            for u in range(min(n, len(homes))):
                tasks["PLACE"].append((homes[u][0], homes[u][1], animal))

    # planting the plan asked for today, on tiles that are actually free
    if due_p and hour <= 16:
        counts = _collections_mod.Counter()
        for row in tiles:
            for t in row:
                if isinstance(t, dict) and t.get("kind") == "PLANT":
                    counts[t.get("crop")] += 1
        for x, y, d, crop in sorted(due_p):
            if seed_left(seeds, crop) <= 0:
                continue
            if _tile(tiles, (x, y)) is None:
                tasks["PLANT"].append((x, y, crop))
                seeds[crop] = seeds.get(crop, 0) - 1
    return tasks


def seed_left(seeds, crop):
    return seeds.get(crop, 0) or 0


def _assign(tasks, positions, keep=None):
    order = ["BUILD", "PLACE", "HARVEST", "WATER", "PLANT", "FERTILIZE", "FEED",
             "CARE", "COLLECT"]
    pool = []
    for kind in order:
        pool.extend([dict(t=t, kind=kind) for t in tasks.get(kind, [])])
    assign = {k: [] for k in range(len(positions))}
    if keep:
        for k, q in keep.items():
            if k in assign:
                assign[k] = q
    cur = {k: (assign[k][-1]["t"][:2] if assign[k] else positions[k])
           for k in assign}
    for task in pool:
        tgt = task["t"][:2]
        best, bd = None, None
        for k in assign:
            if len(assign[k]) >= 20:
                continue
            d = abs(cur[k][0] - tgt[0]) + abs(cur[k][1] - tgt[1])
            if bd is None or d < bd:
                best, bd = k, d
        if best is None:
            continue
        assign[best].append(task)
        cur[best] = tgt
    return assign


def _step_to(pos, tgt):
    dx, dy = tgt[0] - pos[0], tgt[1] - pos[1]
    if dx:
        return ["EAST" if dx > 0 else "WEST"]
    if dy:
        return ["SOUTH" if dy > 0 else "NORTH"]
    return None


def _unit_action(obs, player, k, positions, queue, inv, tiles, shed, day):
    if k >= len(positions):
        return ["PASS"]
    pos = positions[k]
    carry = sum(inv.get(p, 0) for p in _PROD)
    if carry >= 5:
        if tuple(pos) in _SHED:
            return ["DROP"]
        return _step_to(pos, min(_SHED, key=lambda c: abs(c[0] - pos[0]) + abs(c[1] - pos[1]))) or ["PASS"]
    if not queue:
        return ["PASS"]
    task = queue[0]
    tgt = task["t"][:2]
    kind = task["kind"]
    if tuple(pos) != tuple(tgt):
        return _step_to(pos, tgt) or ["PASS"]
    queue.pop(0)
    if kind == "HARVEST":
        return ["HARVEST"]
    if kind == "WATER":
        return ["WATER"]
    if kind == "CARE":
        return ["CARE"]
    if kind == "FEED":
        if inv.get("WHEAT", 0) > 0:
            return ["FEED"]
        queue.insert(0, task)
        queue.insert(0, {"kind": "RELOAD_W", "t": list(min(_SHED, key=lambda c: abs(c[0] - pos[0]) + abs(c[1] - pos[1])))})
        return ["PASS"]
    if kind == "RELOAD_W":
        if tuple(pos) in _SHED:
            return ["PICKUP", "WHEAT", 6]
        return _step_to(pos, tgt) or ["PASS"]
    if kind == "FERTILIZE":
        if inv.get("FERTILIZER", 0) > 0:
            return ["FERTILIZE"]
        queue.insert(0, task)
        queue.insert(0, {"kind": "RELOAD_F", "t": list(min(_SHED, key=lambda c: abs(c[0] - pos[0]) + abs(c[1] - pos[1])))})
        return ["PASS"]
    if kind == "RELOAD_F":
        if tuple(pos) in _SHED and (shed.get("FERTILIZER", 0) or 0) > 0:
            return ["PICKUP", "FERTILIZER", 8]
        if (shed.get("FERTILIZER", 0) or 0) <= 0:
            return ["PASS"]
        return _step_to(pos, tgt) or ["PASS"]
    if kind == "COLLECT":
        return ["COLLECT_FERTILIZER"]
    if kind == "BUILD":
        return [task["t"][2]]
    if kind == "PLACE":
        animal = task["t"][2]
        if inv.get(animal, 0) > 0:
            return ["PLACE", animal]
        queue.insert(0, task)
        queue.insert(0, {"kind": "RELOAD_A", "t": list(min(_SHED, key=lambda c: abs(c[0] - pos[0]) + abs(c[1] - pos[1]))), "a": animal})
        return ["PASS"]
    if kind == "RELOAD_A":
        if tuple(pos) in _SHED and (shed.get(task["a"], 0) or 0) > 0:
            return ["PICKUP", task["a"], 1]
        return ["PASS"]
    if kind == "PLANT":
        queue.insert(0, {"kind": "WATER", "t": [task["t"][0], task["t"][1]]})
        return ["PLANT", task["t"][2]]
    return ["PASS"]


def agent(observation, configuration=None):
    action = _BASE_AGENT(observation, configuration)
    try:
        player = int(observation.get("player") or 0)
        step = int(observation.get("step") or 0)
        day, hour = divmod(step, 24)
        farm = observation["farms"][player]
        tiles = farm["tiles"]
        positions = [tuple(farm.get("farmer") or (4, 4))] + \
                    [tuple(h) for h in (farm.get("hands") or [])]
        chassis = _IMPL.chassis
        route = (chassis.players.get(player) or {}).get("route")
        st = _EXEC.get(player)
        if st is None or step <= st["step"] or step % 24 == 0 or len(positions) != len(st["q"]):
            st = {"step": step, "q": {k: [] for k in range(len(positions))}}
            _EXEC[player] = st
        st["step"] = step
        # rebuild the day's task list every few hours (new crops ripen, hands appear)
        if hour % 3 == 0 or all(not q for q in st["q"].values()):
            tasks = _build_tasks(observation, player, day, hour, route)
            st["q"] = _assign(tasks, positions, keep=st["q"])
            import os as _os
            _f = _os.environ.get("PLANEXEC_DEBUG")
            if _f:
                with open(_f, "a") as _fh:
                    _fh.write("d%d h%02d route=%s units=%d seeds=%s tasks=%s assigned=%s\n" % (
                        day, hour, route, len(positions),
                        {k: v for k, v in (observation.get("private") or {}).get("seeds", {}).items() if v},
                        {k: len(v) for k, v in tasks.items() if v},
                        sum(len(v) for v in st["q"].values())))
        priv = observation.get("private") or {}
        invs = priv.get("inventories") or [{}]
        shed = priv.get("shed") or {}
        hands = []
        for k in range(len(positions)):
            inv = invs[k] if k < len(invs) else {}
            hands.append(_unit_action(observation, player, k, positions, st["q"].get(k, []),
                                      inv, tiles, shed, day))
        action["farmer"] = hands[0]
        action["hands"] = hands[1:]
    except Exception:
        import os as _os, traceback as _tb
        _f = _os.environ.get("PLANEXEC_DEBUG")
        if _f:
            with open(_f, "a") as _fh:
                _fh.write(_tb.format_exc() + "\n")
    return action
'''


def build_plan(data):
    plan = {}
    for rid in sorted(int(k) for k in data["routes"]):
        tape = [data["actions"][i] for i in data["routes"][str(rid)]]
        nhand = max(len(a.get("hands") or []) for a in tape if isinstance(a, dict))
        traj = simulate(tape, nhand)
        p, h, a, s = [], [], [], []
        for k, rows in traj.items():
            for step, pos, c in rows:
                if not (isinstance(c, list) and c and pos is not None):
                    continue
                day = step // 24
                if c[0] == "PLANT" and len(c) > 1:
                    p.append([pos[0], pos[1], day, c[1]])
                elif c[0] == "HARVEST":
                    h.append([pos[0], pos[1], day])
                elif c[0] == "PLACE" and len(c) > 1 and c[1] in ("GOOSE", "COW", "SHEEP"):
                    a.append([pos[0], pos[1], day, c[1]])
                elif c[0] in ("BUILD_COOP", "BUILD_PASTURE"):
                    s.append([pos[0], pos[1], day, c[0]])
        # keep only the first plant per tile-day and unique harvest tile-days
        seen = set()
        pp = []
        for e in sorted(p):
            key = (e[0], e[1], e[2])
            if key in seen:
                continue
            seen.add(key)
            pp.append(e)
        hh = sorted({(e[0], e[1], e[2]) for e in h})
        plan[str(rid)] = {"p": pp, "h": [list(x) for x in hh], "a": a, "s": s}
    return plan


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default="data/tapeopt/planexec")
    ap.add_argument("--base", default=None)
    args = ap.parse_args()
    src, m, data = load_blob(args.base) if args.base else load_blob()
    plan = build_plan(data)
    raw = json.dumps(plan, separators=(",", ":")).encode()
    blob = base64.b85encode(zlib.compress(raw, 9)).decode()
    decoder = ('_PLAN_B = %r\n'
               '_PLAN = __import__("json").loads(__import__("zlib").decompress(\n'
               '    __import__("base64").b85decode(_PLAN_B)))\n' % blob)
    out_src = src + "\n\n" + decoder + LAYER
    d = ROOT / args.out
    d.mkdir(parents=True, exist_ok=True)
    (d / "main.py").write_text(out_src)
    tot_p = sum(len(v["p"]) for v in plan.values())
    tot_h = sum(len(v["h"]) for v in plan.values())
    print(f"embedded plans for {len(plan)} routes ({tot_p} plants, {tot_h} harvest tile-days, "
          f"{len(blob):,} chars); wrote {d/'main.py'} ({len(out_src):,} bytes)")


if __name__ == "__main__":
    main()
