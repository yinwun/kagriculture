#!/usr/bin/env python
"""Simulate a V42-family route and measure reclaimable slack.

The gap checklist says the top agents spend their worker turns watering while we
PASS ~7% of ours. Whether those PASSes can be converted to watering *without
breaking the choreography* is a position-constraint question:

  * a worker's next committing action (PICKUP/DROP/PLANT/HARVEST/PLACE/FEED/CARE)
    requires it to be on a specific tile at a specific step;
  * converting a PASS to "walk somewhere and back" is only safe if the worker can
    return to that required tile in time.

This simulator plays the route forward, tracks every worker's [x,y] through the
whole 719 steps, and reports:
  - each worker's total PASS count,
  - the "dead windows" (consecutive PASS-only runs) and their length,
  - the worker's next required position + how many steps away it is committed,
  - hence the maximum number of turns that could be spent away-and-back.

It does NOT decide what to water (that is seed/state dependent); it only
measures the *slack budget* the choreography leaves us.

Usage: python scripts/tape_sim.py [--route 105]
"""
import argparse
import json
import re
import zlib
import base64
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
BASE = ROOT / "data" / "v42clamp" / "main.py"

MOVES = {"NORTH": (0, -1), "SOUTH": (0, 1), "EAST": (1, 0), "WEST": (-1, 0)}
COMMIT = {"PICKUP", "DROP", "PLANT", "HARVEST", "BUILD_COOP", "BUILD_PASTURE",
          "PLACE", "FEED", "CARE", "COLLECT_FERTILIZER", "DIG", "WATER", "FERTILIZE"}


def load_data():
    src = Path(BASE).read_text()
    m = re.search(r"b85decode\('([^']+)'\)", src)
    return json.loads(zlib.decompress(base64.b85decode(m.group(1))))


def resolve_route(data, route_id):
    actions, routes = data["actions"], data["routes"]
    ids = routes[str(route_id)]
    return [actions[i] for i in ids]


def hand_count(tape):
    return max((len(a.get("hands") or []) for a in tape), default=0)


def simulate(tape):
    """Return per-step per-worker position [x,y] (0=farmer, 1..=hands)."""
    # initial: farmer [4,4]; hands spawn at shed-adjacent? -> unknown, track from actions.
    # We track positions from the farmer start and hand HIRE assumptions; hands only
    # exist after HIRE orders. For slack analysis we only need *relative* continuity.
    nhand = hand_count(tape)
    pos = [[4, 4]] + [[None, None] for _ in range(nhand)]
    hires = 0
    snapshots = []
    for step, a in enumerate(tape):
        cmds = [a.get("farmer") or ["PASS"]] + list(a.get("hands") or [])
        # count HIREs -> spawn a hand at (4,4) next to shed (approx)
        for o in (a.get("market") or []):
            if o and o[0] == "HIRE":
                hires += 1
                if hires <= nhand:
                    pos[hires] = [4, 4]
        # apply worker commands in place
        for k, c in enumerate(cmds):
            if k >= len(pos):
                break
            if not (isinstance(c, list) and c):
                continue
            op = c[0]
            if op in MOVES and pos[k][0] is not None:
                dx, dy = MOVES[op]
                pos[k] = [pos[k][0] + dx, pos[k][1] + dy]
        snapshots.append([list(p) if p[0] is not None else None for p in pos])
    return snapshots


def slack_windows(tape):
    """For each worker, find runs of consecutive PASS commands, with the distance
    (in steps) to its next COMMIT action. A window of length L with next-commit
    at distance D lets the worker spend up to (L) steps walking+watering as long
    as it returns within D steps. The safe 'round-trip' budget at the START of a
    window is roughly floor(L/2) steps of walking out and back."""
    nhand = hand_count(tape)
    windows = []
    for k in range(nhand + 1):
        i = 0
        while i < len(tape):
            cmd = [tape[i].get("farmer")] + list(tape[i].get("hands") or [])
            c = cmd[k] if k < len(cmd) else None
            if isinstance(c, list) and c and c[0] == "PASS":
                j = i
                while j < len(tape):
                    cmdj = [tape[j].get("farmer")] + list(tape[j].get("hands") or [])
                    cj = cmdj[k] if k < len(cmdj) else None
                    if isinstance(cj, list) and cj and cj[0] == "PASS":
                        j += 1
                    else:
                        break
                L = j - i
                # distance to next commit for this worker
                dist = 0
                t = j
                while t < len(tape):
                    cmdt = [tape[t].get("farmer")] + list(tape[t].get("hands") or [])
                    ct = cmdt[k] if k < len(cmdt) else None
                    if isinstance(ct, list) and ct and ct[0] in COMMIT:
                        break
                    dist += 1
                    t += 1
                if L >= 2:
                    windows.append((k, i, L, dist))
                i = j
            else:
                i += 1
    return windows


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--route", type=int, default=105)
    args = ap.parse_args()
    data = load_data()
    tape = resolve_route(data, args.route)
    print(f"route {args.route}: {len(tape)} steps, hands={hand_count(tape)}")
    wins = slack_windows(tape)
    total_pass = sum(w[2] for w in wins)
    # a window of length L with round-trip allows floor(L/2) walk-out + 1 water + floor(L/2) walk-back
    reclaim = sum(w[2] // 2 for w in wins)
    print(f"PASS runs (len>=2): {len(wins)}  total PASS turns in them: {total_pass}")
    print(f"naive reclaimable (walk-out+water+walk-back, L//2): {reclaim}")
    print(f"\n最长 12 个空窗: (worker, start_step, length, dist_to_next_commit)")
    for w in sorted(wins, key=lambda x: -x[2])[:12]:
        print(f"   worker={w[0]:>2} start={w[1]:>3} len={w[2]:>3} next_commit_in={w[3]:>3} steps")
    # note: worker 0 = farmer; 1..N = hands


if __name__ == "__main__":
    main()
