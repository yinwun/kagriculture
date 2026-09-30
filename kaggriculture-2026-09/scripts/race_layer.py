"""Sell-layout search for the last step of the market chain.

The engine clears both players' market lists slot by slot: slot 0 of player 0
against slot 0 of player 1, one unit at a time, quoted at the same pre-commit
price, and only then slot 1 (`_process_market`).  A unit's price is therefore
fixed by how many units of that item were already sold in the turn -- by *either*
player -- so what a player can choose is the position of each of its own lots in
that global order.

Facts this module is built on (all verified against the engine, see
`scripts/test_lockstep.py`):

* items are independent: item X's price path depends only on X's own inventory,
  and the only thing that touches another item is a BUY_PRODUCT of WHEAT or
  FERTILIZER;
* in a slot where both players sell the same item, the paired units get the SAME
  price, so they contribute exactly zero to `revenue_me - revenue_opp`; the
  differential is produced only by units that are *not* paired;
* hence, for a fixed multiset of quantities, the search is an assignment problem:
  give each of my contested items the slot that maximises its own differential.

This file is imported by the offline experiments and is spliced verbatim into the
built agent by `scripts/build_race.py` (which strips the RACE-IMPORT block).
"""
# RACE-IMPORT-BEGIN
from lockstep import MARKET_PARAMS, PRODUCTS, clear_item, sell_schedule  # noqa: F401
# RACE-IMPORT-END

MAX_SLOTS = 10
GREEDY_LIMIT = 4          # exact search while the contested set stays this small


def split_orders(orders, n_slots=MAX_SLOTS):
    """(sells, fixed); sells = [(slot, item, qty)], fixed = [(slot, raw_order)]."""
    sells, fixed = [], []
    for i, o in enumerate(list(orders or [])[:n_slots]):
        if isinstance(o, (list, tuple)) and len(o) >= 3 and o[0] == "SELL":
            try:
                q = int(o[2])
            except (TypeError, ValueError):
                q = 0
            if q > 0:
                sells.append((i, o[1], q))
                continue
        fixed.append((i, o))
    return sells, fixed


def schedule(orders, items=PRODUCTS, n_slots=MAX_SLOTS):
    """{item: {slot: qty}} over the SELL orders of a market list."""
    out = {}
    for slot, item, qty in split_orders(orders, n_slots)[0]:
        if item in items:
            d = out.setdefault(item, {})
            d[slot] = d.get(slot, 0) + qty
    return out


def rival_slots_from_plan(orders, items=PRODUCTS, n_slots=MAX_SLOTS):
    """Slots the rival is predicted to use, per item (for hypothesis construction)."""
    return {it: sorted(d) for it, d in schedule(orders, items, n_slots).items()}


def implied_quantities(prev_inv, cur_inv, my_sold, drain, items=PRODUCTS):
    """Rival's executed SELL units per item, recovered from the public inventory.

    The market inventory is public in every observation and only three things move
    it: our sells (price > $1), the rival's sells (price > $1) and the town drain
    on this step (`_town_consume`).  So
        rival_sold = (inv_after - inv_before) - my_sold + drain
    is observable, which is the only rival information the engine exposes.
    """
    out = {}
    for it in items:
        delta = int(cur_inv.get(it, 0)) - int(prev_inv.get(it, 0))
        out[it] = max(0, delta - int(my_sold.get(it, 0)) + int(drain.get(it, 0)))
    return out


def _diff_item(item, my_slot, my_qty, rival_sched, inv0, stock_me, stock_opp, params=None):
    """Simulated `revenue_me - revenue_opp` of one item under slot `my_slot`."""
    mine = {my_slot: my_qty} if my_qty > 0 else {}
    theirs = dict(rival_sched.get(item, {}))
    if not theirs:
        # the rival does not sell this item: our own revenue does not depend on the
        # slot of a lone lot, so every slot scores the same
        theirs = {}
    a, b, _st, _inv = clear_item(mine, theirs, item, inv0, stock_me, stock_opp, params)
    return a - b


def _assemble(orders, placement, max_slots=MAX_SLOTS):
    """Rebuild the market list with `placement` = {sell_index: slot}.

    Non-SELL orders keep their slot; unplaced sells fill the remaining slots in
    their original relative order; a placement past the current end pads with `[]`
    (the engine parses `[]` as no order, so padding only delays what follows).
    """
    src = list(orders or [])[:max_slots]
    sells, fixed = split_orders(src, max_slots)
    need = max(placement.values(), default=-1) + 1
    out_len = min(max_slots, max(len(src), need))
    out = [None] * out_len
    for slot, o in fixed:
        if slot < out_len:
            out[slot] = list(o) if isinstance(o, (list, tuple)) else o
    queue = [["SELL", it, q] for i, (_s, it, q) in enumerate(sells) if i not in placement]
    for i, slot in placement.items():
        if slot < out_len:
            _s, it, q = sells[i]
            out[slot] = ["SELL", it, q]
    for slot in range(out_len):
        if out[slot] is None:
            out[slot] = queue.pop(0) if queue else []
    for o in queue:
        if len(out) < max_slots:
            out.append(o)
    return out


def step_margin(my_orders, rival_orders, inv, my_shed, rival_shed=None, params=None,
                n_slots=MAX_SLOTS):
    """Exact `revenue_me - revenue_opp` of a whole step, summed over items.

    Items are independent, so the per-item lockstep can be summed; this is the
    quantity the layout search maximises (and the one the offline headroom script
    scores candidate layouts with).
    """
    rivals = schedule(rival_orders, PRODUCTS, n_slots)
    mine = schedule(my_orders, PRODUCTS, n_slots)
    total = 0.0
    for item in set(list(rivals) + list(mine)):
        avail = max(0, int((my_shed or {}).get(item, 0)))
        opp = None if rival_shed is None else max(0, int(rival_shed.get(item, 0)))
        a, b, _st, _inv = clear_item(mine.get(item, {}), rivals.get(item, {}), item,
                                     int((inv or {}).get(item, 0)), avail,
                                     10 ** 9 if opp is None else opp, params)
        total += a - b
    return total


def choose_layout(my_orders, rival_orders, inv, my_shed, rival_shed=None, params=None,
                  max_slots=MAX_SLOTS, objective="diff", min_gain=0.5, only_items=None,
                  exact_limit=None):
    """Slot layout of our own SELL lots that maximises the simulated margin.

    my_orders    : our current `action["market"]` (never mutated)
    rival_orders : predicted rival market list
    inv          : {item: market inventory} (public)
    my_shed      : {item: units actually in our shed when the market clears}
    rival_shed   : {item: units the rival can sell}; None = assume unconstrained
    objective    : "diff" -> maximise revenue_me - revenue_opp (default)
                   "mine" -> maximise revenue_me
                   "anti" -> maximise -(revenue_me - revenue_opp); a sign probe
    only_items   : restrict the search to these items (None = every contested item)

    Returns (new_orders, predicted_gain).  `new_orders is my_orders` when nothing
    is predicted to help, so a no-op step costs one simulation at most.
    """
    src = list(my_orders or [])
    sells, fixed = split_orders(src, max_slots)
    if not sells:
        return my_orders, 0.0
    rivals = schedule(rival_orders, PRODUCTS, max_slots)
    contest = [i for i, (_s, it, _q) in enumerate(sells)
               if rivals.get(it) and (only_items is None or it in only_items)]
    if not contest:
        return my_orders, 0.0          # every item we sell is unopposed: no lever

    def stock_of(shed, item):
        return max(0, int((shed or {}).get(item, 0)))

    avail_me = [min(q, stock_of(my_shed, it)) for _s, it, q in sells]
    if rival_shed is None:
        avail_opp = [10 ** 9] * len(sells)
    else:
        avail_opp = [stock_of(rival_shed, it) for _s, it, q in sells]

    def diff_of(i, slot):
        _s, item, _q = sells[i]
        if objective == "anti":
            # deliberately choose the slot the interleaving punishes: used only to
            # MEASURE which sign the mechanism rewards, never as a candidate build
            return -_diff_item(item, slot, avail_me[i], rivals, inv.get(item, 0),
                               avail_me[i], avail_opp[i], params)
        if objective == "mine":
            a, _b, _st, _inv = clear_item(
                {slot: avail_me[i]} if avail_me[i] > 0 else {},
                dict(rivals.get(item, {})), item, inv.get(item, 0),
                avail_me[i], avail_opp[i], params)
            return a
        return _diff_item(item, slot, avail_me[i], rivals, inv.get(item, 0),
                          avail_me[i], avail_opp[i], params)

    fixed_slots = {slot for slot, _o in fixed}
    allowed = [s for s in range(max_slots) if s not in fixed_slots]
    need = max(len(src), 1)
    allowed = [s for s in allowed if s < max(max_slots, need)] or list(range(max_slots))

    weight = {i: {s: diff_of(i, s) for s in allowed} for i in contest}

    def total_of(placement):
        value = 0.0
        for i, (slot, _it, _q) in enumerate(sells):
            value += diff_of(i, placement.get(i, slot))
        return value

    base = total_of({})
    items = sorted(weight, key=lambda i: -max(weight[i].values()))
    exact_limit = GREEDY_LIMIT if exact_limit is None else int(exact_limit)
    if len(items) > exact_limit:       # keep the search bounded on crowded steps
        keep = set(items[:exact_limit])
        items = items[:exact_limit]
        allowed_map = {i: sorted(allowed, key=lambda s: -weight[i][s])[:3] for i in items}
        for i in weight:
            if i not in keep:
                allowed_map[i] = []
    else:
        allowed_map = {i: allowed for i in items}

    best = {"value": None, "placement": None}

    def rec(pos, used, value, placement):
        if pos == len(items):
            if best["value"] is None or value > best["value"]:
                best["value"] = value
                best["placement"] = dict(placement)
            return
        i = items[pos]
        for s in allowed_map[i]:
            if s in used:
                continue
            used.add(s)
            placement[i] = s
            rec(pos + 1, used, value + weight[i][s], placement)
            del placement[i]
            used.remove(s)
        if not allowed_map[i] and best["value"] is None:
            rec(pos + 1, used, value, placement)

    rec(0, set(), 0.0, {})
    if best["placement"] is None:
        return my_orders, 0.0
    gain = best["value"] - base
    if gain <= min_gain:
        return my_orders, 0.0
    new_orders = _assemble(src, best["placement"], max_slots)
    if new_orders == src:
        return my_orders, 0.0
    return new_orders, gain
