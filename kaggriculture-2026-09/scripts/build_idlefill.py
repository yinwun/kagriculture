#!/usr/bin/env python
"""Build the `idlefill` variant: champion tape + an idle-slot work layer.

Motivation (measured, see REPORT-overnight-plan-2.md): the champion tape wastes
7.6-8.5% of its unit-commands on PASS while rank-1 runs at 0.9%, waters 26% more
and fertilises 37% more.  The tape itself cannot be edited safely -- hands are
daily labourers, so slot k is a different worker every day and path-level edits
do not survive -- so the fix is a runtime layer:

    whenever the tape's order for a unit is one the engine would ignore anyway
    (PASS / provably no-op), replace it with the best action available ON THE TILE
    THE UNIT ALREADY STANDS ON.

That keeps the scripted route untouched (no re-targeting, no movement) and turns
dead worker-turns into watering / feeding / care / fertiliser collection /
harvesting / weeding.

Usage:
  python scripts/build_idlefill.py                       # -> data/tapeopt/idlefill/main.py
  python scripts/build_idlefill.py --out data/tapeopt/idlefill_fert/main.py --fert
"""
import argparse
import hashlib
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

CROP_TABLE = """
_LAYER_CROPS = {
    "WHEAT":      {"first_yield_day": 2,  "max_yield_day": 4,  "max_yield": 6, "ongoing": False},
    "CARROT":     {"first_yield_day": 2,  "max_yield_day": 3,  "max_yield": 4, "ongoing": False},
    "TOMATO":     {"first_yield_day": 8,  "max_yield_day": 8,  "max_yield": 4, "ongoing": True},
    "STRAWBERRY": {"first_yield_day": 10, "max_yield_day": 10, "max_yield": 4, "ongoing": True},
    "MELON":      {"first_yield_day": 10, "max_yield_day": 12, "max_yield": 6, "ongoing": False},
}
"""
CHAMPION = ROOT / "data" / "tapeopt" / "rgcs" / "main.py"

LAYER = '''
    # ---- layer: idle_fill ------------------------------------------------------
    def _idle_fill(self, action, view, step):
        """Turn units the tape leaves idle into useful work on their own tile.

        Only slots whose tape order the engine would ignore are touched, and only
        with work available on the tile the unit already occupies, so the scripted
        route is never disturbed (hands are re-hired daily, so the tape cannot be
        edited positionally instead).
        """
        try:
            return self._idle_fill_inner(action, view, step)
        except Exception:
            self.diagnostics["idle_fill_errors"] = self.diagnostics.get("idle_fill_errors", 0) + 1
            return 0

    def _idle_fill_inner(self, action, view, step):
        budget = _int(self.cfg.get("idle_fill_max", 0))
        if budget <= 0:
            return 0
        day = step // max(1, _int(self.cfg.get("turns_per_day", 24)))
        units = [action.get("farmer") or ["PASS"]] + list(action.get("hands") or [])
        filled = 0
        for i in range(min(len(units), len(view.positions))):
            if filled >= budget:
                break
            pos = view.positions[i]
            if not isinstance(pos, (list, tuple)) or len(pos) < 2:
                continue
            tile = _tile_at(view.tiles, pos)
            inv = view.inv(i)
            if not _is_noop(units[i], tile, inv, view.seeds, pos, view.board):
                continue
            work = self._idle_work(tile, inv, view, day)
            if work is None:
                continue
            if i == 0:
                action["farmer"] = work
            else:
                action["hands"][i - 1] = work
            filled += 1
        return filled

    def _idle_work(self, tile, inv, view, day):
        """Best action available on this unit's own tile, or None.

        Tile kinds are disjoint, so the order only matters within a kind: save a
        crop that would die, then keep watering while the bonus window pays, then
        harvest; on an animal tile prevent a loss (feed), then double the output
        (care), then take the free fertiliser.
        """
        if not isinstance(tile, dict):
            return None
        kind = _get(tile, "kind")
        if kind == "PLANT":
            cd = _LAYER_CROPS.get(_get(tile, "crop"))
            if not cd:
                return None
            age = day - _int(_get(tile, "planted_day", day))
            unwatered = _int(_get(tile, "consecutive_unwatered", 0))
            units = _int(_get(tile, "yield_units", 0))
            watered = bool(_get(tile, "watered_today"))
            if not watered and unwatered >= 1:
                return ["WATER"]
            if (not watered and not cd["ongoing"] and units < cd["max_yield"]
                    and (cd["max_yield_day"] + 1) // 2 <= age <= cd["max_yield_day"]):
                return ["WATER"]
            if units > 0:
                if cd["ongoing"]:
                    if age >= cd["first_yield_day"]:
                        return ["HARVEST"]
                elif age >= cd["max_yield_day"] or units >= cd["max_yield"]:
                    return ["HARVEST"]
            if (self.cfg.get("idle_fert") and not watered
                    and _int(_get(inv, "FERTILIZER", 0)) > 0
                    and _int(_get(tile, "fertilized_until_day", -1)) < day
                    and age <= cd["max_yield_day"]):
                return ["FERTILIZE"]
            return None
        if kind in ("PASTURE", "COOP"):
            if _get(tile, "animal") is None:
                return None
            if not _get(tile, "fed_today") and _int(_get(inv, "WHEAT", 0)) > 0:
                return ["FEED"]
            if not _get(tile, "cared_today"):
                return ["CARE"]
            if _get(tile, "fertilizer_available"):
                return ["COLLECT_FERTILIZER"]
            return None
        if kind == "WEED":
            return ["DIG"]
        return None
'''


def build(out, fert=False, max_fill=12, extra_settings=None):
    src = CHAMPION.read_text()
    assert "def _idle_fill" not in src, "champion already patched"

    anchor = "\ndef make_agent(routes, router=None, opponent_plan=None, **settings):"
    assert src.count(anchor) == 1
    cls = "\nclass Chassis:"
    assert src.count(cls) == 1
    src = src.replace(cls, CROP_TABLE + cls, 1)
    src = src.replace(anchor, LAYER + anchor)

    call_anchor = '''            if cfg["clamp_sells"]:
                self._clamp_sells(action, projected)'''
    assert src.count(call_anchor) == 1
    src = src.replace(call_anchor, call_anchor + '''
            if cfg.get("idle_fill"):
                self._idle_fill(action, view, step)''')

    # tunables land in DEFAULT_SETTINGS (so Chassis.cfg always has them) ...
    src = src.replace('    "max_orders": 10,',
                      '    "max_orders": 10,\n    "idle_fill": True,\n'
                      f'    "idle_fill_max": {max_fill},\n'
                      f'    "idle_fert": {bool(fert)},', 1)
    # ... and in the module-level _SETTINGS the production agent is built with.
    old = "'front_run': False}"
    assert src.count(old) == 1
    new = ("'front_run': False, 'idle_fill': True, "
           f"'idle_fill_max': {max_fill}, 'idle_fert': {bool(fert)}"
           + "".join(f", {k!r}: {v!r}" for k, v in (extra_settings or {}).items()) + "}")
    src = src.replace(old, new, 1)

    out = Path(out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(src)
    print(f"wrote {out} ({len(src):,} bytes, sha256 {hashlib.sha256(src.encode()).hexdigest()[:12]})")
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default=str(ROOT / "data" / "tapeopt" / "idlefill" / "main.py"))
    ap.add_argument("--fert", action="store_true", help="also fertilise when idle")
    ap.add_argument("--max-fill", type=int, default=12)
    args = ap.parse_args()
    build(args.out, fert=args.fert, max_fill=args.max_fill)
    return 0


if __name__ == "__main__":
    sys.exit(main())
