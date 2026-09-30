#!/usr/bin/env python
"""plan_v0 -- a needs-driven day scheduler, written to be recorded into a tape.

Design (from REPORT-tape-replan-methodology.md):

  * the daily job list is dictated by the engine: water every plant every day
    (ongoing crops need it to survive, one-shot crops need it inside the bonus
    window), feed + care + collect fertiliser for every animal, harvest ripe
    crops, plant the portfolio schedule, and trade;
  * the crew is the binding constraint (units x 24 steps, ~40% of it spent
    walking), so jobs are assigned zone-first and nearest-first instead of
    replaying a fixed positional trajectory;
  * every action is derived from the live observation, so the resulting game can
    be *recorded* into a 719-step tape (scripts/record_plan.py) and replayed by
    the champion chassis in any town -- which is how we A/B it.

Spec targets taken from rank-1's measured profile (per day): 12 hands from day 10,
~52 crop tiles and ~15 animals by day 10, water coverage ~1.0 (every plant every
day), animal ops ~3 per animal per day, idle <2%.

Usage:
  python scripts/plan_v0.py --selftest --seed 900            # play vs starter, print L1
  python scripts/plan_v0.py --selftest --seed 900 --opponent <main.py>
"""
import argparse
import collections
import json
from pathlib import Path

CROPS = {
    "WHEAT":      {"seed": 10,  "first_yield_day": 2,  "max_yield_day": 4,  "interval": 0, "max_yield": 6, "ongoing": False},
    "CARROT":     {"seed": 20,  "first_yield_day": 2,  "max_yield_day": 3,  "interval": 0, "max_yield": 4, "ongoing": False},
    "TOMATO":     {"seed": 50,  "first_yield_day": 8,  "max_yield_day": 8,  "interval": 1, "max_yield": 4, "ongoing": True},
    "STRAWBERRY": {"seed": 100, "first_yield_day": 10, "max_yield_day": 10, "interval": 2, "max_yield": 4, "ongoing": True},
    "MELON":      {"seed": 80,  "first_yield_day": 10, "max_yield_day": 12, "max_yield": 6, "ongoing": False},
}
ANIMALS = {
    "COW":   {"cost": 400, "structure": "PASTURE", "first_yield_day": 8, "interval": 2, "max_held": 6, "product": "MILK"},
    "SHEEP": {"cost": 500, "structure": "PASTURE", "first_yield_day": 6, "interval": 3, "max_held": 6, "product": "WOOL"},
    "GOOSE": {"cost": 300, "structure": "COOP",    "first_yield_day": 4, "interval": 1, "max_held": 4, "product": "EGG"},
}
PRODUCTS = ("WHEAT", "CARROT", "TOMATO", "STRAWBERRY", "MELON", "EGG", "MILK", "WOOL", "FERTILIZER")
# engine 1.32.7 base prices: the reference point for "is this price worth selling at"
BASE_PRICE = {"WHEAT": 25, "CARROT": 35, "TOMATO": 60, "STRAWBERRY": 120, "MELON": 250,
              "EGG": 50, "MILK": 160, "WOOL": 200, "FERTILIZER": 100}
BALLAST = ("WHEAT", "EGG", "FERTILIZER", "CARROT")   # deep books: sell whenever
MOVES = {"NORTH": (0, -1), "SOUTH": (0, 1), "EAST": (1, 0), "WEST": (-1, 0), "PASS": (0, 0)}
SHED = ((4, 4), (5, 4), (4, 5), (5, 5))
LAND_PRICES = [1000, 2000, 4000]

# ---- portfolio schedule, copied from rank-1's measured planting profile -------
PLANT_SCHEDULE = {
    0:  (("MELON", 6), ("WHEAT", 9)),
    1:  (("MELON", 4),),
    2:  (("STRAWBERRY", 2),),
    3:  (("STRAWBERRY", 2),),
    4:  (("STRAWBERRY", 4),),
    6:  (("STRAWBERRY", 10), ("WHEAT", 3)),
    7:  (("STRAWBERRY", 3),),
    9:  (("WHEAT", 15),),
    12: (("WHEAT", 6),),
    15: (("WHEAT", 7), ("TOMATO", 2)),
    18: (("WHEAT", 5), ("TOMATO", 3), ("CARROT", 2)),
    21: (("WHEAT", 7), ("CARROT", 4)),
    24: (("WHEAT", 9), ("CARROT", 8)),
    27: (("CARROT", 6), ("WHEAT", 5)),
}
# animals: slow ramp, cows first (rank-1 ends a game with ~12 cows + ~6 sheep)
ANIMAL_SCHEDULE = {
    0: (("SHEEP", 3), ("COW", 2)),   # rank-1: 5 pastures + 2 cow + 3 sheep on day 0
                                     # (sheep first: 6-day first yield funds the land)
    6: (("COW", 5), ("SHEEP", 1)),   # second batch, funded by the day-6 wool
    8: (("COW", 4),),
}

# Premium portfolio: the reference agent's own revenue mix is strawberry 105u,
# melon 48u, milk 132u at prices far above base, i.e. it grows *value* rather than
# bulk wheat.  Selected at runtime when the world (shops + realised prices) says
# the premium books are the deep ones.
PREMIUM_SCHEDULE = {
    0:  (("MELON", 8), ("WHEAT", 4)),
    2:  (("STRAWBERRY", 6),),
    4:  (("STRAWBERRY", 8),),
    6:  (("STRAWBERRY", 10), ("WHEAT", 3)),
    9:  (("STRAWBERRY", 8), ("WHEAT", 6)),
    12: (("STRAWBERRY", 8), ("WHEAT", 4), ("TOMATO", 2)),
    15: (("STRAWBERRY", 6), ("WHEAT", 4), ("TOMATO", 3)),
    18: (("STRAWBERRY", 6), ("WHEAT", 4), ("CARROT", 3)),
    21: (("STRAWBERRY", 6), ("WHEAT", 5), ("CARROT", 3)),
    24: (("STRAWBERRY", 6), ("WHEAT", 5), ("CARROT", 4)),
    27: (("STRAWBERRY", 4), ("WHEAT", 4), ("CARROT", 4)),
}

LAND_DAYS = (6, 9)

# Every knob the sweep may turn.  Structure (the needs-driven scheduler, the aging
# claim rule, the pen geometry) is not a parameter: a sweep over a broken structure
# only finds the best of a bad family.
DEFAULTS = {
    "hire_mult": 1.9,        # crew size = workload * hire_mult / 24 steps
    "hire_min": 4,
    "hire_cap": 12,
    "claim_slack": 2,        # priority window inside which the nearest job wins
    "age_div": 8,            # aging: effective prio = prio - age // age_div
    "feed_days": 3,          # days of feed held per animal
    "feed_reserve": 8,
    "land_first_day": 6,
    "land_reserve": 150,
    "sell_batch": 20,
    "portfolio": "rank1",    # "rank1" = the measured rank-1 planting schedule,
                             # "spec" = the reference tape's own seeds-per-day
                             # (its portfolio is what its market plan is tuned for)
    "portfolio_spec": {},
    "place_phase_days": 0,
    "place_phase_units_early": 3,
    "market_mode": "auto",   # "auto" = own policy; "spec" = execute the day-indexed
                             # plan extracted from the reference tape
                             # (scripts/extract_market_spec.py)
    "market_spec": {},
    "spec_batch": 6,          # units per sell order when replaying a spec
    "sell_order": "ratio",   # "value" = price*qty (old), "ratio" = price/base first,
                             # so premium lines are sold while their price still holds
    "wheat_hold_until": 0,   # keep wheat off the market until this day: the reference
                             # agent buys feed all game (draining the wheat pool, which
                             # lifts the price) and dumps its own wheat late
    "price_floor_frac": 0.0,  # hold a shallow-book product whose price fell below this
                              # fraction of base (deep books are always sold)
    "liquidate_day": 28,      # from this day, sell regardless of the floor
    "fert_keep": 2,
    "wheat_keep": 8,
    "feed_buy_mult": 1,      # buy this many times the herd's feed need: the
                             # wheat pool is shared and finite, so buying more
                             # than we eat drains it and lifts the price we
                             # later sell our own wheat into (M2 price operation)
    "pen_ahead": 1,
    "seed_ahead": 1,         # buy seeds this many days early (no missed plantings)
    "queue_radius": 0,       # local sweep after a job: measured WORSE (q1 63k vs
                             # 84k) and radius>=2 locks units into re-picking a job
                             # they cannot perform (idle 62%, reward 0)
    "queue_slack": 2,        # ... within this priority slack (a local sweep)
    "carry_batch": 1,        # wheat per shed trip (measured: 4 or 8 is worse --
                             # wheat parked in hands cannot be sold from the shed)
    "herd_cash_gate": 1,     # buy a scheduled animal batch once cash allows it
    "herd_reserve": 400,     # ... keeping this much back for seeds/feed
    "pen_min_dist": 2,       # 1 is legal (only the shed tiles themselves fall
                             # through to the shed-drop path) and cheaper to service
    "plant_scale": 1.0,      # multiplies every scheduled batch size
    "animal_scale": 1.0,
    "prio_place": 0,
    "prio_feed": 0,
    "prio_collect": 3,
    "prio_water_window": 3,
    "prio_harvest": 6,
    "prio_plant": 7,
    "prio_animal_product": 2,   # collect milk/wool/egg as soon as it exists
    "prio_build_idle": 8,
    "zone_penalty": 0,       # priority penalty for a job outside the unit's zone
    "zone_grid": 2,          # 2 => quadrants, 3 => 3x3 blocks
    "strip_penalty": 0,      # priority penalty for a job outside the unit's column strip
    "strip_urgent_max": 1,   # priorities at or below this ignore the strip
    "preempt_margin": 2,     # a job this much more urgent takes a unit off its work
    "place_phase_hours": 3,  # at the start of a day, this many hours are spent on
                             # placement before the field rounds begin (a morning
                             # routine, like the reference agent)
    "place_phase_units": 2,  # how many units join the placement phase
    "preempt_max_prio": 1,   # ... but only jobs at or below this priority may preempt
                             # (general preemption thrashes: units abandon jobs they
                             # have already walked to, and the move share explodes)
    "save_for_land": 1,      # hold cash for the land purchase instead of spending
    "land_goal": 1100,       # cash floor while saving
}
HIRE_SCHEDULE = {0: 4, 1: 4, 2: 6, 3: 6, 4: 6, 5: 6, 6: 8, 7: 9, 8: 9, 9: 10, 10: 11}
HIRE_DEFAULT = 11
FEED_RESERVE = 8
FERT_RESERVE = 2


def g(v, k, default=None):
    if isinstance(v, dict):
        return v.get(k, default)
    getter = getattr(v, "get", None)
    if callable(getter):
        return getter(k, default)
    return getattr(v, k, default)


def i_(v, default=0):
    try:
        return int(v)
    except (TypeError, ValueError):
        return default


class PlanV0:
    """One instance per player slot; state is keyed by player."""

    def __init__(self, verbose=False, params=None):
        self.state = {}
        self.verbose = verbose
        self.p = dict(DEFAULTS)
        self.p.update(params or {})
        self.diag = collections.Counter()

    # ---------------------------------------------------------------- entry
    def act(self, obs):
        player = i_(g(obs, "player", 0))
        step = i_(g(obs, "step", 0)) or 0
        st = self.state.get(player)
        if st is None or step == 0:
            st = {"assigned": {}, "land": 0, "seen": {}}
            self.state[player] = st
        day, hour = step // 24, step % 24
        farm = g(obs, "farms", [])[player]
        priv = g(obs, "private", {}) or {}
        tiles = g(farm, "tiles", [])
        positions = [g(farm, "farmer")] + [list(p) for p in (g(farm, "hands") or [])]

        if hour == 0:
            self._pf_day = None
        self._pick_portfolio(obs)
        market = self._market(obs, player, st, day, hour, farm, priv, tiles)

        # rebuild the open job set from the live state every step (the market
        # orders above only land after this action, so a job set built once at
        # hour 0 would miss today's seeds and animals entirely)
        jobs = self._jobs(obs, player, day, tiles, priv)
        for j in jobs:
            key = (j["kind"], j["pos"])
            j["age"] = step - st["seen"].setdefault(key, step)
        st["seen"] = {k: v for k, v in st["seen"].items()
                      if k in {(x["kind"], x["pos"]) for x in jobs}}
        live = {(j["kind"], j["pos"]): j for j in jobs}
        claimed = set()
        for ui in list(st["assigned"]):
            job = st["assigned"][ui]
            if job is None:
                continue
            key = (job["kind"], job["pos"])
            if key not in live:
                st["assigned"][ui] = None
            elif key in claimed:
                st["assigned"][ui] = None
            else:
                claimed.add(key)

        # morning placement phase: get the animals out of the shed before the field
        # rounds start.  Priority- or preemption-based placement thrashes (measured:
        # any preemption costs 20k+), so the phase is explicit instead.
        place_jobs = [j for j in jobs if j["kind"] == "PLACE"]
        early = self.p["place_phase_days"] and day < self.p["place_phase_days"]
        n_units = (self.p["place_phase_units_early"] if early
                   else self.p["place_phase_units"])
        if place_jobs and (hour < self.p["place_phase_hours"]
                           or (early and hour < 4)):
            for ui in range(min(n_units, len(positions))):
                key = (st["assigned"].get(ui) or {}).get("pos")
                cur = st["assigned"].get(ui)
                if cur is not None and cur["kind"] == "PLACE":
                    continue
                free = [j for j in place_jobs if (j["kind"], j["pos"]) not in claimed]
                if not free:
                    break
                pos = positions[ui]
                if not (isinstance(pos, (list, tuple)) and len(pos) >= 2):
                    continue
                best = min(free, key=lambda j: abs(j["pos"][0] - pos[0]) + abs(j["pos"][1] - pos[1]))
                if cur is not None:
                    claimed.discard((cur["kind"], cur["pos"]))
                st["assigned"][ui] = best
                claimed.add((best["kind"], best["pos"]))

        units = []
        for ui, pos in enumerate(positions):
            # preemption: assignments are sticky by design (a unit finishes what it
            # started), but a much more urgent job -- placement, feeding -- must be
            # able to take the unit now.  Without this the herd never got placed:
            # two PLACE jobs sat open for the whole game while every hand watered.
            if isinstance(pos, (list, tuple)) and len(pos) >= 2:
                cur = st["assigned"].get(ui)
                best = self._claim(jobs, claimed, pos, ui, len(positions))
                can_preempt = (best is not None
                               and best["prio"] <= self.p["preempt_max_prio"])
                if can_preempt and (cur is None
                                    or best["prio"] + self.p["preempt_margin"]
                                    <= cur["prio"]):
                    if cur is not None:
                        claimed.discard((cur["kind"], cur["pos"]))
                    st["assigned"][ui] = best
                    claimed.add((best["kind"], best["pos"]))
            cmd = self._unit_action(obs, player, st, day, ui, pos, tiles, priv, jobs,
                                    claimed, len(positions))
            units.append(cmd)
        return {"farmer": units[0] if units else ["PASS"],
                "hands": units[1:],
                "market": market[:10]}

    # ---------------------------------------------------------------- jobs
    def _jobs(self, obs, player, day, tiles, priv):
        """Needs-driven job list for the day, highest priority first."""
        jobs = []
        shed = g(priv, "shed", {}) or {}
        seeds_now = g(priv, "seeds", {}) or {}
        seen_planted = set()

        def add(prio, kind, pos, carry=None):
            jobs.append({"prio": prio, "kind": kind, "pos": tuple(pos), "carry": carry})

        for y, row in enumerate(tiles):
            for x, cell in enumerate(row):
                if not isinstance(cell, dict):
                    continue
                kind = g(cell, "kind")
                if kind == "PLANT":
                    cd = CROPS.get(g(cell, "crop"))
                    if not cd:
                        continue
                    age = day - i_(g(cell, "planted_day", day))
                    watered = bool(g(cell, "watered_today"))
                    risk = i_(g(cell, "consecutive_unwatered", 0)) >= 1
                    in_window = (not cd["ongoing"]
                                 and (cd["max_yield_day"] + 1) // 2 <= age <= cd["max_yield_day"]
                                 and i_(g(cell, "yield_units", 0)) < cd["max_yield"])
                    if not watered and risk:
                        add(0, "WATER", (x, y))
                    elif not watered and in_window:
                        add(self.p["prio_water_window"], "WATER", (x, y))
                    elif not watered and cd["ongoing"]:
                        add(4, "WATER", (x, y))
                    units = i_(g(cell, "yield_units", 0))
                    ripe = units > 0 and (age >= cd["first_yield_day"] if cd["ongoing"]
                                          else age >= cd["max_yield_day"] or units >= cd["max_yield"])
                    if ripe:
                        add(self.p["prio_harvest"], "HARVEST", (x, y))
                elif kind in ("PASTURE", "COOP"):
                    animal = g(cell, "animal")
                    if animal is None:
                        continue
                    if not g(cell, "fed_today"):
                        prio = 1 if i_(g(cell, "consecutive_unfed", 0)) >= 1 else 2
                        add(0, "FEED", (x, y))
                    if not g(cell, "cared_today"):
                        add(5, "CARE", (x, y))
                    if g(cell, "fertilizer_available"):
                        add(self.p["prio_collect"], "COLLECT_FERTILIZER", (x, y))
                    # HARVEST on an animal tile collects its product (milk / wool /
                    # egg).  Without this the products pile up in the tile and the
                    # herd earns nothing -- which is what killed the day-6 wool that
                    # pays for the first land purchase.
                    if i_(g(cell, "yield_units", 0)) > 0:
                        add(self.p["prio_animal_product"], "HARVEST", (x, y))
                elif kind == "WEED":
                    add(9, "DIG", (x, y))
        # free tiles: pens go NEAR the shed (animals need three visits a day),
        # crops farther out (one visit a day) -- the travel-optimal split
        free = []
        for y, row in enumerate(tiles):
            for x, cell in enumerate(row):
                if cell is None:
                    free.append((x, y))
        free.sort(key=lambda t: abs(t[0] - 4) + abs(t[1] - 4))
        # A pen must NOT sit on or beside the shed: PLACE on a shed-adjacent tile
        # falls through to the engine's "shed drop" path, so the animal goes back
        # into the shed and the placement loops forever (a sheep sat there 30 days).
        pen_min = self.p["pen_min_dist"]
        pen_free = [t for t in free if t not in SHED and min(
            abs(t[0] - sx) + abs(t[1] - sy) for sx, sy in SHED) >= pen_min]

        # --- pens: decide the STRUCTURE TYPE from the plan, not from the shed
        # (building a coop for cows is what silently killed the day-0 herd before)
        sched = tuple((a, max(0, int(round(n * self.p["animal_scale"]))))
                      for a, n in ANIMAL_SCHEDULE.get(day, ()))
        geese = int(self.p.get("early_geese", 0) or 0)
        if geese and day == 0:
            sched = sched + (("GOOSE", geese),)
        cowsheep = (sum(n for a, n in sched if a in ("COW", "SHEEP"))
                    + i_(shed.get("COW", 0)) + i_(shed.get("SHEEP", 0)))
        geese = sum(n for a, n in sched if a == "GOOSE") + i_(shed.get("GOOSE", 0))
        free_pasture = free_coop = 0
        for row in tiles:
            for cell in row:
                if isinstance(cell, dict) and g(cell, "animal") is None:
                    if g(cell, "kind") == "PASTURE":
                        free_pasture += 1
                    elif g(cell, "kind") == "COOP":
                        free_coop += 1
        want_pasture = max(0, cowsheep - free_pasture)
        want_coop = max(0, geese - free_coop)
        slot = 0
        build_prio = 1 if (i_(shed.get("COW", 0)) + i_(shed.get("SHEEP", 0))
                           + i_(shed.get("GOOSE", 0))) > 0 else self.p["prio_build_idle"]
        for _ in range(want_pasture):
            if slot < len(free):
                add(build_prio, "BUILD", free[slot], "PASTURE")
                slot += 1
        for _ in range(want_coop):
            if slot < len(free):
                add(build_prio, "BUILD", free[slot], "COOP")
                slot += 1
        crop_slots = free[slot:]

        # --- plantings: every scheduled crop not yet in the ground
        want = []
        scale = self.p["plant_scale"]
        sched = self._plant_schedule()
        for d in sorted(sched):
            if d > day:
                break
            want.extend(c for c, n in sched[d]
                        for _ in range(int(round(n * scale))))
        standing = collections.Counter()
        growing = collections.Counter()
        for row in tiles:
            for cell in row:
                if isinstance(cell, dict) and g(cell, "kind") == "PLANT":
                    standing[g(cell, "crop")] += 1
        for (r, c) in list(seen_planted):
            growing[c] += 1
        k = 0
        for crop in want:
            if i_(seeds_now.get(crop, 0)) <= 0 or k >= len(crop_slots):
                continue
            add(self.p["prio_plant"], "PLANT", crop_slots[k], crop)
            k += 1

        # --- animals waiting in the shed go onto free structures
        placed = collections.Counter()
        for y, row in enumerate(tiles):
            for x, cell in enumerate(row):
                if not (isinstance(cell, dict) and g(cell, "kind") in ("PASTURE", "COOP")):
                    continue
                if g(cell, "animal") is not None:
                    continue
                for animal in ("COW", "SHEEP", "GOOSE"):
                    if ANIMALS[animal]["structure"] == g(cell, "kind") \
                            and i_(shed.get(animal, 0)) > placed[animal]:
                        add(self.p["prio_place"], "PLACE", (x, y), animal)
                        placed[animal] += 1
                        break

        jobs.sort(key=lambda j: j["prio"])
        if self.verbose:
            print(f"  day {day}: {collections.Counter(j['kind'] for j in jobs)}")
        return jobs

    # ---------------------------------------------------------------- market
    def _market(self, obs, player, st, day, hour, farm, priv, tiles):
        if self.p["market_mode"] == "spec" and str(day) in (self.p.get("market_spec") or {}):
            return self._market_from_spec(obs, player, st, day, hour, farm, priv)
        market = []
        money = float(g(farm, "money", 0) or 0)
        shed = dict(g(priv, "shed", {}) or {})
        seeds_now = dict(g(priv, "seeds", {}) or {})
        prices = dict(g(g(obs, "market", {}) or {}, "prices", {}) or {})

        # 1) LAND FIRST: everything else (farm size) depends on it.  The tape we
        #    record must unlock quadrants on schedule or the whole plan starves.
        quads = len(g(farm, "unlocked_quadrants", []) or [])
        if quads < 3 and len(market) < 10:
            price = LAND_PRICES[min(quads - 1, len(LAND_PRICES) - 1)]
            if day >= self.p["land_first_day"] and money >= price + self.p["land_reserve"]:
                money -= price
                market.append(["BUY_LAND"])

        # 2) ANIMALS FIRST, then seeds, then crew, then feed -- this is rank-1's
        #    day-0 basket (2 cow + 3 sheep + 7 melon + 7 wheat + 4 hands + 5 feed
        #    = the whole 3000).  The sheep matter most: 5 sheep at day 0 produce
        #    ~18 wool on day 6, which is what funds the first land purchase.  Get
        #    the order wrong (seeds before animals) and there is no wool, no land,
        #    no scale -- the death spiral this planner sat in for ten days.
        batches = list(ANIMAL_SCHEDULE.get(day, ()))
        if self.p["herd_cash_gate"]:
            # any *past* batch that never got bought is still owed to the herd
            for d in sorted(ANIMAL_SCHEDULE):
                if d < day:
                    batches = list(ANIMAL_SCHEDULE[d]) + batches
            seen_kinds = {"COW": 0, "SHEEP": 0, "GOOSE": 0}
            census = collections.Counter()
            for row in tiles:
                for cell in row:
                    if isinstance(cell, dict) and g(cell, "animal"):
                        census[g(cell, "animal")] += 1
            for animal in seen_kinds:
                owed = sum(max(0, int(round(n * self.p["animal_scale"])))
                           for d in ANIMAL_SCHEDULE if d <= day
                           for a, n in ANIMAL_SCHEDULE[d] if a == animal)
                seen_kinds[animal] = max(0, owed - census[animal] - i_(shed.get(animal, 0)))
            batches = [(a, seen_kinds[a]) for a in seen_kinds if seen_kinds[a] > 0]
        for animal, n in sorted(batches, key=lambda kv: ANIMALS[kv[0]]["first_yield_day"]):
            n = max(0, int(n))
            have = i_(shed.get(animal, 0))
            need = max(0, n - have)
            cost = ANIMALS[animal]["cost"] * need
            floor = self.p["herd_reserve"] if self.p["herd_cash_gate"] else 0
            if need and len(market) < 10 and money >= cost + floor:
                money -= cost
                market.append(["BUY_ANIMAL", animal, need])

        sched = self._plant_schedule()
        want_seed = collections.Counter()
        for d in range(day, day + 1 + int(self.p["seed_ahead"])):
            for crop, n in sched.get(d, ()):
                want_seed[crop] += max(0, int(round(n * self.p["plant_scale"])))
        for crop, n in want_seed.items():
            if crop not in CROPS:
                continue
            have = i_(seeds_now.get(crop, 0))
            need = max(0, n - have)
            if need and len(market) < 10 and money >= CROPS[crop]["seed"] * need:
                money -= CROPS[crop]["seed"] * need
                market.append(["BUY_SEED", crop, need])

        workload = self._workload_estimate(tiles, day, priv)
        want = HIRE_SCHEDULE.get(day, HIRE_DEFAULT)
        # jobs plus the walking to reach them, over one day of steps (rank-1 runs
        # 11-12 hands for a ~135-job / ~120-move day)
        want = max(self.p["hire_min"], min(want, int(workload * self.p["hire_mult"] / 24) + 1,
                                           self.p["hire_cap"]))
        already = i_(g(farm, "hires_today", 0))
        fib = [1, 1, 2, 3, 5, 8, 13, 21, 34, 55, 89, 144, 233, 377, 610]
        while already < want and len(market) < 10:
            cost = fib[min(already, len(fib) - 1)]
            if money < cost:
                break
            money -= cost
            already += 1
            market.append(["HIRE"])

        # 3) feed: hold several days of it (an unfed animal escapes on day two)
        herd = sum(1 for row in tiles for c in row if isinstance(c, dict) and g(c, "animal"))
        want_feed = int((herd * self.p["feed_days"] + self.p["feed_reserve"])
                        * self.p["feed_buy_mult"])
        short = want_feed - i_(shed.get("WHEAT", 0))
        if short > 0 and len(market) < 10:
            price = max(1, prices.get("WHEAT", 25))
            afford = int(max(0.0, money - 20) / price)
            buy = min(short, afford)
            if buy > 0:
                money -= price * buy
                market.append(["BUY_PRODUCT", "WHEAT", buy])

        # 6) metered selling
        liquidate = day >= self.p["liquidate_day"]
        keep = ({} if liquidate else
                {"WHEAT": self.p["wheat_keep"], "FERTILIZER": self.p["fert_keep"]})
        frac = self.p["price_floor_frac"]
        if self.p["sell_order"] == "ratio":
            order = sorted(shed, key=lambda k: -(prices.get(k, 0) / max(1, BASE_PRICE.get(k, 1))))
        else:
            order = sorted(shed, key=lambda k: -prices.get(k, 0) * shed[k])
        rich = money >= float(self.p.get("sell_hold_cash", 0) or 0)
        for item in order:
            qty = i_(shed[item]) - keep.get(item, 0)
            if qty <= 0 or len(market) >= 10 or prices.get(item, 0) <= 1:
                continue
            if (item == "WHEAT" and not liquidate
                    and day < self.p["wheat_hold_until"]):
                continue
            # "hold only if rich": a poor farm must keep cash flowing every day, a
            # rich one can wait for a shallow book to recover (sell_hold_cash = 0
            # disables the hold entirely, i.e. always sell)
            if (frac and rich and not liquidate and item not in BALLAST
                    and prices.get(item, 0) < BASE_PRICE.get(item, 1) * frac):
                continue
            cap = qty if liquidate else min(qty, self.p["sell_batch"])
            market.append(["SELL", item, cap])
        return market

    def _market_from_spec(self, obs, player, st, day, hour, farm, priv):
        """Execute the reference tape's day plan: hires, land, seeds, animals, sells.

        The plan is day-indexed quantities, not positions, so it is executed against
        whatever farm our scheduler built; every order is filtered by what is
        actually affordable / in the shed.  Sells are spread across the day in
        metered batches (the tape's own rhythm) using the remaining-quantity budget.
        """
        spec = (self.p.get("market_spec") or {}).get(str(day), {})
        market = []
        money = float(g(farm, "money", 0) or 0)
        shed = dict(g(priv, "shed", {}) or {})
        seeds_now = dict(g(priv, "seeds", {}) or {})
        prices = dict(g(g(obs, "market", {}) or {}, "prices", {}) or {})
        budget = st.setdefault("spec_left", {})
        if hour == 0:
            budget.clear()
            budget.update({k: int(v) for k, v in (spec.get("sell") or {}).items()})
        fib = [1, 1, 2, 3, 5, 8, 13, 21, 34, 55, 89, 144, 233, 377, 610]

        already = i_(g(farm, "hires_today", 0))
        while hour < 3 and already < i_(spec.get("hire", 0)) and len(market) < 10:
            cost = fib[min(already, len(fib) - 1)]
            if money < cost:
                break
            money -= cost
            already += 1
            market.append(["HIRE"])

        for _ in range(i_(spec.get("buy_land", 0))):
            quads = len(g(farm, "unlocked_quadrants", []) or [])
            price = LAND_PRICES[min(quads - 1, len(LAND_PRICES) - 1)]
            if quads < 4 and money >= price and len(market) < 10:
                money -= price
                market.append(["BUY_LAND"])

        if hour < 4:
            for crop, n in (spec.get("buy_seed") or {}).items():
                need = max(0, int(n) - i_(seeds_now.get(crop, 0)))
                cost = CROPS.get(crop, {}).get("seed", 0) * need
                if need and money >= cost and len(market) < 10:
                    money -= cost
                    market.append(["BUY_SEED", crop, need])
            for animal, n in (spec.get("buy_animal") or {}).items():
                need = max(0, int(n) - i_(shed.get(animal, 0)))
                cost = ANIMALS[animal]["cost"] * need
                if need and money >= cost and len(market) < 10:
                    money -= cost
                    market.append(["BUY_ANIMAL", animal, need])

        keep = {"WHEAT": self.p["wheat_keep"], "FERTILIZER": self.p["fert_keep"]}
        for item, total in sorted(budget.items(), key=lambda kv: -prices.get(kv[0], 0)):
            left = int(total)
            if left <= 0:
                continue
            stock = max(0, i_(shed.get(item, 0)) - keep.get(item, 0))
            if stock <= 0 or len(market) >= 10 or prices.get(item, 0) <= 1:
                continue
            steps_left = max(1, 24 - hour)
            qty = min(stock, left, max(1, -(-left // steps_left)), self.p["spec_batch"] * 3)
            market.append(["SELL", item, qty])
            budget[item] = left - qty
        return market

    def _workload_estimate(self, tiles, day, priv):
        """Rough size of today's job list (used only to size the crew)."""
        n = 0
        for row in tiles:
            for cell in row:
                if not isinstance(cell, dict):
                    continue
                if g(cell, "kind") == "PLANT":
                    n += 1
                elif g(cell, "animal"):
                    n += 3
                elif g(cell, "kind") in ("PASTURE", "COOP"):
                    n += 1
        for crop, cnt in PLANT_SCHEDULE.get(day, ()):
            n += cnt
        return n

    # ---------------------------------------------------------------- units
    def _pick_portfolio(self, obs):
        """Choose rank1 / premium from the world (shops + realised prices).

        The reference agent forks on the shop draw and on realised prices around
        day 6-7 rather than replaying one fixed schedule; this is the structural
        degree of freedom the 25-knob parameterisation was missing.
        """
        day = i_(g(obs, "step", 0)) // 24
        sw = int(self.p.get("pf_switch_day", 0) or 0)
        if not sw or day < sw:
            return getattr(self, "_pf_choice", "rank1")
        if getattr(self, "_pf_day", None) == day:
            return self._pf_choice
        prices = dict(g(g(obs, "market", {}) or {}, "prices", {}) or {})
        prem = [prices.get(k, 0) / max(1, BASE_PRICE.get(k, 1))
                for k in ("STRAWBERRY", "MELON", "MILK", "WOOL")]
        bulk = [prices.get(k, 0) / max(1, BASE_PRICE.get(k, 1))
                for k in ("WHEAT", "CARROT")]
        ratio = (sum(prem) / max(1, len(prem))) / max(1e-6, sum(bulk) / max(1, len(bulk)))
        shops = list(g(g(obs, "town", {}) or {}, "unlocked_shops", []) or [])
        prem_shops = sum(1 for sh in shops if sh in
                         ("SMOOTHIE_SHOP", "ICE_CREAM_SHOP", "BRUNCH_SPOT", "YARN_STORE"))
        self._pf_choice = ("premium" if (ratio >= self.p.get("pf_world_thresh", 1.0)
                                        or prem_shops >= 2) else "rank1")
        self._pf_day = day
        return self._pf_choice

    def _plant_schedule(self):
        """Planting plan: the measured rank-1 schedule, or the reference tape's own.

        The tape's market plan is tuned for the portfolio it grows, so when adopting
        its sell schedule the portfolio has to come with it (its seeds-per-day are
        the planting plan in disguise).
        """
        if getattr(self, "_pf_choice", "rank1") == "premium":
            return PREMIUM_SCHEDULE
        if self.p.get("portfolio") == "spec":
            spec = self.p.get("portfolio_spec") or {}
            out = {}
            for d, row in spec.items():
                crops = tuple((k, int(v)) for k, v in (row.get("buy_seed") or {}).items())
                if crops:
                    out[int(d)] = crops
            if out:
                return out
        return PLANT_SCHEDULE

    def _endgame(self, obs, player, st, day, pos, inv):
        """Final days: carry everything to the shed and drop it, never idle."""
        if day < self.p["liquidate_day"]:
            return None
        if not inv:
            return None
        if pos in SHED:
            return ["DROP"]
        return self._step(pos, (4, 4)) or ["PASS"]

    def _unit_action(self, obs, player, st, day, ui, pos, tiles, priv, jobs, claimed,
                     n_units=1):
        if not isinstance(pos, (list, tuple)) or len(pos) < 2:
            return ["PASS"]
        pos = (i_(pos[0]), i_(pos[1]))
        invs = g(priv, "inventories", []) or []
        inv = dict(invs[ui] or {}) if ui < len(invs) else {}
        eg = self._endgame(obs, player, st, day, pos, inv)
        if eg is not None:
            return eg
        job = st["assigned"].get(ui)
        if job is None:
            job = self._claim(jobs, claimed, pos, ui, n_units)
            st["assigned"][ui] = job
            if job is not None:
                claimed.add((job["kind"], job["pos"]))
            else:
                return ["PASS"]

        # jobs that need something in hand fetch it at the shed first
        need = {"FEED": "WHEAT", "PLACE": job.get("carry")}.get(job["kind"])
        if need and i_(inv.get(need, 0)) <= 0:
            if pos in SHED:
                n = self.p["carry_batch"] if need == "WHEAT" else 1
                return ["PICKUP", need, max(1, int(n))]
            return self._step(pos, (4, 4)) or ["PASS"]

        target = job["pos"]
        try:
            tile = tiles[target[1]][target[0]]
        except Exception:
            tile = None
        if pos == target:
            cmd = self._perform(job, tile, inv)
            st["assigned"][ui] = None
            claimable = claimed | {(job["kind"], job["pos"])}
            nxt = (self._local_next(jobs, claimable, pos, job, ui, n_units)
                   if cmd is not None else None)
            if nxt is not None:
                st["assigned"][ui] = nxt
                claimed.add((nxt["kind"], nxt["pos"]))
            return cmd if cmd is not None else ["PASS"]
        return self._step(pos, target) or ["PASS"]

    def _zone_of(self, pos):
        n = max(1, int(self.p["zone_grid"]))
        cell = 10 // n if 10 % n == 0 else 5
        return (int(pos[0] // cell), int(pos[1] // cell))

    def _home_zone(self, ui, pos):
        """Round-robin a home zone per unit so the crew spreads over the farm."""
        n = max(1, int(self.p["zone_grid"]))
        cells = [(zx, zy) for zx in range(n) for zy in range(n)]
        return cells[ui % len(cells)]

    def _strip_of(self, ui, units):
        """Column strip for this unit: the crew covers the farm in vertical bands."""
        n = max(1, int(units))
        width = max(1, -(-10 // n))
        return (ui * width) % 10, width

    def _local_next(self, jobs, claimed, pos, done, ui, units):
        """Sweep locally: after a job, take the nearest job still near this tile.

        Walking is 1.3 steps per work action against the reference agent's 0.9, so
        the win is to keep a unit in one neighbourhood instead of hopping across
        the farm after every single job.
        """
        rad = self.p["queue_radius"]
        if rad <= 0:
            return None
        best, best_d = None, None
        for job in jobs:
            if (job["kind"], job["pos"]) in claimed:
                continue
            d = abs(job["pos"][0] - pos[0]) + abs(job["pos"][1] - pos[1])
            if d > rad:
                continue
            eff = max(0, job["prio"] - job.get("age", 0) // max(1, self.p["age_div"]))
            if eff > done["prio"] + self.p["queue_slack"]:
                continue
            if best_d is None or d < best_d:
                best, best_d = job, d
        return best

    def _claim(self, jobs, claimed, pos, ui=0, units=1):
        """Best open job for this unit: priority first, then distance."""
        cands = []
        for job in jobs:
            key = (job["kind"], job["pos"])
            if key in claimed:
                continue
            eff = max(0, job["prio"] - job.get("age", 0) // max(1, self.p["age_div"]))
            d = abs(job["pos"][0] - pos[0]) + abs(job["pos"][1] - pos[1])
            pen = self.p["zone_penalty"]
            if pen and job["prio"] > 1:
                home = self._home_zone(ui, pos)
                if self._zone_of(job["pos"]) != home:
                    eff += pen
            strip = self.p["strip_penalty"]
            if strip and job["prio"] > self.p["strip_urgent_max"]:
                x0, w = self._strip_of(ui, units)
                if not (x0 <= job["pos"][0] < x0 + w):
                    eff += strip
            cands.append((eff, d, job))
        if not cands:
            return None
        top = min(c[0] for c in cands)
        pool = [c for c in cands if c[0] <= top + self.p["claim_slack"]]
        return min(pool, key=lambda c: c[1])[2]

    def _perform(self, job, tile, inv):
        kind = job["kind"]
        if kind == "WATER":
            return ["WATER"]
        if kind == "HARVEST":
            return ["HARVEST"]
        if kind == "FEED":
            return ["FEED"] if i_(inv.get("WHEAT", 0)) > 0 else None
        if kind == "CARE":
            return ["CARE"]
        if kind == "COLLECT_FERTILIZER":
            return ["COLLECT_FERTILIZER"]
        if kind == "DIG":
            return ["DIG"]
        if kind == "PLANT":
            return ["PLANT", job["carry"]]
        if kind == "PLACE":
            animal = job["carry"]
            ok = (isinstance(tile, dict)
                  and g(tile, "kind") == ANIMALS[animal]["structure"]
                  and g(tile, "animal") is None)
            if not ok or i_(inv.get(animal, 0)) <= 0:
                # NEVER emit PLACE against an invalid target: the engine then falls
                # through to its "shed drop" path and puts the animal straight back
                # in the shed, which is how a sheep spent whole games in there
                # while every hand took turns fetching it.
                return None
            return ["PLACE", animal]
        if kind == "BUILD":
            return ["BUILD_" + job["carry"]]
        return None

    def _step(self, pos, target):
        dx, dy = target[0] - pos[0], target[1] - pos[1]
        if dx == 0 and dy == 0:
            return None
        if abs(dx) >= abs(dy):
            return ["EAST"] if dx > 0 else ["WEST"]
        return ["SOUTH"] if dy > 0 else ["NORTH"]


# ------------------------------------------------------------------ selftest
def selftest(seed, opponent_path=None, verbose=False, params=None):
    from kaggle_environments import make
    planner = PlanV0(verbose=verbose, params=params)
    if opponent_path:
        ns = {"__name__": "opp"}
        exec(compile(Path(opponent_path).read_text(), opponent_path, "exec"), ns)
        opp = ns["agent"]
    else:
        opp = "starter"
    env = make("kaggriculture", configuration={"episodeSteps": 720, "seed": seed})
    def _seat0(obs, configuration=None):
        return planner.act(obs)

    env.run([_seat0, opp])
    steps = env.steps
    cov = collections.defaultdict(lambda: [0, 0, 0, 0, 0])  # plants, animals, waters, animalops, pass
    moves = collections.Counter()
    for t in range(len(steps)):
        o = steps[t][0].get("observation")
        a = steps[t][0].get("action") or {}
        if not o:
            continue
        day, hour = t // 24, t % 24
        if hour == 0:
            cov[day][0] = sum(1 for row in o["farms"][0]["tiles"] for c in row
                              if isinstance(c, dict) and c.get("kind") == "PLANT")
            cov[day][1] = sum(1 for row in o["farms"][0]["tiles"] for c in row
                              if isinstance(c, dict) and c.get("animal"))
        for cmd in [a.get("farmer") or []] + list(a.get("hands") or []):
            if not (isinstance(cmd, list) and cmd):
                continue
            v = cmd[0]
            if v in ("NORTH", "SOUTH", "EAST", "WEST"):
                moves["MOVE"] += 1
            elif v == "PASS":
                moves["PASS_T"] += 1
            else:
                moves["WORK"] += 1
            if v == "WATER":
                cov[day][2] += 1
            elif v in ("FEED", "CARE", "COLLECT_FERTILIZER"):
                cov[day][3] += 1
            elif v == "PASS":
                cov[day][4] += 1
    r = [steps[-1][i]["reward"] for i in (0, 1)]
    st = [steps[-1][i]["status"] for i in (0, 1)]
    print(f"seed {seed}: planner {r[0]:,.0f} [{st[0]}]  vs  {r[1]:,.0f} [{st[1]}]")
    print(f"{'day':>4s} {'plants':>7s} {'animals':>7s} {'waters':>7s} {'cover':>6s} "
          f"{'animal_ops':>10s} {'a_cover':>8s} {'PASS':>5s} {'MOVE':>5s} {'WORK':>5s}")
    tot = dict(moves)
    for day in range(30):
        p, an, w, ao, ps = cov[day]
        print(f"{day:4d} {p:7d} {an:7d} {w:7d} {(w / p if p else 0):6.2f} "
              f"{ao:10d} {(ao / (3 * an) if an else 0):8.2f} {ps:5d} "
              f"{tot['MOVE'] // 30:5d} {tot['WORK'] // 30:5d}")
    print(f"totals: {dict(moves)}")
    return env


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--selftest", action="store_true")
    ap.add_argument("--seed", type=int, default=900)
    ap.add_argument("--opponent", default=None)
    ap.add_argument("--verbose", action="store_true")
    ap.add_argument("--set", action="append", default=[], help="key=value parameter override")
    args = ap.parse_args()
    params = {}
    for item in args.set:
        k, _, v = item.partition("=")
        try:
            params[k] = int(v)
        except ValueError:
            try:
                params[k] = float(v)
            except ValueError:
                params[k] = v
    if args.selftest:
        selftest(args.seed, args.opponent, args.verbose, params)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
