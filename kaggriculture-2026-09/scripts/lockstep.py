#!/usr/bin/env python
"""Standalone replica of the kaggriculture market clearing (kaggle-environments 1.32.7).

Why this file exists
--------------------
`_process_market` in
`kaggle_environments/envs/kaggriculture/kaggriculture.py` clears both players'
market orders in a *per-slot / per-unit lockstep*:

    for i in range(max(len(q0), len(q1))):        # slot i of player 0 vs slot i of player 1
        parse both orders at slot i
        while True:                               # one unit at a time
            quote both players at the CURRENT market inventory
            player 0 commits, then player 1
            if neither committed: break

Two consequences drive everything below:

1. A slot is cleared to exhaustion before the next slot is even parsed, so the
   *slot index* of an order decides when in the whole turn it is executed.
2. Both players are quoted the same pre-commit price for a paired unit, and a
   SELL adds 1 to the market inventory per committed unit (unless the price is
   already the $1 floor).  Therefore the price handed to the k-th unit of an
   item sold in a turn is a pure function of k -- the *global* order position of
   that unit, summed over both players.  Whoever sells their units earliest in
   that global order sells them dearest.

`market_price` is a pure function of `market["inventory"]` (no reversion), so a
turn's clearing for item X depends only on the slot-indexed quantities of X on
both sides.  Items do not interact at all (a BUY_PRODUCT of WHEAT is the only
thing that touches another item's inventory, and it is itself a WHEAT order).

This module is used for two things:
  * `clear()`      -- exact replica of the whole engine clearing, for tests;
  * `clear_item()` -- the per-item fast path the live market layer uses.

Every asymmetry of the engine is replicated on purpose:
  * orders past `max_orders` are dropped (`q[:max_orders]`);
  * SELL needs `shed[item] > 0`, BUY_PRODUCT only accepts WHEAT/FERTILIZER,
    an unknown item aborts that order, `n <= 0` or a short order is not an order
    at all;
  * a failed commit kills the order (`order_states[p] = None`);
  * player 0 commits before player 1 inside one unit iteration.

Known approximation: `clear_item()` assumes the shed never runs out mid-turn
beyond what the caller passes as `stock`, and it ignores money (irrelevant for
SELL).  `clear()` is exact for the common case; cash limits, shed capacity and
BUY_* are replicated but only ever validated by the tests in
`scripts/test_lockstep.py`.
"""
from __future__ import annotations

import math

PRODUCTS = ("WHEAT", "CARROT", "TOMATO", "STRAWBERRY", "MELON", "EGG", "MILK", "WOOL", "FERTILIZER")

# Verbatim from the engine's CROPS / ANIMALS tables (seed costs and animal costs
# are fixed prices, they do not move with the market).
CROPS = {
    "WHEAT": {"seed": 10},
    "CARROT": {"seed": 20},
    "TOMATO": {"seed": 50},
    "STRAWBERRY": {"seed": 100},
    "MELON": {"seed": 80},
}
ANIMALS = {"GOOSE": {"cost": 300}, "COW": {"cost": 400}, "SHEEP": {"cost": 500}}

MARKET_I0 = 10000
PRICE_FLOOR = 1
HINGE_GAIN = 8.0

# Verbatim copy of `MARKET_PARAMS`.  The observation never carries `market.params`
# (only `inventory` and `prices`), and no local run has ever set `marketParams`,
# so these defaults are what the engine uses.
MARKET_PARAMS = {
    "WHEAT":      {"base":  25, "I0": MARKET_I0, "T": 400, "below_func": "sqrt",   "below_target": 0.80, "above_func": "log",    "above_target": 0.20},
    "CARROT":     {"base":  35, "I0": MARKET_I0, "T": 450, "below_func": "hinge",  "below_target": 1.00, "above_func": "sqrt",   "above_target": 0.70},
    "TOMATO":     {"base":  60, "I0": MARKET_I0, "T": 200, "below_func": "hinge",  "below_target": 0.40, "above_func": "sqrt",   "above_target": 0.60},
    "STRAWBERRY": {"base": 120, "I0": MARKET_I0, "T": 100, "below_func": "sqrt",   "below_target": 0.70, "above_func": "linear", "above_target": 1.60},
    "MELON":      {"base": 250, "I0": MARKET_I0, "T": 300, "below_func": "log",    "below_target": 0.20, "above_func": "sq",     "above_target": 3.60},
    "EGG":        {"base":  50, "I0": MARKET_I0, "T": 332, "below_func": "hinge",  "below_target": 0.40, "above_func": "log",    "above_target": 0.20},
    "MILK":       {"base": 160, "I0": MARKET_I0, "T": 122, "below_func": "sqrt",   "below_target": 0.60, "above_func": "linear", "above_target": 1.60},
    "WOOL":       {"base": 200, "I0": MARKET_I0, "T": 105, "below_func": "log",    "below_target": 0.20, "above_func": "sq",     "above_target": 3.20},
    "FERTILIZER": {"base": 100, "I0": MARKET_I0, "T": 200, "below_func": "linear", "below_target": 0.40, "above_func": "linear", "above_target": 0.40},
}

BUYABLE_PRODUCTS = ("WHEAT", "FERTILIZER")


def _shape(func, x, T=None):
    x = max(0.0, x)
    if func == "linear":
        return x
    if func == "sq":
        return x * x
    if func == "sqrt":
        return math.sqrt(x)
    if func == "log":
        return math.log(1.0 + x)
    if func == "log10":
        return math.log10(1.0 + x)
    if func == "hinge":
        if not T or T <= 0:
            return x
        u = x / T
        return u + HINGE_GAIN * max(0.0, u - 1.0) ** 2
    return x


def market_price(item, inventory, params=None):
    """Engine `market_price`: pure function of the market inventory, floored at $1."""
    p = (params or MARKET_PARAMS)[item]
    base = p["base"]
    i0 = p["I0"]
    T = p["T"]
    if inventory < i0:
        f = p["below_func"]
        amp = p["below_target"] * base / _shape(f, T, T)
        price = base + amp * _shape(f, i0 - inventory, T)
    else:
        f = p["above_func"]
        amp = p["above_target"] * base / _shape(f, T, T)
        price = base - amp * _shape(f, inventory - i0, T)
    return max(PRICE_FLOOR, int(round(price)))


def parse_order(order):
    """Engine `_parse_order`: None when the engine would ignore the order."""
    if not isinstance(order, (list, tuple)) or not order:
        return None
    op = order[0]
    if op == "HIRE":
        return {"type": "HIRE"}
    if op == "BUY_LAND":
        return {"type": "BUY_LAND"}
    if op in ("BUY_SEED", "BUY_PRODUCT", "BUY_ANIMAL", "SELL"):
        if len(order) < 3:
            return None
        try:
            n = int(order[2])
        except (TypeError, ValueError):
            return None
        if n <= 0:
            return None
        return {"type": op, "item": order[1], "remaining": n}
    return None


def _fib(n):
    a, b = 1, 1
    for _ in range(n):
        a, b = b, a + b
    return a


def clear(orders_p0, orders_p1, inventory, sheds, params=None, max_orders=10,
          shed_capacity=100, money=(0.0, 0.0), hires_today=(0, 0), quadrants=(1, 1),
          guard=100000):
    """Replay one turn of the engine's market for two players.

    orders_pN : the raw `action["market"]` list of player N (order matters)
    inventory : {item: units} at the start of the turn
    sheds     : ({item: units}, {item: units}) shed contents at the start
    money     : starting cash, only needed when BUY_* orders are present
    hires_today / quadrants : only needed for HIRE / BUY_LAND

    Returns a dict:
        rev      : [revenue_p0, revenue_p1]  (money delta from SELL minus BUY_*)
        money    : final cash per player
        inv      : final market inventory
        shed     : final shed contents per player
        units    : [units sold p0, units sold p1]
        slots    : number of slots the engine walks
    """
    params = params or MARKET_PARAMS
    inv = dict(inventory)
    stock = [dict(sheds[0]), dict(sheds[1])]
    cash = [float(money[0]), float(money[1])]
    hired = [int(hires_today[0]), int(hires_today[1])]
    quads = [int(quadrants[0]), int(quadrants[1])]
    sold = [0, 0]

    queues = [list(orders_p0 or [])[:max_orders], list(orders_p1 or [])[:max_orders]]
    n_slots = max(len(queues[0]), len(queues[1]))

    for i in range(n_slots):
        ostate = [None, None]
        for p in (0, 1):
            if i < len(queues[p]):
                ostate[p] = parse_order(queues[p][i])

        # Atomic orders (HIRE, BUY_LAND) resolve once, in player order, before the
        # per-unit loop of this slot.
        for p in (0, 1):
            o = ostate[p]
            if o is None:
                continue
            if o["type"] == "HIRE":
                cost = _fib(hired[p])
                if cash[p] >= cost:
                    cash[p] -= cost
                    hired[p] += 1
                ostate[p] = None
            elif o["type"] == "BUY_LAND":
                n_extra = quads[p] - 1
                if n_extra < 3:
                    cost = (1000, 2000, 4000)[n_extra]
                    if cash[p] >= cost:
                        cash[p] -= cost
                        quads[p] += 1
                ostate[p] = None

        steps = 0
        while True:
            steps += 1
            if steps >= guard:
                break
            quoted = [None, None]
            for p in (0, 1):
                o = ostate[p]
                if o is None or o["remaining"] <= 0:
                    continue
                op, item = o["type"], o["item"]
                if op == "SELL" and item in PRODUCTS:
                    quoted[p] = ("SELL", item, market_price(item, inv[item], params), o)
                elif op == "BUY_PRODUCT" and item in BUYABLE_PRODUCTS:
                    # Quoted at the post-buy inventory.
                    quoted[p] = ("BUY_PRODUCT", item, market_price(item, inv[item] - 1, params), o)
                elif op == "BUY_SEED" and item in CROPS:
                    quoted[p] = ("BUY_SEED", item, CROPS[item]["seed"], o)
                elif op == "BUY_ANIMAL" and item in ANIMALS:
                    quoted[p] = ("BUY_ANIMAL", item, ANIMALS[item]["cost"], o)
                else:
                    ostate[p] = None

            if quoted[0] is None and quoted[1] is None:
                break

            committed = False
            for p in (0, 1):
                q = quoted[p]
                if q is None:
                    continue
                op, item, price, o = q
                ok = False
                if op == "SELL":
                    if stock[p].get(item, 0) > 0:
                        stock[p][item] -= 1
                        cash[p] += price
                        sold[p] += 1
                        # Sales at the $1 floor do not add market supply.
                        if price > 1:
                            inv[item] += 1
                        ok = True
                elif op == "BUY_PRODUCT":
                    if cash[p] >= price and sum(stock[p].values()) < shed_capacity:
                        cash[p] -= price
                        stock[p][item] = stock[p].get(item, 0) + 1
                        inv[item] -= 1
                        ok = True
                elif op == "BUY_SEED":
                    if cash[p] >= price:
                        cash[p] -= price
                        ok = True
                elif op == "BUY_ANIMAL":
                    if cash[p] >= price and sum(stock[p].values()) < shed_capacity:
                        cash[p] -= price
                        stock[p][item] = stock[p].get(item, 0) + 1
                        ok = True
                if ok:
                    o["remaining"] -= 1
                    committed = True
                else:
                    ostate[p] = None
            if not committed:
                break

    rev = [cash[0] - float(money[0]), cash[1] - float(money[1])]
    return {"rev": rev, "money": cash, "inv": inv, "shed": stock, "units": sold,
            "slots": n_slots}


# --------------------------------------------------------------------------- fast path
def sell_schedule(orders, item, n_slots, op="SELL"):
    """Slot-indexed lot layout of one item: {slot: [op, item, qty]}; absent = empty.

    Only orders that the engine would accept for `item` are placed; every other
    order of the list (other items, atomic orders) is ignored here -- it cannot
    influence this item's price path.
    """
    out = {}
    for i, o in enumerate(list(orders or [])[:n_slots]):
        if not isinstance(o, (list, tuple)) or len(o) < 3 or o[0] != op or o[1] != item:
            continue
        try:
            n = int(o[2])
        except (TypeError, ValueError):
            continue
        if n > 0:
            out[i] = n
    return out


def clear_item(mine, theirs, item, inv0, stock_me, stock_opp, params=None,
               shed_capacity=100, money=(10 ** 9, 10 ** 9), guard=100000):
    """Lockstep for a single item.

    `mine` / `theirs` are {slot: qty} of SELL orders for `item` (see
    `sell_schedule`).  Returns (rev_me, rev_opp, (stock_me, stock_opp), inv_end).

    Exactness: the engine's per-slot loop for an item reads and writes only that
    item's inventory and each player's own shed, and its per-item price quote
    depends on nothing else, so a per-item replay reproduces the whole-turn
    clearing for that item bit for bit.  BUY_PRODUCT of WHEAT/FERTILIZER can be
    folded in by the caller by passing `their_buys`-style negative quantities --
    not needed for SELL-only lists, which is all the layer produces.
    """
    params = params or MARKET_PARAMS
    inv = {item: inv0}
    stock = [{item: stock_me}, {item: stock_opp}]
    cash = [float(money[0]), float(money[1])]
    rev = [0, 0]
    sched = [mine, theirs]
    n_slots = 1 + max(max(mine) if mine else -1, max(theirs) if theirs else -1)
    if n_slots <= 0:
        return 0, 0, (stock_me, stock_opp), inv0

    for i in range(n_slots):
        rem = [sched[0].get(i), sched[1].get(i)]
        steps = 0
        while True:
            steps += 1
            if steps >= guard:
                break
            quoted = [None, None]
            for p in (0, 1):
                if rem[p] is None or rem[p] <= 0:
                    continue
                quoted[p] = market_price(item, inv[item], params)
            if quoted[0] is None and quoted[1] is None:
                break
            committed = False
            for p in (0, 1):
                price = quoted[p]
                if price is None:
                    continue
                if stock[p][item] > 0:
                    stock[p][item] -= 1
                    cash[p] += price
                    rev[p] += price
                    if price > 1:
                        inv[item] += 1
                    rem[p] -= 1
                    committed = True
                else:
                    rem[p] = None
            if not committed:
                break
    return rev[0], rev[1], (stock[0][item], stock[1][item]), inv[item]


def total_revenue(orders_p0, orders_p1, inventory, sheds, **kw):
    """Convenience wrapper: `clear(...)["rev"]`."""
    return clear(orders_p0, orders_p1, inventory, sheds, **kw)["rev"]
