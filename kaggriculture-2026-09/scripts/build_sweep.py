#!/usr/bin/env python
"""Build the `sweep` variant: champion tape + an end-of-day work sweeper.

Why this and not plain idle-filling (measured):

  * the naive layer (work only on the tile the unit already stands on) fired 26
    times per game and changed nothing -- idle units mostly stand on tiles with
    nothing to do (scripts/idle_audit.py: 0.78 idle units/step but 36 pending
    tile-jobs per step, median distance 1).
  * the real deficit against rank-1 is in *missed* work at day end
    (scripts/missed_work.py, per game):

        miss_water  rank-1 16.8   ours 45.8     <- 2.7x more bonus-window
        miss_fert   rank-1 13.3   ours 37.3     <- 2.8x more fertiliser left
        miss_care   rank-1 73.8   ours 20.0     (we are better)
        miss_feed   rank-1 78.6   ours 62.0     (we are better)

  * the engine resets every position at the day rollover (`farmer` respawns, hands
    are dissolved and re-hired), so work done in the *last hours of a day* costs
    nothing positionally.  That is where the slack is free.

So the layer does two things, and nothing else:

  URGENT (any hour): a unit whose tape order is a no-op and which stands on a
    plant that would die at the rollover, or an animal about to escape, fixes it.
  SWEEP (last `sweep_hours` hours): units the tape leaves idle for the next few
    steps are sent to the nearest pending job -- fertiliser to collect, a
    bonus-window watering, a ripe crop -- and do it on arrival.

The tape's own orders are never overridden; only PASS/no-op slots are used, and a
slot is skipped if the tape has real work for it within `sweep_lookahead` steps.

Usage:
  python scripts/build_sweep.py                       # -> data/tapeopt/sweep/main.py
  python scripts/build_sweep.py --hours 8 --out .../sweep8/main.py
"""
import argparse
import hashlib
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

# Crop table for the extra layers (the champion's own table is not in module scope
# at runtime, so the layer carries its own copy of engine 1.32.7 CROPS).
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
    # ---- layer: sweep ----------------------------------------------------------
    def _sweep(self, action, view, step):
        """Spend the crew's idle slots on the farm's most urgent pending work.

        Two regimes: urgent repairs at any hour (a plant that would die at the
        rollover, an animal about to escape), and a general sweep in the last
        `sweep_hours` hours of a day -- positions reset at the rollover, so moving
        an idle unit then costs nothing. Tape orders are never overridden: only
        slots whose order the engine would ignore are touched, and a slot with real
        tape work within `sweep_lookahead` steps is left alone.
        """
        try:
            return self._sweep_inner(action, view, step)
        except Exception:
            self.diagnostics["sweep_errors"] = self.diagnostics.get("sweep_errors", 0) + 1
            return 0

    def _sweep_inner(self, action, view, step):
        cfg = self.cfg
        if not cfg.get("sweep"):
            return 0
        per_day = max(1, _int(cfg.get("turns_per_day", 24)))
        day = step // per_day
        hour = step % per_day
        late = hour >= per_day - _int(cfg.get("sweep_hours", 6))
        budget = _int(cfg.get("sweep_max", 12))
        if budget <= 0:
            return 0

        tape = self.routes.get(getattr(self, "_cur_route", None)) or []
        units = [action.get("farmer") or ["PASS"]] + list(action.get("hands") or [])
        board = view.board

        jobs = self._pending_jobs(view, day, late)
        if not jobs:
            return 0
        claimed = set()
        filled = 0
        for i in range(min(len(units), len(view.positions))):
            if filled >= budget:
                break
            pos = view.positions[i]
            if not isinstance(pos, (list, tuple)) or len(pos) < 2:
                continue
            pos = (_int(pos[0]), _int(pos[1]))
            inv = view.inv(i)
            if self._sweep_busy(tape, step, i, cfg):
                continue
            here = jobs.get(pos)
            if here is not None and not _is_noop(units[i], _tile_at(view.tiles, pos),
                                                 inv, view.seeds, pos, board):
                continue  # the tape already does the right thing here
            if here is not None and pos not in claimed:
                if i == 0:
                    action["farmer"] = here
                else:
                    action["hands"][i - 1] = here
                claimed.add(pos)
                filled += 1
                continue
            if _is_noop(units[i], _tile_at(view.tiles, pos), inv, view.seeds, pos, board):
                if here is not None:
                    continue  # standing on a job we are not allowed to reuse
                target = self._nearest_job(jobs, pos, claimed)
                if target is None:
                    continue
                if target == pos:
                    continue
                mv = self._step_to(pos, target)
                if mv is None:
                    continue
                if i == 0:
                    action["farmer"] = [mv]
                else:
                    action["hands"][i - 1] = [mv]
                filled += 1
        return filled

    def _sweep_busy(self, tape, step, slot, cfg):
        """True when the tape has real (non-move) work for this slot soon."""
        look = _int(cfg.get("sweep_lookahead", 3))
        for k in range(1, look + 1):
            t = step + k
            if not (0 <= t < len(tape)) or not isinstance(tape[t], dict):
                continue
            cmds = [tape[t].get("farmer") or []] + list(tape[t].get("hands") or [])
            if slot < len(cmds):
                c = cmds[slot]
                if isinstance(c, list) and c and c[0] not in MOVES and c[0] != "PASS":
                    return True
        return False

    def _pending_jobs(self, view, day, late):
        """{tile: action} for work worth doing right now, urgent work first."""
        urgent = {}
        normal = {}
        tiles = view.tiles
        for y, row in enumerate(tiles):
            for x, cell in enumerate(row):
                if not isinstance(cell, dict):
                    continue
                kind = _get(cell, "kind")
                pos = (x, y)
                if kind == "PLANT":
                    cd = _LAYER_CROPS.get(_get(cell, "crop"))
                    if not cd:
                        continue
                    age = day - _int(_get(cell, "planted_day", day))
                    units = _int(_get(cell, "yield_units", 0))
                    watered = bool(_get(cell, "watered_today"))
                    if not watered and _int(_get(cell, "consecutive_unwatered", 0)) >= 1:
                        urgent[pos] = ["WATER"]
                        continue
                    if not late:
                        continue
                    if (units > 0 and (age >= cd["first_yield_day"] if cd["ongoing"]
                                       else age >= cd["max_yield_day"] or units >= cd["max_yield"])):
                        normal.setdefault(pos, ["HARVEST"])
                    elif (not watered and not cd["ongoing"] and units < cd["max_yield"]
                          and (cd["max_yield_day"] + 1) // 2 <= age <= cd["max_yield_day"]):
                        normal.setdefault(pos, ["WATER"])
                    elif (self.cfg.get("sweep_fert") and not watered
                          and _int(_get(view.inv(0), "FERTILIZER", 0)) >= 0
                          and _int(_get(cell, "fertilized_until_day", -1)) < day
                          and age <= cd["max_yield_day"]):
                        normal.setdefault(pos, ["WATER"])
                elif kind in ("PASTURE", "COOP") and _get(cell, "animal") is not None:
                    if not _get(cell, "fed_today"):
                        if _int(_get(cell, "consecutive_unfed", 0)) >= 1:
                            urgent[pos] = ["FEED"]
                        elif late:
                            normal.setdefault(pos, ["FEED"])
                    elif not _get(cell, "cared_today") and late:
                        normal.setdefault(pos, ["CARE"])
                    if _get(cell, "fertilizer_available") and late:
                        normal.setdefault(pos, ["COLLECT_FERTILIZER"])
        out = dict(normal)
        out.update(urgent)
        return out

    def _nearest_job(self, jobs, pos, claimed):
        best = None
        bestd = None
        for t in jobs:
            if t in claimed:
                continue
            d = abs(t[0] - pos[0]) + abs(t[1] - pos[1])
            if bestd is None or d < bestd:
                best, bestd = t, d
        return best


    # ---- layer: extra_hands ----------------------------------------------------
    def _extra_hands(self, action, view, step):
        """Hire service hands the tape never planned for.

        The tape's own work is choreographed and cannot absorb extra tasks (the
        measured sweep result), but the crew it hires is also its production
        ceiling: rank-1 and the rank-5 agent both spend more on labour than the
        field (11-14 hands/day) and the mid-game production gap is where we lose
        (rank-1 is +18.7% by day 27 while the endgame is level).  Extra hands are
        hired at the top of a day, cost the usual Fibonacci price, and exist only
        to be picked up by the sweep layer.
        """
        want = _int(self.cfg.get("extra_hands", 0))
        if want <= 0 or step % max(1, _int(self.cfg.get("turns_per_day", 24))) != 0:
            return 0
        already = view.hires_today
        cost = sum(_fib(already + j) for j in range(want))
        reserve = _int(self.cfg.get("extra_hands_reserve", 4000))
        if view.money - cost < reserve:
            return 0
        market = action.setdefault("market", [])
        room = _int(self.cfg.get("max_orders", 10)) - len(market)
        n = max(0, min(want, room))
        for _ in range(n):
            market.append(["HIRE"])
        return n

    def _step_to(self, pos, target):
        dx = target[0] - pos[0]
        dy = target[1] - pos[1]
        if dx == 0 and dy == 0:
            return None
        if abs(dx) >= abs(dy) and dx != 0:
            return "EAST" if dx > 0 else "WEST"
        return "SOUTH" if dy > 0 else "NORTH"
'''


def build(out, hours=6, lookahead=3, max_units=12, fert=True, extra=None,
          extra_hands=0, reserve=4000):
    src = CHAMPION.read_text()
    assert "_pending_jobs" not in src, "already patched"

    anchor = "\ndef make_agent(routes, router=None, opponent_plan=None, **settings):"
    cls = "\nclass Chassis:"
    assert src.count(cls) == 1
    src = src.replace(cls, CROP_TABLE + cls, 1)
    src = src.replace(anchor, LAYER + anchor, 1)

    call = '''            if cfg.get("idle_fill"):
                self._idle_fill(action, view, step)'''
    if call not in src:
        call = '''            if cfg["clamp_sells"]:
                self._clamp_sells(action, projected)'''
    assert src.count(call) == 1, "call anchor not unique"
    src = src.replace(call, call + '''
            if cfg.get("sweep"):
                self._sweep(action, view, step)
            if cfg.get("extra_hands"):
                self._extra_hands(action, view, step)''', 1)

    # remember the route the chassis picked, so the sweep can read tape lookahead
    route_anchor = '''        st["route"] = route
        action = self._route_action(route, step)'''
    assert src.count(route_anchor) == 1
    src = src.replace(route_anchor, '''        st["route"] = route
        self._cur_route = route
        action = self._route_action(route, step)''', 1)

    src = src.replace('    "max_orders": 10,', '    "max_orders": 10,\n'
                      '    "sweep": True,\n'
                      f'    "sweep_hours": {hours},\n'
                      f'    "sweep_lookahead": {lookahead},\n'
                      f'    "sweep_max": {max_units},\n'
                      f'    "sweep_fert": {bool(fert)},\n'
                      f'    "extra_hands": {extra_hands},\n'
                      f'    "extra_hands_reserve": {reserve},', 1)

    old = "'front_run': False}"
    assert src.count(old) == 1
    new = ("'front_run': False, 'sweep': True, "
           f"'sweep_hours': {hours}, 'sweep_lookahead': {lookahead}, "
           f"'sweep_max': {max_units}, 'sweep_fert': {bool(fert)}, "
           f"'extra_hands': {extra_hands}, 'extra_hands_reserve': {reserve}"
           + "".join(f", {k!r}: {v!r}" for k, v in (extra or {}).items()) + "}")
    src = src.replace(old, new, 1)

    out = Path(out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(src)
    print(f"wrote {out} ({len(src):,} bytes, sha256 {hashlib.sha256(src.encode()).hexdigest()[:12]})")
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default=str(ROOT / "data" / "tapeopt" / "sweep" / "main.py"))
    ap.add_argument("--hours", type=int, default=6)
    ap.add_argument("--lookahead", type=int, default=3)
    ap.add_argument("--max-units", type=int, default=12)
    ap.add_argument("--no-fert", action="store_true")
    ap.add_argument("--extra-hands", type=int, default=0)
    ap.add_argument("--reserve", type=int, default=4000)
    args = ap.parse_args()
    build(args.out, hours=args.hours, lookahead=args.lookahead,
          max_units=args.max_units, fert=not args.no_fert,
          extra_hands=args.extra_hands, reserve=args.reserve)
    return 0


if __name__ == "__main__":
    sys.exit(main())
