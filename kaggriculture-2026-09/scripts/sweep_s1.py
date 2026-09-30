#!/usr/bin/env python
"""S1: one dedicated watering sweeper (the uncommanded extra hand).

Design (each choice targets a failure mode we measured earlier):

  * the tape commands at most 11 hands, so we hire a 12th each morning -- that
    worker is NEVER commanded by the tape, so using it cannot break the
    choreography (the failure mode of watermove / wg1-wg3);
  * the sweeper only starts at hour >= START_HOUR, so the tape's own workers get
    first crack at the tiles they were scheduled to water. This avoids a
    *displacement* effect where we water a tile first and the tape worker then
    wastes its WATER turn on an already-watered tile;
  * stateless: it re-runs BFS from its real position every turn.

Mechanism gate: end-of-day unwatered crop rate should fall from ~33.8% toward
<=20% (the top-tier level).

Builds data/tapeopt/sweep1/main.py from the V42 baseline.

Usage: python scripts/sweep_s1.py [--start-hour 12] [--max-d 12]
"""
import argparse
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
BASE = ROOT / "data" / "league" / "ahmedberatozer_kaggriculture-v42-production-that-fits-the-marke" / "main.py"

LAYER = '''

# ============ S1: dedicated watering sweeper on the uncommanded hand =========
_S1_PARENT = agent
del agent
_S1_START_HOUR = __START_HOUR__
_S1_MAX_D = __MAX_D__
_S1_RESERVE = 2000
_S1_REPURPOSE = __REPURPOSE__
_S1_STATS = {"hires": 0, "water": 0, "move": 0, "sweep_turns": 0}
_S1_DAY = {}
_S1_DIRS = (("NORTH", (0, -1)), ("SOUTH", (0, 1)), ("EAST", (1, 0)), ("WEST", (-1, 0)))


def _s1_grid(farm):
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


def _s1_is_goal(tiles):
    def g(x, y):
        t = tiles[y][x]
        return isinstance(t, dict) and t.get("kind") == "PLANT" and not t.get("watered_today")
    return g


def _s1_path(tiles, H, W, blocked, goal, sx, sy, maxd):
    from collections import deque
    if 0 <= sx < W and 0 <= sy < H and not blocked[sy][sx] and goal(sx, sy):
        return []
    q = deque([(sx, sy, 0)])
    prev = {(sx, sy): None}
    found = None
    while q and found is None:
        x, y, d = q.popleft()
        if d >= maxd:
            continue
        for op, (dx, dy) in _S1_DIRS:
            nx, ny = x + dx, y + dy
            if 0 <= nx < W and 0 <= ny < H and not blocked[ny][nx] and (nx, ny) not in prev:
                prev[(nx, ny)] = (x, y, op)
                if goal(nx, ny):
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


def _s1_tape_hands(tape, step):
    if tape is None or not (0 <= step < len(tape)):
        return 0
    a = tape[step]
    if not isinstance(a, dict):
        return 0
    return len(a.get("hands") or [])


def _s1_fill(obs, action):
    if not isinstance(action, dict):
        return action
    p = int(obs.get("player", 0))
    step = int(obs.get("step", 0))
    hour = step % 24
    farm = (obs.get("farms") or [])[p]

    # --- 1. keep one uncommanded hand alive all day (it becomes the sweeper) --
    st = _S1_DAY.get(p)
    day = step // 24
    if st is None or step <= st.get("last", -1) or st.get("day") != day:
        st = _S1_DAY[p] = {"last": -1, "day": day, "tries": 0}
    st["last"] = step

    tape0 = None
    try:
        cst0 = _IMPL.chassis.players.get(p) or {}
        tape0 = _IMPL.chassis.routes.get(cst0.get("route", 0))
    except Exception:
        tape0 = None
    th_now = _s1_tape_hands(tape0, step)
    hands_now = len(farm.get("hands") or [])

    if __REPURPOSE__ and (hands_now <= th_now and st["tries"] < 3
            and farm.get("money", 0) > _S1_RESERVE and hour >= 1):
        market = list(action.get("market") or [])
        if len(market) < 10:
            market.append(["HIRE"])
            st["tries"] += 1
            _S1_STATS["hires"] += 1
        action["market"] = market

    if hour < _S1_START_HOUR:
        return action

    # --- 2. the uncommanded extra hand sweeps for unwatered crops ------------
    tape = None
    try:
        cst = _IMPL.chassis.players.get(p) or {}
        tape = _IMPL.chassis.routes.get(cst.get("route", 0))
    except Exception:
        tape = None
    th = _s1_tape_hands(tape, step)

    positions = [list(farm.get("farmer") or [4, 4])] + [list(h) for h in (farm.get("hands") or [])]
    hands = list(action.get("hands") or [])
    while len(hands) < len(positions) - 1:
        hands.append(["PASS"])
    hands = hands[: max(0, len(positions) - 1)]
    cmds = [action.get("farmer")] + hands
    tiles, H, W, blocked = _s1_grid(farm)
    goal = _s1_is_goal(tiles)

    for k in range(1, len(cmds)):          # never touch the farmer
        if k < th if __REPURPOSE__ else k <= th:
            continue                       # tape owns this worker (all but the last, when repurposing)
        _S1_STATS["sweep_turns"] += 1
        x, y = positions[k]
        if not (0 <= x < W and 0 <= y < H):
            continue
        if goal(x, y):
            cmds[k] = ["WATER"]
            _S1_STATS["water"] += 1
            continue
        path = _s1_path(tiles, H, W, blocked, goal, x, y, _S1_MAX_D)
        if path:
            cmds[k] = [path[0]]
            _S1_STATS["move"] += 1
        # else: leave whatever the parent produced (PASS padding)

    action["farmer"] = cmds[0]
    if len(cmds) > 1:
        action["hands"] = cmds[1:]
    return action


def agent(observation, configuration=None):
    a = _S1_PARENT(observation, configuration)
    try:
        r = _s1_fill(observation, a)
    except Exception:
        r = a
    try:
        if int(observation.get("step", 0)) >= 718:
            import json as _json
            with open("data/_s1_stats.json", "w") as _fh:
                _json.dump(_S1_STATS, _fh)
    except Exception:
        pass
    return r
'''


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--start-hour", type=int, default=12)
    ap.add_argument("--max-d", type=int, default=12)
    ap.add_argument("--out", default="data/tapeopt/sweep1")
    ap.add_argument("--repurpose", type=int, default=0)
    args = ap.parse_args()
    src = BASE.read_text()
    assert "\n_S1_PARENT" not in src
    out = (src.rstrip("\n") + "\n" + LAYER
           .replace("__START_HOUR__", str(args.start_hour))
           .replace("__MAX_D__", str(args.max_d))
           .replace("__REPURPOSE__", "True" if args.repurpose else "False"))
    d = ROOT / args.out
    d.mkdir(parents=True, exist_ok=True)
    (d / "main.py").write_text(out)
    print(f"built {args.out}/main.py (start_hour={args.start_hour}, max_d={args.max_d}, {len(out):,} bytes)")


if __name__ == "__main__":
    main()
