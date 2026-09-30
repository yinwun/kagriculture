#!/usr/bin/env python
"""Build tape-layer candidates: fill idle worker turns with watering work.

Evidence this targets a real gap (top-tier replays vs ours, same game):
  WATER    top 1274-1426  vs ours 1100   (-16..-30%)
  PASS     top 0.8-5.0%   vs ours 7.3%   (idle turns)

Two variants:
  waterfix   conservative - only water the tile the worker is already standing on
  watermove  aggressive   - also walk toward the nearest unwatered plant

Usage: python scripts/build_waterfix.py
"""
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
BASE = ROOT / "data" / "v42clamp" / "main.py"

LAYER = '''

# ================= tape-layer EXP: idle-fill watering =========================
# Top-of-ladder replays water 16-30% more often and idle 9x less than this
# family's plans. Those turns are baked into the action tapes, so this layer
# reclaims them at runtime instead of regenerating tapes.
_WF_PARENT = agent
del agent
_WF_STATS = {"water": 0, "move": 0, "scanned": 0}
_WF_AGGRESSIVE = __AGGRESSIVE__
_WF_MAX_WALK = __MAXWALK__


def _wf_unwatered(farm):
    out = []
    for y, row in enumerate(farm.get("tiles") or []):
        for x, t in enumerate(row):
            if isinstance(t, dict) and t.get("kind") == "PLANT" and not t.get("watered_today"):
                out.append((x, y))
    return out


def _wf_fill(obs, action):
    if not isinstance(action, dict):
        return action
    p = int(obs.get("player", 0))
    farms = obs.get("farms") or []
    if p >= len(farms):
        return action
    farm = farms[p]
    grid = farm.get("tiles") or []
    H, W = len(grid), (len(grid[0]) if grid else 0)
    positions = [list(farm.get("farmer") or [4, 4])] + [list(h) for h in (farm.get("hands") or [])]
    hands = list(action.get("hands") or [])
    while len(hands) < len(positions) - 1:
        hands.append(["PASS"])
    hands = hands[: max(0, len(positions) - 1)]
    cmds = [action.get("farmer")] + hands
    targets = _wf_unwatered(farm)
    if not targets:
        return action
    claimed = set()
    for k, c in enumerate(cmds):
        if k >= len(positions):
            break
        if not (isinstance(c, list) and c and c[0] == "PASS"):
            continue
        x, y = positions[k]
        here = grid[y][x] if (0 <= y < H and 0 <= x < W) else None
        if (isinstance(here, dict) and here.get("kind") == "PLANT"
                and not here.get("watered_today") and (x, y) not in claimed):
            cmds[k] = ["WATER"]
            claimed.add((x, y))
            _WF_STATS["water"] += 1
            continue
        if not _WF_AGGRESSIVE:
            continue
        best = None
        for (px, py) in targets:
            if (px, py) in claimed:
                continue
            d = abs(px - x) + abs(py - y)
            if best is None or d < best[0]:
                best = (d, px, py)
        if best is None or best[0] > _WF_MAX_WALK:
            continue
        _, px, py = best
        if px == x and py == y:
            cmds[k] = ["WATER"]
            _WF_STATS["water"] += 1
        elif abs(px - x) >= abs(py - y):
            cmds[k] = ["EAST"] if px > x else ["WEST"]
        else:
            cmds[k] = ["SOUTH"] if py > y else ["NORTH"]
        claimed.add((px, py))
        _WF_STATS["move"] += 1
    action["farmer"] = cmds[0]
    if len(cmds) > 1:
        action["hands"] = cmds[1:]
    return action


def agent(observation, configuration=None):
    a = _WF_PARENT(observation, configuration)
    try:
        return _wf_fill(observation, a)
    except Exception:
        return a
'''


def build(name, aggressive, max_walk):
    src = BASE.read_text()
    assert "\n_WF_PARENT" not in src, "layer already applied"
    out = src.rstrip("\n") + "\n" + (LAYER
                                     .replace("__AGGRESSIVE__", "True" if aggressive else "False")
                                     .replace("__MAXWALK__", str(max_walk)))
    d = ROOT / "data" / "tapeopt" / name
    d.mkdir(parents=True, exist_ok=True)
    (d / "main.py").write_text(out)
    print(f"  {name:<12} aggressive={aggressive} max_walk={max_walk}  ({len(out):,} bytes)")
    return d


if __name__ == "__main__":
    build("waterfix", aggressive=False, max_walk=0)
    build("watermove", aggressive=True, max_walk=3)
