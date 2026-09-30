#!/usr/bin/env python
"""Build enhancement variants of the v37+clamp champion.

Two independent ideas, both aimed at the mirror/execution edge that the ladder
A/B showed is worth real rating:

  FR    fill the dormant `front_run` hook. The town (`unlocked_shops`) is public
        and shared, and the family's route is a pure function of the first two
        shops -- so on a ladder saturated with copies of this family we can
        predict the opponent's tape and sell our own lots one step before theirs
        depresses the price.

  SORT  reorder SELL orders by value (price x qty) descending before the
        max_orders truncation, so the most valuable lots are sold first while
        our own supply is still (relatively) un-dumped.

Usage: python scripts/build_enhancements.py
"""
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
BASE = ROOT / "data" / "variants" / "on_clamp_sells" / "main.py"
OUT = ROOT / "data" / "enh"

FR_TAIL = '''

# ================= enhancement: predicted opponent plan for front_run =========
# The first two town shops are PUBLIC and shared by both seats, and this family's
# route is a pure lookup on them, so a same-family opponent's tape is predictable.
class _LiveOppPlan:
    __slots__ = ("routes", "table", "route")

    def __init__(self, routes, table):
        self.routes = routes
        self.table = table
        self.route = 0

    def update(self, observation):
        try:
            step = _step_of(observation)
            shops = _get(_get(observation, "town", {}), "unlocked_shops", []) or []
            if step >= FINAL_PLAN_STEP:
                self.route = 2
            elif step >= ROUTE_STEP:
                self.route = self.table.get(tuple(shops[:2]), 0)
            else:
                self.route = 0
        except Exception:
            pass

    def __len__(self):
        return LAST_ACT_STEP + 1

    def __getitem__(self, index):
        tape = self.routes.get(self.route)
        if tape is None:
            tape = next(iter(self.routes.values()))
        return tape[index] if 0 <= index < len(tape) else PASS_ACTION


_OPP = _LiveOppPlan(_ROUTES, {('BAKERY', 'YARN_STORE'): 3, ('BRUNCH_SPOT', 'YARN_STORE'): 4,
                              ('FARMERS_MARKET', 'YARN_STORE'): 5, ('ICE_CREAM_SHOP', 'YARN_STORE'): 6,
                              ('PET_CAFE', 'YARN_STORE'): 5, ('PIZZA_SHOP', 'YARN_STORE'): 7,
                              ('SMOOTHIE_SHOP', 'YARN_STORE'): 8, ('YARN_STORE', 'BAKERY'): 9,
                              ('YARN_STORE', 'BRUNCH_SPOT'): 9, ('YARN_STORE', 'FARMERS_MARKET'): 1,
                              ('YARN_STORE', 'ICE_CREAM_SHOP'): 9, ('YARN_STORE', 'PET_CAFE'): 10,
                              ('YARN_STORE', 'PIZZA_SHOP'): 6, ('YARN_STORE', 'SMOOTHIE_SHOP'): 11,
                              ('YARN_STORE', 'YARN_STORE'): 12})
_IMPL.chassis.opponent_plan = _OPP
_IMPL.chassis.cfg["front_run"] = True

_FR_BASE = agent
del agent


def agent(observation, configuration=None):
    try:
        _OPP.update(observation)
    except Exception:
        pass
    return _FR_BASE(observation, configuration)
'''

SORT_OLD = '            action["market"] = action["market"][: cfg["max_orders"]]'
SORT_NEW = '''            _mk = list(action.get("market") or [])
            _sells = sorted([o for o in _mk if o and o[0] == "SELL" and len(o) >= 3],
                            key=lambda o: -(view.prices.get(o[1], 0) * _int(o[2])))
            _it = iter(_sells)
            action["market"] = [next(_it) if (o and o[0] == "SELL" and len(o) >= 3) else o
                                for o in _mk][: cfg["max_orders"]]'''


def build(name, front_run=False, sort_sells=False):
    src = BASE.read_text()
    if sort_sells:
        assert src.count(SORT_OLD) == 1, "sort patch point not unique"
        src = src.replace(SORT_OLD, SORT_NEW)
    if front_run:
        src = src.rstrip("\n") + "\n" + FR_TAIL
    d = OUT / name
    d.mkdir(parents=True, exist_ok=True)
    (d / "main.py").write_text(src)
    print(f"  {name:<10} front_run={front_run} sort_sells={sort_sells}  "
          f"({len(src):,} bytes)")
    return d


if __name__ == "__main__":
    OUT.mkdir(parents=True, exist_ok=True)
    build("fr", front_run=True)
    build("sort", sort_sells=True)
    build("fr_sort", front_run=True, sort_sells=True)
