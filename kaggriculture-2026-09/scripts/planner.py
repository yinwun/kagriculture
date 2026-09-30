#!/usr/bin/env python
"""From-scratch planner: a day-by-day greedy farm scheduler (no recorded tape).

Target profile, read off the rank-1 team's replays (scripts/profile_top.py):
  WATER ~1,300-1,430, FERTILIZE ~140-180, PASS < 100, hires ~290,
  cows only (milk), 3 quadrants, wheat/carrot/strawberry blocks.

Design
------
State comes from the observation every turn (positions, tiles, inventories), so
there is no position model to get wrong -- that is what killed the static tape
editors.  Each day the planner rebuilds a task list and assigns tasks to units by
nearest-neighbour; each unit then walks its own list.  Tasks, in priority order:

  harvest ripe crop / collect animal product
  fertilize a crop inside its effective window (only when the shed has fertilizer)
  water (keep-alive plus the window)
  feed / care animals          (feed needs wheat in the unit's inventory)
  plant on an empty tile       (only while the seeds last and it is not too late)
  drop carried goods at the shed

The engine facts this encodes:
  * two consecutive unwatered days turn a plant into a WEED (planting day counts
    as unwatered), so a keep-alive water is mandatory, not optional;
  * a watered day inside the window gives +2 instead of +1 when the tile is
    fertilized (``fertilized_until_day >= day``, one FERTILIZE covers 3 days);
  * two consecutive unfed days make an animal escape;
  * hands are day-laborers: the n-th hire of a day costs fib(n), so hiring is
    rationed by a marginal-cost cap.

Usage:
  python scripts/planner.py --seeds 3            # self-play metrics
  python scripts/planner.py --seeds 3 --vs V42   # vs our tape agent
"""
import argparse
import collections
import json
import math
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
MOVES = {"NORTH": (0, -1), "SOUTH": (0, 1), "EAST": (1, 0), "WEST": (-1, 0)}
SHED = [(4, 4), (5, 4), (4, 5), (5, 5)]
CROPS = {
    "WHEAT":      {"seed": 10,  "first": 2,  "max_day": 4,  "max_yield": 6, "price": 25,  "days": 5},
    "CARROT":     {"seed": 20,  "first": 2,  "max_day": 3,  "max_yield": 4, "price": 35,  "days": 4},
    "TOMATO":     {"seed": 50,  "first": 8,  "max_day": 8,  "max_yield": 4, "price": 60,  "days": 12,
                   "ongoing": True, "interval": 1},
    "STRAWBERRY": {"seed": 100, "first": 10, "max_day": 10, "max_yield": 4, "price": 120, "days": 18,
                   "ongoing": True, "interval": 2},
    "MELON":      {"seed": 80,  "first": 10, "max_day": 12, "max_yield": 6, "price": 250, "days": 13},
}
ANIMAL = {"GOOSE": {"cost": 300, "first": 4, "interval": 1, "max_held": 4, "product": "EGG",
                    "structure": "COOP", "price": 50},
          "COW":   {"cost": 400, "first": 8, "interval": 2, "max_held": 6, "product": "MILK",
                    "structure": "PASTURE", "price": 160},
          "SHEEP": {"cost": 500, "first": 6, "interval": 3, "max_held": 6, "product": "WOOL",
                    "structure": "PASTURE", "price": 200}}
SHOP_ITEMS = {
    "BAKERY": ["EGG", "WHEAT"], "PIZZA_SHOP": ["MILK", "TOMATO", "WHEAT"],
    "BRUNCH_SPOT": ["EGG", "WHEAT", "STRAWBERRY"], "YARN_STORE": ["WOOL"],
    "ICE_CREAM_SHOP": ["STRAWBERRY", "MILK", "WHEAT"], "PET_CAFE": ["CARROT"],
    "SMOOTHIE_SHOP": ["STRAWBERRY", "MILK"],
    "FARMERS_MARKET": ["WHEAT", "CARROT", "TOMATO", "STRAWBERRY"],
}
PRODUCTS = ["WHEAT", "CARROT", "TOMATO", "STRAWBERRY", "MELON",
            "EGG", "MILK", "WOOL", "FERTILIZER"]
FIB = [1, 1]
while len(FIB) < 30:
    FIB.append(FIB[-1] + FIB[-2])


def fib(n):
    return FIB[n] if n < len(FIB) else FIB[-1]


def quad_of(x, y):
    return ("N" if y < 5 else "S") + ("W" if x < 5 else "E")


class Planner:
    """Stateless-per-day greedy planner; state is re-derived from the observation."""

    def __init__(self, cfg=None):
        self.cfg = cfg or {}
        self.max_hands = self.cfg.get("max_hands", 11)
        self.hire_cap = self.cfg.get("hire_cap", 55)      # do not pay more than this
        self.work_per_hand = self.cfg.get("work_per_hand", 14)
        self.plant_until_hour = self.cfg.get("plant_until_hour", 14)
        self.fert_from_shed = self.cfg.get("fert_from_shed", True)
        # best-measured configuration (self-play 6,066 / 7,336 vs V42): staple
        # crops plus strawberries, and NO animals -- every animal configuration
        # tried so far starves the crop economy and then starves the animals
        # (see REPORT-top5-and-planner.md section 13)
        self.quota = self.cfg.get("quota", {"WHEAT": 25, "CARROT": 12, "STRAWBERRY": 20,
                                            "TOMATO": 0, "MELON": 0})
        self.max_animals = self.cfg.get("max_animals", 0)
        self.rich_crop_cash = self.cfg.get("rich_crop_cash", 1500)
        self.animal_price = self.cfg.get("animal_price", 400)
        self.reserve_bias = self.cfg.get("reserve_bias", 1.0)
        self.tasks = {}           # unit index -> list of task dicts
        self.hires_today = 0
        self.day_for_hires = -1
        self.planned_units = -1
        self.plan_hour = -99
        self.plan_size = 0
        self.claimed = set()
        self.last_day = -1
        self.plan = collections.Counter()

    # ---------------------------------------------------------------- helpers
    def _tiles(self, obs, p):
        return obs["farms"][p]["tiles"]

    def _pos(self, obs, p):
        f = obs["farms"][p]
        return [tuple(f.get("farmer") or (4, 4))] + [tuple(h) for h in (f.get("hands") or [])]

    def _inv(self, obs, k):
        invs = (obs.get("private") or {}).get("inventories") or [{}]
        return invs[k] if k < len(invs) else {}

    @staticmethod
    def _dist(a, b):
        return abs(a[0] - b[0]) + abs(a[1] - b[1])

    def _step_to(self, pos, tgt):
        dx, dy = tgt[0] - pos[0], tgt[1] - pos[1]
        if dx:
            return ["EAST" if dx > 0 else "WEST"]
        if dy:
            return ["SOUTH" if dy > 0 else "NORTH"]
        return None

    # ------------------------------------------------------------- planning
    def desired_crops(self, obs):
        """Crop mix from the shops the town actually has (drain-aware)."""
        shops = (obs.get("town") or {}).get("unlocked_shops") or []
        drain = collections.Counter()
        for s in shops:
            items = SHOP_ITEMS.get(s) or []
            mult = 2 if len(items) == 1 else 1
            for it in items:
                drain[it] += mult * 6
        out = {}
        for crop, info in CROPS.items():
            if drain.get(crop, 0) <= 0:
                continue
            per_tile_day = info["price"] * (info["max_yield"] * 0.6) / info["days"]
            out[crop] = per_tile_day * min(1.0, drain[crop] / 30.0)
        return out

    def build_tasks(self, obs, p, day, hour):
        farm = obs["farms"][p]
        tiles = self._tiles(obs, p)
        shed = ((obs.get("private") or {}).get("shed") or {})
        tasks = collections.defaultdict(list)
        fert_left = [shed.get("FERTILIZER", 0)]
        for y in range(len(tiles)):
            for x in range(len(tiles[y])):
                t = tiles[y][x]
                if not isinstance(t, dict) or t.get("kind") != "PLANT":
                    continue
                crop = t.get("crop")
                info = CROPS.get(crop)
                if not info:
                    continue
                age = day - t.get("planted_day", day)
                pos = (x, y)
                if (t.get("yield_units") or 0) > 0 and age >= info["first"]:
                    # do NOT harvest the moment it is legal: the yield window runs
                    # to max_day, so waiting doubles or triples the units taken
                    # (measured: harvest-at-first-day gave 1.3 units/crop, the
                    # tape's harvest-at-window-end gives 3.7-6)
                    u = t.get("yield_units") or 0
                    if info.get("ongoing"):
                        ready = u >= 2 or age >= info["max_day"]
                    else:
                        ready = age >= info["max_day"] or u >= info["max_yield"]
                    if ready:
                        tasks["HARVEST"].append({"pos": pos})
                        continue
                if (t.get("fertilized_until_day", -1) or -1) < day and fert_left[0] > 0:
                    ws = (info["max_day"] + 1) // 2
                    if info.get("ongoing") or ws <= age <= info["max_day"]:
                        tasks["FERTILIZE"].append({"pos": pos, "put": 1})
                        fert_left[0] -= 1
                if not t.get("watered_today"):
                    ws = (info["max_day"] + 1) // 2
                    if (t.get("consecutive_unwatered") or 0) >= 1 or \
                            (not info.get("ongoing") and ws <= age <= info["max_day"]):
                        tasks["WATER"].append({"pos": pos})
        for y in range(len(tiles)):
            for x in range(len(tiles[y])):
                t = tiles[y][x]
                if not isinstance(t, dict) or "animal" not in t:
                    continue
                a = ANIMAL.get(t.get("animal"))
                if not a:
                    continue
                pos = (x, y)
                if (t.get("yield_units") or 0) > 0:
                    tasks["HARVEST"].append({"pos": pos})
                if not t.get("fed_today"):
                    tasks["FEED"].append({"pos": pos})
                if not t.get("cared_today"):
                    tasks["CARE"].append({"pos": pos})
                if t.get("fertilizer_available") and shed.get("FERTILIZER", 0) < 20:
                    tasks["COLLECT_FERTILIZER"].append({"pos": pos})
        # animals bought into the shed need a structure, and BUILD_* is a UNIT
        # action (not a market order): queue both the build and the placement
        waiting = [a for a in ANIMAL if (shed.get(a, 0) or 0) > 0]
        free = {"COOP": [], "PASTURE": []}
        empties = []
        for y in range(len(tiles)):
            for x in range(len(tiles[y])):
                t = tiles[y][x]
                if isinstance(t, dict) and t.get("kind") in ("COOP", "PASTURE") \
                        and "animal" not in t:
                    free[t["kind"]].append((x, y))
                elif t is None and quad_of(x, y) in (farm.get("unlocked_quadrants") or []):
                    empties.append((x, y))
        build_need = {"COOP": 0, "PASTURE": 0}
        for a in waiting:
            kind = ANIMAL[a]["structure"]
            if free[kind]:
                tasks["PLACE"].append({"pos": free[kind].pop(0), "animal": a})
            else:
                build_need[kind] += 1
        # keep two spare structures so the next animal has a home
        for kind in ("COOP", "PASTURE"):
            spare = 2 - len(free[kind]) - sum(1 for t in tasks["BUILD"]
                                              if t.get("build") == kind)
            build_need[kind] = max(0, max(build_need[kind], spare))
        for kind, n in build_need.items():
            for _ in range(min(n, len(empties))):
                if not empties:
                    break
                tasks["BUILD"].append({"pos": empties.pop(0), "build": kind})

        # planting: keep the tile quota per crop, only early enough to be useful
        if hour <= self.plant_until_hour:
            counts = collections.Counter()
            for y in range(len(tiles)):
                for x in range(len(tiles[y])):
                    t = tiles[y][x]
                    if isinstance(t, dict) and t.get("kind") == "PLANT":
                        counts[t.get("crop")] += 1
            seeds = ((obs.get("private") or {}).get("seeds") or {})
            for y in range(len(tiles)):
                for x in range(len(tiles[y])):
                    if tiles[y][x] is not None:
                        continue
                    if quad_of(x, y) not in (obs["farms"][p].get("unlocked_quadrants") or []):
                        continue
                    for crop, quota in self.quota.items():
                        if quota <= 0 or counts[crop] >= quota or seeds.get(crop, 0) <= 0:
                            continue
                        left = 30 - day - CROPS[crop]["first"]
                        if left <= 0:
                            continue
                        counts[crop] += 1
                        seeds[crop] = seeds.get(crop, 0) - 1
                        tasks["PLANT"].append({"pos": (x, y), "crop": crop})
                        break
        return tasks

    def assign(self, obs, p, day, hour):
        positions = self._pos(obs, p)
        tasks = self.build_tasks(obs, p, day, hour)
        order = ["HARVEST", "BUILD", "PLACE", "PLANT", "FERTILIZE", "WATER",
                 "FEED", "CARE", "COLLECT_FERTILIZER"]
        pool = []
        for kind in order:
            pool.extend([dict(t, kind=kind) for t in tasks.get(kind, [])])
        # greedy nearest-neighbour assignment so each unit gets a compact beat
        assign = {k: [] for k in range(len(positions))}
        # keep whatever each unit is already walking to, otherwise a re-plan
        # sends it somewhere else mid-journey and nothing ever completes
        # keep whatever each unit is already walking to.  Synthetic follow-ups
        # (PICKUP_AT / RELOAD / RELOAD_WHEAT) are not in the pool at all: dropping
        # them sent the worker back to the structure every 4 hours and the animal
        # never got placed (measured: PLACE in the pool for 20+ days, 0 animals).
        _POOL_KINDS = {"HARVEST", "BUILD", "PLACE", "PLANT", "FERTILIZE", "WATER",
                       "FEED", "CARE", "COLLECT_FERTILIZER"}
        keep = set()
        for k in assign:
            old = self.tasks.get(k) or []
            if not old:
                continue
            head = old[0]
            if head["kind"] not in _POOL_KINDS:
                assign[k].append(head)
                continue
            for i, t in enumerate(pool):
                if (t["pos"], t["kind"]) == (head["pos"], head["kind"]) and i not in keep:
                    assign[k].append(t)
                    keep.add(i)
                    break
        pool = [t for i, t in enumerate(pool) if i not in keep]
        cur = {k: (assign[k][-1]["pos"] if assign[k] else positions[k]) for k in assign}
        for task in pool:
            best, best_d = None, None
            for k in assign:
                if len(assign[k]) >= 22:
                    continue
                d = self._dist(cur[k], task["pos"])
                if best_d is None or d < best_d:
                    best, best_d = k, d
            if best is None:
                continue
            assign[best].append(task)
            cur[best] = task["pos"]
        self.tasks = assign
        self.plan = collections.Counter(t["kind"] for t in pool)
        self.plan_size = max(self.plan_size if hour else 0, len(pool))
        return assign

    # ------------------------------------------------------------ execution
    def unit_action(self, obs, p, k, day, hour):
        positions = self._pos(obs, p)
        if k >= len(positions):
            return ["PASS"]
        pos = positions[k]
        inv = self._inv(obs, k)
        tiles = self._tiles(obs, p)
        shed = ((obs.get("private") or {}).get("shed") or {})
        carried = sum(v for kk, v in inv.items() if kk in PRODUCTS)
        if carried >= 4:
            if tuple(pos) in SHED:
                return ["DROP"]
            tgt = min(SHED, key=lambda c: self._dist(pos, c))
            return self._step_to(pos, tgt) or ["PASS"]
        queue = self.tasks.get(k) or []
        if not queue:
            return ["PASS"]
        task = queue[0]
        tgt = task["pos"]
        kind = task["kind"]
        if tuple(pos) != tuple(tgt):
            step = self._step_to(pos, tgt)
            return step or ["PASS"]
        queue.pop(0)
        t = tiles[tgt[1]][tgt[0]]
        if kind == "HARVEST":
            return ["HARVEST"]
        if kind == "WATER":
            return ["WATER"]
        if kind == "FERTILIZE":
            if inv.get("FERTILIZER", 0) > 0:
                return ["FERTILIZE"]
            queue.insert(0, dict(task, kind="FERTILIZE"))
            queue.insert(0, dict(task, kind="RELOAD"))
            return ["PASS"]
        if kind == "RELOAD":
            if tuple(pos) in SHED:
                return ["PICKUP", "FERTILIZER", 8]
            tgt2 = min(SHED, key=lambda c: self._dist(pos, c))
            return self._step_to(pos, tgt2) or ["PASS"]
        if kind == "FEED":
            if inv.get("WHEAT", 0) > 0:
                return ["FEED"]
            queue.insert(0, dict(task, kind="FEED"))
            queue.insert(0, dict(task, kind="RELOAD_WHEAT"))
            return ["PASS"]
        if kind == "RELOAD_WHEAT":
            if tuple(pos) in SHED:
                return ["PICKUP", "WHEAT", 8]
            tgt2 = min(SHED, key=lambda c: self._dist(pos, c))
            return self._step_to(pos, tgt2) or ["PASS"]
        if kind == "CARE":
            return ["CARE"]
        if kind == "COLLECT_FERTILIZER":
            return ["COLLECT_FERTILIZER"]
        if kind == "PLACE":
            animal = task["animal"]
            if inv.get(animal, 0) > 0:
                return ["PLACE", animal]
            # the animal sits in the shed, and PLACE consumes from the worker's
            # own inventory: fetch it first (83 silent PLACE no-ops before this)
            queue.insert(0, dict(task))
            queue.insert(0, {"kind": "PICKUP_AT",
                             "pos": min(SHED, key=lambda c: self._dist(pos, c)),
                             "item": animal, "n": 1})
            return ["PASS"]
        if kind == "PICKUP_AT":
            if (shed.get(task["item"], 0) or 0) <= 0:
                return ["PASS"]          # nothing to fetch: do not loop forever
            if tuple(pos) in SHED:
                return ["PICKUP", task["item"], task["n"]]
            tgt2 = min(SHED, key=lambda c: self._dist(pos, c))
            return self._step_to(pos, tgt2) or ["PASS"]
        if kind == "BUILD":
            return ["BUILD_PASTURE" if task["build"] == "PASTURE" else "BUILD_COOP"]
        if kind == "PLANT":
            # ENGINE: _new_plant starts with consecutive_unwatered = 1, so a crop
            # that is not watered the same day turns into a WEED at the rollover.
            # Queue the follow-up immediately instead of waiting for a re-plan.
            queue.insert(0, {"kind": "WATER", "pos": task["pos"]})
            return ["PLANT", task["crop"]]
        return ["PASS"]

    # --------------------------------------------------------------- market
    def market(self, obs, p, day, hour):
        farm = obs["farms"][p]
        priv = obs.get("private") or {}
        shed = priv.get("shed") or {}
        orders = []
        animals_now = sum(1 for row in self._tiles(obs, p) for t in row
                          if isinstance(t, dict) and "animal" in t)
        # keep enough cash back to buy the next animal: a cow is 400 coins and
        # pays back in 4-5 days, so spending the last coin on seeds is a loss
        reserve = 0.0
        if animals_now < self.max_animals and day >= self.cfg.get("animal_day", 2):
            reserve = self.animal_price * self.reserve_bias + 60
        # sells first: they are the only thing that brings cash in, and the
        # order list is truncated to maxMarketOrdersPerTurn at the end
        keep = {"WHEAT": 8, "FERTILIZER": 30}
        prices0 = obs["market"]["prices"]
        # NEVER sell an animal: it sits in the shed only until it is placed, and
        # selling it threw away a 400-coin cow every two turns (measured: the
        # planner bought and resold 4 cows on day 2 and produced nothing at all)
        sells = [(it, q - keep.get(it, 0)) for it, q in shed.items()
                 if it not in ANIMAL and q - keep.get(it, 0) > 0]
        sells.sort(key=lambda iq: -(prices0.get(iq[0], 0) * iq[1]))
        for it, q in sells[:5]:
            orders.append(["SELL", it, q])
        # land: three extra quadrants, earliest affordable first
        money = float(farm.get("money") or 0)
        nq = len(farm.get("unlocked_quadrants") or [])
        price = [1000, 2000, 4000][max(0, nq - 1)] if nq < 4 else 10 ** 9
        if (day >= self.cfg.get("land_day", 5) and nq < 4 and day <= self.cfg.get("land_last_day", 21)
                and money - reserve >= price + self.cfg.get("land_buffer", 600)):
            orders.append(["BUY_LAND"])
        # animals: prefer what the town drains, cows first
        shops = (obs.get("town") or {}).get("unlocked_shops") or []
        drain = collections.Counter()
        for s in shops:
            items = SHOP_ITEMS.get(s) or []
            for it in items:
                drain[it] += (2 if len(items) == 1 else 1) * 6
        animals = sum(1 for row in self._tiles(obs, p) for t in row
                      if isinstance(t, dict) and "animal" in t)
        structs = sum(1 for row in self._tiles(obs, p) for t in row
                      if isinstance(t, dict) and t.get("kind") in ("COOP", "PASTURE"))
        want = "COW" if drain.get("MILK", 0) >= 12 else ("GOOSE" if drain.get("EGG", 0) >= 12 else "COW")
        free_homes = 0
        for row in self._tiles(obs, p):
            for t in row:
                if isinstance(t, dict) and t.get("kind") in ("COOP", "PASTURE") \
                        and "animal" not in t:
                    free_homes += 1
        if (animals + 1 <= self.max_animals and free_homes > 0
                and day >= self.cfg.get("animal_day", 2)
                and float(farm.get("money") or 0) > ANIMAL[want]["cost"] + 20):
            orders.append(["BUY_ANIMAL", want, 1])
        # seeds for the quota
        seeds = priv.get("seeds") or {}
        standing = collections.Counter()
        empty_tiles = 0
        for row in self._tiles(obs, p):
            for t in row:
                if t is None:
                    empty_tiles += 1
                elif isinstance(t, dict) and t.get("kind") == "PLANT":
                    standing[t.get("crop")] += 1
        for crop, quota in self.quota.items():
            if quota <= 0:
                continue
            # never stockpile: buy only what the standing target still needs and
            # what the free tiles can take (measured: a blind 10-seed batch spent
            # ~2,000 coins on day 0 and left 176 seeds idle in the pool)
            want = max(0, min(quota - standing[crop] - seeds.get(crop, 0),
                              max(0, empty_tiles - sum(seeds.values()))))
            if not want:
                continue
            batch = min(4, want)
            # the bread-and-butter crops fund everything else, so they are never
            # blocked by the animal reserve; the expensive ones must wait for a
            # genuine surplus (a strawberry seed costs 4x a wheat seed)
            rich = crop not in ("WHEAT", "CARROT")
            cash = float(farm.get("money") or 0) - (reserve if rich else 0.0)
            floor = self.rich_crop_cash if rich else 50
            if cash > CROPS[crop]["seed"] * batch + floor:
                orders.append(["BUY_SEED", crop, batch])
        # feed: keep enough wheat in the shed for tomorrow's animals
        need_feed = max(0, animals + 2 - (shed.get("WHEAT", 0) or 0))
        if need_feed and float(farm.get("money") or 0) > 400:
            orders.append(["BUY_PRODUCT", "WHEAT", min(10, need_feed)])
        # hands, rationed by the fib cost; counted locally because the
        # observation's hand list lags the hires made this turn
        if self.day_for_hires != day:
            self.day_for_hires = day
            self.hires_today = 0
        want = self.cfg.get("min_hands", 5) + int(self.plan_size / self.work_per_hand)
        want = min(self.max_hands, max(self.cfg.get("min_hands", 5), want))
        if self.hires_today < want and fib(self.hires_today) <= self.hire_cap:
            orders.append(["HIRE"])
            self.hires_today += 1
        return orders[:10]

    def act(self, observation, configuration=None):
        try:
            p = int(observation.get("player", 0))
            step = int(observation.get("step", 0))
            day, hour = divmod(step, 24)
            units = 1 + len(observation["farms"][p].get("hands") or [])
            # hands are hired through the day, so a single dawn plan would only
            # ever address the farmer: re-plan when the roster changes or every
            # few hours, which also picks up crops that just became harvestable
            if (units != self.planned_units or hour == 0
                    or hour - self.plan_hour >= self.cfg.get("replan_every", 4)):
                self.assign(observation, p, day, hour)
                self.planned_units = units
                self.plan_hour = hour
                self.last_day = day
            actions = []
            for k in range(1 + len(observation["farms"][p].get("hands") or [])):
                actions.append(self.unit_action(observation, p, k, day, hour))
            return {"farmer": actions[0], "hands": actions[1:],
                    "market": self.market(observation, p, day, hour)}
        except Exception as exc:  # noqa: BLE001
            import os, traceback
            f = os.environ.get("PLANNER_DEBUG")
            if f:
                with open(f, "a") as fh:
                    fh.write(traceback.format_exc() + "\n")
            hands = len((observation.get("farms") or [{}])[
                int(observation.get("player", 0))].get("hands") or []) \
                if observation.get("farms") else 0
            return {"farmer": ["PASS"], "hands": [["PASS"]] * hands, "market": []}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--seeds", type=int, default=3)
    ap.add_argument("--start", type=int, default=900)
    ap.add_argument("--vs", default=None, help="opponent main.py (default: self-play)")
    ap.add_argument("--out", default=None, help="write the planner agent to this dir")
    ap.add_argument("--quota", default="WHEAT60,CARROT24")
    args = ap.parse_args()
    quota = {}
    for part in args.quota.split(","):
        if not part:
            continue
        i = 0
        while i < len(part) and not part[i].isdigit():
            i += 1
        quota[part[:i]] = int(part[i:])
    cfg = {"quota": quota}
    if args.out:
        d = ROOT / args.out
        d.mkdir(parents=True, exist_ok=True)
        src = Path(__file__).read_text()
        (d / "main.py").write_text(src + "\n\nagent = Planner().act\n")
        print(f"wrote {d/'main.py'}")
        return
    from kaggle_environments import make
    import statistics
    diffs = []
    for s in range(args.seeds):
        seed = args.start + s
        env = make("kaggriculture", configuration={"episodeSteps": 720, "seed": seed})
        a = Planner(cfg).act
        b = args.vs if args.vs else Planner(cfg).act
        env.run([a, b])
        f = env.steps[-1]
        ra, rb = (f[0]["reward"] or 0), (f[1]["reward"] or 0)
        diffs.append(ra - rb)
        print(f"seed {seed}: planner {ra:,.0f} vs {rb:,.0f} -> {ra-rb:+,.0f} "
              f"[{f[0]['status']}/{f[1]['status']}]")
    if diffs:
        print(f"mean {statistics.mean(diffs):+,.0f}  wins {sum(1 for d in diffs if d>0)}"
              f"/{len(diffs)}")


if __name__ == "__main__":
    main()
