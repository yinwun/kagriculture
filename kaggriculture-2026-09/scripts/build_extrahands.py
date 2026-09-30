#!/usr/bin/env python
"""Build the "extra hands" tape-layer candidate.

Rationale (measured):
  * Diverting tape-assigned workers off their route destroys the choreography
    (-15k bank, 0/12 seeds, t=-4.6) -- proven negative.
  * The top of the ladder waters 16-30% more and hires ~8% more.
  * A worker that the tape never commands has no post to leave, so extra hands
    hired on top of the plan can be given watering work safely.

Layer does two market/micro things and nothing else:
  1. adds EXTRA_HIRES HIRE orders each morning (respecting a cash reserve),
  2. gives any *extra* hand (one the tape has no command for) watering work.

Usage: python scripts/build_extrahands.py [extra_hires] [max_walk]
"""
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
BASE = ROOT / "data" / "v42clamp" / "main.py"

LAYER = '''

# ============ tape-layer EXP: extra hands for watering ========================
# Tape-assigned workers must stay on their route (proven: diverting them costs
# ~15k bank). Hands the tape never commands have no post to leave, so hire a few
# extra and point them at unwatered plants.
_EH_PARENT = agent
del agent
_EH_EXTRA_HIRES = __EXTRA__
_EH_MAX_WALK = __MAXWALK__
_EH_RESERVE = 2500
_EH_STATS = {"hires": 0, "water": 0, "move": 0, "extra_turns": 0}


def _eh_tape(player):
    try:
        st = _IMPL.chassis.players.get(player) or {}
        route = st.get("route", 0)
        return _IMPL.chassis.routes.get(route) or next(iter(_IMPL.chassis.routes.values()))
    except Exception:
        return None


def _eh_unwatered(farm):
    out = []
    for y, row in enumerate(farm.get("tiles") or []):
        for x, t in enumerate(row):
            if isinstance(t, dict) and t.get("kind") == "PLANT" and not t.get("watered_today"):
                out.append((x, y))
    return out


def _eh_fill(obs, action):
    if not isinstance(action, dict):
        return action
    p = int(obs.get("player", 0))
    step = int(obs.get("step", 0))
    farm = (obs.get("farms") or [])[p]
    grid = farm.get("tiles") or []
    H, W = len(grid), (len(grid[0]) if grid else 0)
    tape = _eh_tape(p)

    # how many hands the tape itself commands at this step
    tape_hands = 0
    if tape is not None and 0 <= step < len(tape):
        t = tape[step]
        if isinstance(t, dict):
            tape_hands = len(t.get("hands") or [])

    # ---- 1. extra morning hires -------------------------------------------
    money = farm.get("money", 0)
    if step % 24 == 3 and _EH_EXTRA_HIRES:
        market = list(action.get("market") or [])
        have = len(farm.get("hands") or [])
        spare = 10 - len(market)
        for _ in range(min(_EH_EXTRA_HIRES, max(0, spare))):
            if money < _EH_RESERVE:
                break
            market.append(["HIRE"])
            _EH_STATS["hires"] += 1
        action["market"] = market

    # ---- 2. give *extra* hands watering work ------------------------------
    positions = [list(farm.get("farmer") or [4, 4])] + [list(h) for h in (farm.get("hands") or [])]
    hands = list(action.get("hands") or [])
    while len(hands) < len(positions) - 1:
        hands.append(["PASS"])
    hands = hands[: max(0, len(positions) - 1)]
    targets = _eh_unwatered(farm)
    if not targets:
        return action
    claimed = set()
    for k in range(len(hands)):
        worker_index = k + 1               # 0 is the farmer
        if worker_index <= tape_hands:     # tape owns this worker -> do not touch
            continue
        c = hands[k]
        _EH_STATS["extra_turns"] += 1
        if not (isinstance(c, list) and c and c[0] == "PASS"):
            continue
        x, y = positions[k + 1]
        here = grid[y][x] if (0 <= y < H and 0 <= x < W) else None
        if (isinstance(here, dict) and here.get("kind") == "PLANT"
                and not here.get("watered_today") and (x, y) not in claimed):
            hands[k] = ["WATER"]
            claimed.add((x, y))
            _EH_STATS["water"] += 1
            continue
        best = None
        for (px, py) in targets:
            if (px, py) in claimed:
                continue
            d = abs(px - x) + abs(py - y)
            if best is None or d < best[0]:
                best = (d, px, py)
        if best is None or best[0] > _EH_MAX_WALK:
            continue
        _, px, py = best
        if px == x and py == y:
            hands[k] = ["WATER"]
            _EH_STATS["water"] += 1
        elif abs(px - x) >= abs(py - y):
            hands[k] = ["EAST"] if px > x else ["WEST"]
        else:
            hands[k] = ["SOUTH"] if py > y else ["NORTH"]
        claimed.add((px, py))
        _EH_STATS["move"] += 1
    if hands:
        action["hands"] = hands
    return action


def agent(observation, configuration=None):
    a = _EH_PARENT(observation, configuration)
    try:
        return _eh_fill(observation, a)
    except Exception:
        return a
'''


def build(name, extra, max_walk):
    src = BASE.read_text()
    assert "\n_EH_PARENT" not in src
    out = src.rstrip("\n") + "\n" + (LAYER
                                    .replace("__EXTRA__", str(extra))
                                    .replace("__MAXWALK__", str(max_walk)))
    d = ROOT / "data" / "tapeopt" / name
    d.mkdir(parents=True, exist_ok=True)
    (d / "main.py").write_text(out)
    print(f"  {name:<14} extra_hires={extra} max_walk={max_walk} ({len(out):,} bytes)")
    return d


if __name__ == "__main__":
    extra = int(sys.argv[1]) if len(sys.argv) > 1 else 2
    walk = int(sys.argv[2]) if len(sys.argv) > 2 else 6
    build(f"eh{extra}w{walk}", extra, walk)
