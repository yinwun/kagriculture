#!/usr/bin/env python
"""Herd-TURN edits: change WHEN/HOW OFTEN our own tape lineage buys and places sheep.

Measured motivation (scripts/herd_gate_probe.py, 14 towns): the 6-sheep investment in
the champion's own `_V233` layer fires on only 2 of 14 towns, and the binding gate is
`town.unlocked_shops.count('YARN_STORE') >= 2` -- at seed 9009 every other condition
passes (yarn=1, WOOL price 233 >= 220, WHEAT 41 <= 45, 3 quadrants, no blocked tiles,
shed empty, cash 12,056 against a ~10,000 requirement).  Cash and shed capacity never
bind (0 budget/capacity declines on all 14 towns).

Each variant is ONE narrow, attributable textual edit applied to a built file (never to
the champion itself).  A plan edit can flip the day-6 shop draw (it shares the per-day
RNG stream with weed spawning), so every candidate needs its own full paired duel.

Usage: python scripts/build_herd_turn.py --name yarn1 --base data/forward/wool_drain1_outerprem/main.py
"""
from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

EDITS = {
    # fire the 6-sheep investment when only ONE yarn store is drawn (the measured gate)
    "yarn1": [("count('YARN_STORE')<2", "count('YARN_STORE')<1")],
    # the parent's "one day earlier" test: fire on day 11 instead of day 12
    "d11": [("hour>1 or day!=12", "hour>1 or day!=11")],
    "d13": [("hour>1 or day!=12", "hour>1 or day!=13")],
    # one more sheep at the same step (budget and incoming updated to match)
    "plus1": [("['BUY_ANIMAL','SHEEP',6]", "['BUY_ANIMAL','SHEEP',7]"),
              ("incoming=6+6*initial", "incoming=7+6*initial"),
              ("budget=7000*initial+6*(", "budget=7500*initial+6*(")],
    # yarn1 + one day earlier, the two measured levers together
    "yarn1_d11": [("count('YARN_STORE')<2", "count('YARN_STORE')<1"),
                  ("hour>1 or day!=12", "hour>1 or day!=11")],
}


def build(name, base, out_root=None):
    src = Path(base).read_text()
    edits = EDITS[name]
    for old, new in edits:
        n = src.count(old)
        assert n == 1, f"anchor {old!r} appears {n} times (must be exactly 1)"
        src = src.replace(old, new, 1)
    compile(src, "herd_turn_main.py", "exec")
    root = Path(out_root) if out_root else ROOT / "data" / "herd"
    d = root / name
    d.mkdir(parents=True, exist_ok=True)
    target = d / "main.py"
    target.write_text(src)
    print(f"built {target} sha256 {hashlib.sha256(src.encode()).hexdigest()[:12]} edits={edits} base={base}")
    return target


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--name", required=True)
    ap.add_argument("--base", default=str(ROOT / "data" / "forward" / "wool_drain1_outerprem" / "main.py"))
    ap.add_argument("--out-root", default=None)
    a = ap.parse_args()
    build(a.name, a.base, a.out_root)
