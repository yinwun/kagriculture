#!/usr/bin/env python
"""Build the return-to-post watering scheduler (waterfill_safe).

The gap checklist says the top agents spend their worker turns watering while we
PASS ~7% of ours. Earlier runtime attempts failed because they moved workers
without guaranteeing they'd be back on their exact tile before the next
position-dependent action.

This layer only converts an *all-PASS standing window* into a CLOSED LOOP:
walk (BFS) to the nearest unwatered plant, WATER, and walk back along the exact
reverse path. Because the loop ends on the start tile, the tape's later actions
(which assumed the worker never moved) stay valid. No move ever steps off-board,
onto LOCKED, or onto a COOP/PASTURE; WATER is downgraded to PASS if the plant
was watered by someone else in the meantime.

Builds data/tapeopt/waterfill_safe/main.py from the V42 baseline.

Usage: python scripts/waterfill_safe.py [--max-d 4]
"""
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
BASE = ROOT / "data" / "league" / "ahmedberatozer_kaggriculture-v42-production-that-fits-the-marke" / "main.py"

LAYER = '''

# ============ waterfill_safe: closed-loop idle -> watering ====================
_WF_PARENT = agent
del agent
_WF_MAX_D = __MAX_D__
_WF_STATES = {}
_WF_STATS = {"pass":0, "win_ok":0, "path_found":0, "started":0, "win_hist": {}}
_WF_REV = {"NORTH": "SOUTH", "SOUTH": "NORTH", "EAST": "WEST", "WEST": "EAST"}
_WF_DIRS = (("NORTH", (0, -1)), ("SOUTH", (0, 1)), ("EAST", (1, 0)), ("WEST", (-1, 0)))


def _wf_grid(farm):
    tiles = farm.get("tiles") or []
    H = len(tiles)
    W = len(tiles[0]) if H else 0
    blocked = [[False] * W for _ in range(H)]
    for y in range(H):
        for x in range(W):
            t = tiles[y][x]
            if t == "LOCKED" or (isinstance(t, dict) and t.get("kind") in ("COOP", "PASTURE")):
                blocked[y][x] = True
    return tiles, H, W, blocked


def _wf_goal(tiles):
    def g(x, y):
        t = tiles[y][x]
        return isinstance(t, dict) and t.get("kind") == "PLANT" and not t.get("watered_today")
    return g


def _wf_path(tiles, H, W, blocked, sx, sy, maxd):
    from collections import deque
    if 0 <= sx < W and 0 <= sy < H and not blocked[sy][sx] and _wf_goal(tiles)(sx, sy):
        return []
    q = deque([(sx, sy, 0)])
    prev = {(sx, sy): None}
    found = None
    while q and found is None:
        x, y, d = q.popleft()
        if d >= maxd:
            continue
        for op, (dx, dy) in _WF_DIRS:
            nx, ny = x + dx, y + dy
            if 0 <= nx < W and 0 <= ny < H and not blocked[ny][nx] and (nx, ny) not in prev:
                prev[(nx, ny)] = (x, y, op)
                if _wf_goal(tiles)(nx, ny):
                    found = (nx, ny)
                    break
                q.append((nx, ny, d + 1))
    if found is None:
        return None
    path = []
    x, y = found
    while (x, y) != (sx, sy):
        px, py, op = prev[(x, y)]
        path.append(op)
        x, y = px, py
    path.reverse()
    return path


def _wf_window(tape, step, k):
    """consecutive PASS length for worker k starting at `step`."""
    n = len(tape)
    t = step
    while t < n:
        a = tape[t]
        if not isinstance(a, dict):
            break
        cmds = [a.get("farmer")] + list(a.get("hands") or [])
        c = cmds[k] if k < len(cmds) else None
        if isinstance(c, list) and c and c[0] == "PASS":
            t += 1
        else:
            break
    return t - step


def _wf_fill(obs, action):
    if not isinstance(action, dict):
        return action
    p = int(obs.get("player", 0))
    step = int(obs.get("step", 0))
    farm = (obs.get("farms") or [])[p]
    st = _WF_STATES.get(p)
    if st is None or step <= st.get("last", -1):
        st = _WF_STATES[p] = {"last": -1, "detours": {}}
    st["last"] = step

    positions = [list(farm.get("farmer") or [4, 4])] + [list(h) for h in (farm.get("hands") or [])]
    hands = list(action.get("hands") or [])
    while len(hands) < len(positions) - 1:
        hands.append(["PASS"])
    hands = hands[: max(0, len(positions) - 1)]
    cmds = [action.get("farmer")] + hands
    detours = st["detours"]

    tape = None
    try:
        cst = _IMPL.chassis.players.get(p) or {}
        route = cst.get("route", 0)
        tape = _IMPL.chassis.routes.get(route)
    except Exception:
        tape = None

    tiles = H = W = blocked = None
    if tape is not None:
        tiles, H, W, blocked = _wf_grid(farm)

    # 1) continue active detours (they are closed loops -> safe)
    for k in list(detours.keys()):
        if k >= len(cmds):
            detours.pop(k)
            continue
        d = detours[k]
        if not d:
            detours.pop(k)
            continue
        nxt = d[0]
        if nxt == "WATER":
            # downgrade if the plant is no longer unwatered / we aren't on a plant
            x, y = positions[k]
            t = tiles[y][x] if (tiles is not None and 0 <= y < H and 0 <= x < W) else None
            if not (isinstance(t, dict) and t.get("kind") == "PLANT" and not t.get("watered_today")):
                nxt = "PASS"
        cmds[k] = [nxt]
        d.pop(0)
        if not d:
            detours.pop(k)

    # 2) start new detours for PASSing workers in a long enough standing window
    if tape is not None:
        goal = _wf_goal(tiles)
        for k in range(len(cmds)):
            if k in detours:
                continue
            c = cmds[k]
            if not (isinstance(c, list) and c and c[0] == "PASS"):
                continue
            win = _wf_window(tape, step, k)
            _WF_STATS["pass"] += 1
            _WF_STATS["win_hist"][win] = _WF_STATS["win_hist"].get(win, 0) + 1
            if win < 3:
                continue
            _WF_STATS["win_ok"] += 1
            maxd = min(_WF_MAX_D, (win - 1) // 2)
            x, y = positions[k]
            if not (0 <= x < W and 0 <= y < H and not blocked[y][x]):
                continue
            path = _wf_path(tiles, H, W, blocked, x, y, maxd)
            if path is None:
                continue
            _WF_STATS["path_found"] += 1
            if 2 * len(path) + 1 > win:
                continue
            detour = list(path) + ["WATER"] + [_WF_REV[m] for m in reversed(path)]
            detours[k] = detour
            nxt = detour[0]
            if nxt == "WATER":
                t = tiles[y][x] if (0 <= y < H and 0 <= x < W) else None
                if not (isinstance(t, dict) and t.get("kind") == "PLANT" and not t.get("watered_today")):
                    nxt = "PASS"
            cmds[k] = [nxt]
            detours[k].pop(0)
            _WF_STATS["started"] += 1
            if not detours[k]:
                detours.pop(k)

    action["farmer"] = cmds[0]
    if len(cmds) > 1:
        action["hands"] = cmds[1:]
    return action


def agent(observation, configuration=None):
    a = _WF_PARENT(observation, configuration)
    try:
        r = _wf_fill(observation, a)
    except Exception:
        r = a
    try:
        if int(observation.get("step", 0)) >= 718 and not getattr(_WF_STATS, "_dumped", False):
            import json as _json
            with open("data/_wf_stats.json", "w") as _fh:
                _json.dump(_WF_STATS, _fh)
            _WF_STATS["_dumped"] = True
    except Exception:
        pass
    return r
'''


def build(max_d):
    src = BASE.read_text()
    assert "\n_WF_PARENT" not in src
    out = src.rstrip("\n") + "\n" + LAYER.replace("__MAX_D__", str(max_d))
    d = ROOT / "data" / "tapeopt" / "waterfill_safe"
    d.mkdir(parents=True, exist_ok=True)
    (d / "main.py").write_text(out)
    print(f"built data/tapeopt/waterfill_safe/main.py (max_d={max_d}, {len(out):,} bytes)")


if __name__ == "__main__":
    md = int(sys.argv[1]) if len(sys.argv) > 1 else 4
    build(md)
