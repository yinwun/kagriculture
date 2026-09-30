#!/usr/bin/env python
"""Build `race_layout` variants of the champion (data/tapeopt/rgcs/main.py).

What the layer does
-------------------
The engine clears the two players' market lists in a per-slot / per-unit lockstep
(`_process_market`), and the i-th order of player 0 is cleared against the i-th
order of player 1 with BOTH quoted the same pre-commit price.  A unit's price is
therefore decided by how many units of that item were already sold in the turn by
either player, so the only lever a player has is the slot layout of its own lots.
This builder appends a layer that runs LAST in the chassis' market chain (right
before the `action["market"][: max_orders]` truncation) and re-picks the slots of
the current step's SELL lots to maximise the simulated
`revenue_me - revenue_opp` against a predicted rival list.

Rival prediction (we cannot observe the simultaneous rival action, and the
observation exposes no rival orders):
  clone (default) -- our own pre-layer list for this step.  In a duel against a
                     build of the same lineage the rival runs the same layers on
                     nearly the same prices, so this is the closest available
                     proxy; it is also what the public single-mechanism notebook
                     uses ("independent item schedules" against its own list).
  tape            -- the raw tape action for this step (`Chassis._route_action`),
                     i.e. what a rival that replays the same frozen tape sells.
  none            -- the empty list.  A control: no item is contested, so the
                     layer provably cannot change anything.
  min             -- take the layout that maximises the minimum margin over the
                     clone and tape hypotheses (worst-case over the two).
Only public information is used: market inventory (for prices), our own shed
(projected), and the tape.

The champion file is never modified; every variant is a copy under data/race/.

Usage:
  python scripts/build_race.py                 # build every variant in VARIANTS
  python scripts/build_race.py --name control  # build one
"""
from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
CHAMPION = ROOT / "data" / "tapeopt" / "rgcs" / "main.py"
SCRIPTS = Path(__file__).resolve().parent

PREFIX = "_race_"

SHOPS_BLOCK = '''
# Town shop table, from the engine (kaggriculture.py): a single-product shop consumes
# 2 units of its product every 4 steps, every other shop 1 unit of each product it
# sells, and the town centre 1 unit of every non-fertilizer product every 24 steps.
SHOPS = {
    "BAKERY":         ["EGG", "WHEAT"],
    "PIZZA_SHOP":     ["MILK", "TOMATO", "WHEAT"],
    "BRUNCH_SPOT":    ["EGG", "WHEAT", "STRAWBERRY"],
    "YARN_STORE":     ["WOOL"],
    "ICE_CREAM_SHOP": ["STRAWBERRY", "MILK", "WHEAT"],
    "PET_CAFE":       ["CARROT"],
    "SMOOTHIE_SHOP":  ["STRAWBERRY", "MILK"],
    "FARMERS_MARKET": ["WHEAT", "CARROT", "TOMATO", "STRAWBERRY"],
}

'''

# module-level names of scripts/lockstep.py and scripts/race_layer.py that must be
# prefixed before injection so they cannot collide with the champion's own globals
RENAME = """
PRODUCTS CROPS ANIMALS MARKET_I0 PRICE_FLOOR HINGE_GAIN MARKET_PARAMS
BUYABLE_PRODUCTS _shape market_price parse_order _fib clear sell_schedule
clear_item total_revenue
MAX_SLOTS GREEDY_LIMIT split_orders schedule rival_slots_from_plan
implied_quantities _diff_item _assemble step_margin choose_layout
math
""".split()

# names the injected helpers use; provided by lockstep.py, renamed with the prefix
ALIASES = {"_race_split_orders": "_race_split_orders", "_race_market_price": "_race_market_price"}

SHARED = '''


def _race_hyp_front(orders, n_slots=MAX_SLOTS):
    """Adversarial placement: the rival packs all its SELL lots into the first slots.

    A rival that offers its lots before ours takes the high end of every price walk,
    and this is the worst slot placement we can be paired against without knowing
    anything else about it.  (An inner optimisation that maximises our regret would
    be stronger, but it costs a second search per candidate; see the report.)
    """
    sells = [list(o) for o in (orders or [])[:n_slots]
             if isinstance(o, (list, tuple)) and len(o) >= 3 and o[0] == "SELL"
             and _int(o[2]) > 0]
    return sells


def _race_hypotheses(cfg, market, tape_market):
    """Predicted rival market list(s) for this step.

    We cannot observe the rival's simultaneous action and the observation carries
    no rival orders, so the hypotheses are:
      clone -- our own pre-layer list: in a duel against a build of the same
               lineage the rival runs the same layers on nearly the same prices;
      tape  -- the raw tape action for this step (a rival replaying the same
               frozen tape);
      none  -- the empty list (a control: nothing is contested, so no layout can
               change anything).
    `race_hyp=min` returns both and the caller then picks the layout that
    maximises the WORST-CASE margin over them.
    """
    mine = [list(o) for o in (market or [])]
    tape = [list(o) for o in (tape_market or [])]
    implied = cfg.get("_race_implied")
    names = cfg.get("race_set")
    if names:
        out = []
        for n in names:
            if n == "clone":
                out.append(mine)
            elif n == "tape":
                out.append(tape)
            elif n == "implied":
                if implied:
                    out.append(implied)
            elif n == "empty":
                out.append([])
            elif n == "front":
                out.append(_race_hyp_front(mine))
        return out or [mine]
    hyp = cfg.get("race_hyp", "clone")
    if hyp == "tape":
        return [tape]
    if hyp == "none":
        return [[]]
    if hyp == "min":
        return [mine, tape]
    if hyp == "implied":
        return [implied] if implied else [mine]
    if hyp == "min2":                      # worst case over clone and implied
        return [mine, implied] if implied else [mine]
    if hyp == "hybrid":                    # implied when fresh, else clone
        return [implied] if implied else [mine]
    if hyp == "anti":                      # deliberately pair where they sell
        return [implied if implied else mine]
    return [mine]


def _race_drain(town, step):
    """Units the town removes from each product on `step` (`_town_consume`).

    Every 4th step each unlocked shop instance consumes 1 unit of each product it
    sells (2 if it sells a single product); every 24th step the town centre
    consumes 1 unit of every non-fertilizer product.  This is the only public
    information about how the shared inventory will move without either player
    acting, and it is what makes the rival's sells recoverable from the inventory.
    """
    out = {}
    shop = (step % 4 == 0)
    centre = (step % 24 == 0)
    if shop:
        for name in (town or []):
            prods = SHOPS.get(name)
            if not prods:
                continue
            mult = 2 if len(prods) == 1 else 1
            for item in prods:
                out[item] = out.get(item, 0) + mult
    if centre:
        for item in PRODUCTS:
            if item != "FERTILIZER":
                out[item] = out.get(item, 0) + 1
    return out


def _race_my_inv_delta(market, inv, shed):
    """Our own NET contribution to each item's market inventory this step.

    Sales raise the inventory by one per unit, except at the $1 floor
    (`_commit_unit` skips the increment), and BUY_PRODUCT lowers it by one per
    executed unit.  Both must be removed from the observed inventory delta before
    the remainder can be read as the rival's sells; ignoring our own buys makes
    the inference go negative and the implied hypothesis never fires (measured).
    """
    out = {}
    for item in PRODUCTS:
        sched = _race_item_schedule(market, item)
        if not sched:
            continue
        left = min(sum(sched.values()), max(0, int((shed or {}).get(item, 0))))
        idx = int((inv or {}).get(item, 0))
        got = 0
        for _k in range(left):
            price = _race_market_price(item, idx)
            if price > 1:
                got += 1
                idx += 1
        bought = 0
        for order in (market or []):
            if (isinstance(order, (list, tuple)) and len(order) >= 3
                    and order[0] == "BUY_PRODUCT" and order[1] == item):
                bought += max(0, _int(order[2]))
        if bought:
            room = max(0, 100 - sum(max(0, _int(v)) for v in (shed or {}).values()))
            bought = min(bought, room)
        if got or bought:
            out[item] = got - bought
    return out


def _race_implied_rival(prev, inv_now, town, step, template):
    """Rival's per-item executed units at step-1 from public data only.

    inv_now = inv_prev + (our sells with price>1) + (rival sells with price>1)
              - town drain, so the rival's quantities are exactly recoverable.
    Their SLOT layout is not observable, so each recovered quantity is placed at
    the slot our own list uses for that item -- the clone template.
    """
    if not prev or prev.get("step") != step - 1:
        return None
    delta = {}
    for item in PRODUCTS:
        d = int((inv_now or {}).get(item, 0)) - int(prev["inv"].get(item, 0))
        mine = int((prev.get("my_gt1") or {}).get(item, 0))  # net: sells - buys
        drain = int(_race_drain(town, prev["step"]).get(item, 0))
        q = d - mine + drain
        if q > 0:
            delta[item] = q
    if not delta:
        return None
    slots = {}
    for item in delta:
        ss = []
        for i, order in enumerate(list(template or [])[:MAX_SLOTS]):
            if (isinstance(order, (list, tuple)) and len(order) >= 3
                    and order[0] == "SELL" and order[1] == item):
                ss.append(i)
        slots[item] = ss[0] if ss else 0
    n = max(slots.values()) + 1
    out = [[] for _ in range(n)]
    for item, s in slots.items():
        out[s] = ["SELL", item, delta[item]]
    return out


def _race_item_schedule(orders, item, n_slots=MAX_SLOTS):
    """{slot: qty} of ONE item in an order list.

    NOTE: this must not be called `_race_schedule` -- that name is taken by the
    renamed `race_layer.schedule`, and shadowing it empties every contested set
    (measured: the rebuilt control stopped reordering and no longer matched the
    incumbent).
    """
    out = {}
    for slot, it, qty in _race_split_orders(orders, n_slots)[0]:
        if item is None or it == item:
            out[slot] = out.get(slot, 0) + qty
    return out


def _race_score_of(layout, rival, inv, shed):
    return _race_step_margin(layout, rival, inv, shed, shed)


def _race_apply(market, hyps, inv, shed, cfg, diag, state, step):
    """Search the layout; returns the new market list or None when unchanged."""
    try:
        only = cfg.get("race_items")
        if only:
            only = set(only)
        slots = int(cfg.get("race_slots", cfg.get("max_orders", 10)) or 10)
        objective = cfg.get("race_objective", "diff")
        if cfg.get("race_hyp") == "anti" and objective == "diff":
            objective = "anti"
        min_gain = float(cfg.get("race_min_gain", 0.5) or 0.0)
        rival_shed = None if cfg.get("race_rival_shed") == "none" else shed
        diag["race_tried"] = diag.get("race_tried", 0) + 1
        cands = [market]
        for h in hyps:
            new, _gain = _race_choose_layout(market, h, inv, shed, rival_shed,
                                             max_slots=slots, objective=objective,
                                             min_gain=min_gain, only_items=only,
                                             exact_limit=cfg.get("race_exact"))
            if new is not market and new != market and new not in cands:
                cands.append(new)
                diag["race_considered"] = diag.get("race_considered", 0) + 1
        if cfg.get("race_hyp") == "anti" and cfg.get("race_force_anti"):
            # Sign probe: the search under objective "anti" maximises -D, and the final
            # selection below would immediately re-score it with the TRUE margin and
            # reject it (measured: considered 124, reorders 0).  Accept it outright.
            for cand in cands[1:]:
                diag["race_reorders"] = diag.get("race_reorders", 0) + 1
                diag["race_forced_anti"] = diag.get("race_forced_anti", 0) + 1
                state.setdefault("emitted", {})[step] = [list(o) for o in cand]
                return cand
            return None
        rule = cfg.get("race_rule", "min")
        # margin matrix over candidates x hypotheses (one evaluation per pair; the
        # per-item replica makes each evaluation cheap, but the product is what the
        # runtime report in the report is about)
        margin = [[_race_score_of(cand, h, inv, shed) for h in hyps] for cand in cands]
        n_h = len(hyps)
        best_by_h = [max(margin[i][j] for i in range(len(cands))) for j in range(n_h)]

        def score_of(i):
            row = margin[i]
            if rule == "avg":                     # soft / average (Laplace) rule
                return sum(row) / n_h
            if rule == "regret":                  # minimise the worst-case regret
                return -max(best_by_h[j] - row[j] for j in range(n_h))
            return min(row)                       # maximin over the set

        base_score = score_of(0)
        best, best_score = market, base_score
        for i in range(1, len(cands)):
            sc = score_of(i)
            if sc > best_score + 1e-9:
                best, best_score = cands[i], sc
        diag["race_eval"] = diag.get("race_eval", 0) + len(cands) * n_h
        if best is market or best == market:
            return None
        diag["race_reorders"] = diag.get("race_reorders", 0) + 1
        diag["race_gain"] = float(diag.get("race_gain", 0.0)) + (best_score - base_score)
        state.setdefault("emitted", {})[step] = [list(o) for o in best]
        return best
    except Exception:
        diag["race_errors"] = diag.get("race_errors", 0) + 1
        return None


'''

ANCHOR_HELPERS = "\n# --------------------------------------------------------------------------- helpers"
ANCHOR_VIEW = '        self.quadrants = len(list(_get(self.farm, "unlocked_quadrants", []) or []))'
ANCHOR_LAYER = "    # ---- layer: clamp_sells ---------------------------------------------------"
ANCHOR_TRUNC = '            action["market"] = action["market"][: cfg["max_orders"]]'
ANCHOR_SETTINGS = "'front_run': False}"

# NOTE: `_View` already has a *method* named `inv(idx)` (and an alias `inventory`),
# so the market inventory must not be stored under that name.
VIEW_PATCH = ANCHOR_VIEW + (
    '\n        self.market_inv = {k: _int(v) for k, v in dict(_get(market, "inventory", {}) or {}).items()}'
    '\n        self.town = list(_get(_get(observation, "town", {}) or {}, "unlocked_shops", []) or [])'
)

LAYER = '''
    # ---- layer: race_layout (inside the chassis, immediately before the
    # `action["market"][: max_orders]` truncation: last in the chassis' market chain)
    def _race_layout(self, action, view, projected, route, step, st):
        """Reorder this step's SELL lots in the market list.

        The engine clears slot *i* of both players against each other, unit by unit,
        at a shared pre-commit price, so a lot's slot decides which of the rival's
        units it is interleaved with and how much of the price walk it takes at the
        high end.  Every quantity is kept exactly as the layers before us left it --
        only the slot assignment moves.
        """
        cfg = self.cfg
        if not cfg.get("race_layout") or cfg.get("race_hook", "chassis") not in ("chassis", "both"):
            return
        market = action.get("market") or []
        shed = {k: max(0, _int(v)) for k, v in (projected or {}).items()}
        # The observation bookkeeping must run on EVERY step, not only on the steps
        # the search runs: the rival's sells are recovered from the inventory delta
        # between consecutive OBSERVED steps, so a step that is skipped (no sell to
        # reorder) would leave the state stale and the implied hypothesis would never
        # fire (measured: race_implied stayed 0 for whole games).
        race_st = st.setdefault("race", {})
        try:
            cfg["_race_implied"] = _race_implied_rival(race_st.get("prev"),
                                                       view.market_inv, view.town,
                                                       step, market)
            if cfg["_race_implied"]:
                self.diagnostics["race_implied"] = self.diagnostics.get("race_implied", 0) + 1
            race_st["prev"] = {"step": step, "inv": dict(view.market_inv),
                               "my_gt1": _race_my_inv_delta(market, view.market_inv, shed)}
        except Exception:
            cfg["_race_implied"] = None
            race_st["prev"] = None
        if sum(1 for o in market if isinstance(o, list) and o and o[0] == "SELL") \
                < int(cfg.get("race_min_sells", 1) or 1):
            return
        if step < int(cfg.get("race_start", 0) or 0):
            return
        hyps = _race_hypotheses(cfg, market, self._route_action(route, step).get("market"))
        new = _race_apply(market, hyps, view.market_inv, shed, cfg, self.diagnostics,
                          race_st, step)
        if new is not None:
            action["market"] = new

'''

OUTER = '''
# ===========================================================================
# race_layout hook (outermost): the ~120 wrapper agents above the chassis may
# insert, drop or re-sort market orders AFTER the chassis' own layers ran
# (`_r37_reorder_sales` re-sorts contiguous SELL blocks, `_r51_close_warehouse`
# adds sales, `_r127`/`_r128` prepend BUY_PRODUCT orders).  Measured: with the
# in-chassis hook only 4 of 12 emitted layouts reached the engine unchanged.  This
# second hook runs after every wrapper, so the layout it picks is the layout the
# engine sees.  `race_hook` selects which one is active.
# ===========================================================================
_RACE_PARENT = agent
_RACE_STATES = {}


def _race_outer(observation, configuration=None):
    result = _RACE_PARENT(observation, configuration)
    try:
        cfg = _IMPL.chassis.cfg
        if not cfg.get("race_layout") or cfg.get("race_hook", "chassis") not in ("outer", "both"):
            return result
        step = _int(_get(observation, "step", 0))
        player = _int(_get(observation, "player", 0))
        st = _RACE_STATES.get(player)
        if st is None or step <= st.get("step", -1):
            st = _RACE_STATES[player] = {"step": -1, "race": {}}
        st["step"] = step
        market = list(result.get("market") or [])
        # Observation bookkeeping runs on EVERY step: the rival's sells are recovered
        # from the inventory delta between consecutive observed steps, so skipping the
        # steps the search does not run would leave `prev` stale and the implied
        # hypothesis would silently fall back to clone for the whole game
        # (measured: race_implied stayed 0 with the bookkeeping behind the gates).
        race_st = st.setdefault("race", {})
        try:
            shed0 = {k: max(0, _int(v)) for k, v in
                     (_IMPL.chassis._projected_shed(result,
                                                    _View(observation, player, cfg)) or {}).items()}
            cfg["_race_implied"] = _race_implied_rival(
                race_st.get("prev"), _View(observation, player, cfg).market_inv,
                _View(observation, player, cfg).town, step, market)
            if cfg["_race_implied"]:
                _IMPL.chassis.diagnostics["race_implied"] = \
                    _IMPL.chassis.diagnostics.get("race_implied", 0) + 1
            race_st["prev"] = {"step": step,
                               "inv": dict(_View(observation, player, cfg).market_inv),
                               "my_gt1": _race_my_inv_delta(
                                   market, _View(observation, player, cfg).market_inv, shed0)}
        except Exception:
            cfg["_race_implied"] = None
            race_st["prev"] = None
        if step < int(cfg.get("race_start", 0) or 0):
            return result
        if sum(1 for o in market if isinstance(o, list) and o and o[0] == "SELL") \
                < int(cfg.get("race_min_sells", 1) or 1):
            return result
        view = _View(observation, player, cfg)
        shed = {k: max(0, _int(v)) for k, v in
                (_IMPL.chassis._projected_shed(result, view) or {}).items()}
        route = _IMPL.chassis.players.get(player, {}).get("route")
        tape_market = None
        if route in _IMPL.chassis.routes:
            tape = _IMPL.chassis._route_action(route, step)
            tape_market = tape.get("market")
        hyps = _race_hypotheses(cfg, market, tape_market)
        new = _race_apply(market, hyps, view.market_inv, shed, cfg,
                          _IMPL.chassis.diagnostics, st["race"], step)
        if new is not None:
            return dict(result, market=new)
    except Exception:
        _IMPL.chassis.diagnostics["race_errors"] = \
            _IMPL.chassis.diagnostics.get("race_errors", 0) + 1
    return result


agent = _race_outer
agent.telemetry = getattr(_RACE_PARENT, "telemetry", {})

'''

CALL = ("            if cfg.get('race_layout', 0):\n"
        "                self._race_layout(action, view, projected, route, step, st)\n")


def _strip_docstring(src):
    m = re.match(r'\s*("""|\'\'\')(?:.|\n)*?\1\n', src)
    return src[m.end():] if m else src


def _rename(src, prefix=PREFIX):
    for name in sorted(RENAME, key=len, reverse=True):
        src = re.sub(r"(?<![\w.])" + re.escape(name) + r"(?![\w])", prefix + name, src)
    return src


def _module_code(path, keep_imports=False):
    src = Path(path).read_text()
    src = re.sub(r"# RACE-IMPORT-BEGIN.*?# RACE-IMPORT-END\n", "", src, flags=re.S)
    src = _strip_docstring(src)
    if not keep_imports:
        src = re.sub(r"^import .*$", "", src, flags=re.M)
        src = re.sub(r"^from .*$", "", src, flags=re.M)
    return _rename(src)


def outer_block(prefix=""):
    """The outermost race hook (see OUTER), optionally with its three module-level
    globals renamed.

    `prefix` exists because a FOREIGN base can already use these names: the
    `the-metav4-farm-submission-v13` composite defines its own `_RACE_PARENT`
    (its internal agent chain calls it), so appending our `_RACE_PARENT = agent`
    silently rebound that name and the composite's chain called our outermost
    wrapper -> RecursionError every step -> the harness fell back to PASS, the
    episode still reported DONE and the wallet stayed at the 3,000 start.
    """
    if not prefix:
        return OUTER
    out = OUTER
    for n in ("_RACE_PARENT", "_RACE_STATES", "_race_outer"):
        out = re.sub(r"\b%s\b" % re.escape(n), prefix + n, out)
    return out


def build(settings, name, out_root=ROOT / "data" / "race", base_path=None, outer_prefix=""):
    """Build a race_layout variant of the champion, or of an arbitrary `base_path`
    build of the same lineage (the anchors below must exist there)."""
    base_path = Path(base_path) if base_path else CHAMPION
    src = base_path.read_text()
    stacked = base_path != CHAMPION
    for anchor, label in ((ANCHOR_LAYER, "clamp_sells"), (ANCHOR_TRUNC, "market truncation"),
                          (ANCHOR_HELPERS, "helpers")):
        assert src.count(anchor) == 1, f"{label} anchor not unique"
    if not stacked:
        assert src.count(ANCHOR_VIEW) == 1, "_View anchor not unique"
        assert src.count(ANCHOR_SETTINGS) == 1, "settings anchor not unique"
    assert "_race_layout" not in src, "the base file already has a race layer"
    assert "_race_outer" not in src, "the base file already has the outer race hook"

    block = ("\n\n# ===========================================================================\n"
             "# race_layout: exact replicas of the engine's market price and per-slot /\n"
             "# per-unit clearing (scripts/lockstep.py) plus the sell-layout search\n"
             "# (scripts/race_layer.py).  Generated by scripts/build_race.py; the\n"
             "# champion file is not modified.\n"
             "# ===========================================================================\n"
             "import math as _race_math\n\n"
             + _module_code(SCRIPTS / "lockstep.py")
             + "\n\n" + _module_code(SCRIPTS / "race_layer.py")
             + _rename(SHARED) + "\n")

    out = src.replace(ANCHOR_HELPERS, SHOPS_BLOCK + block + ANCHOR_HELPERS, 1)
    if "self.market_inv" not in out:
        assert out.count(ANCHOR_VIEW) == 1, "_View anchor not unique"
        out = out.replace(ANCHOR_VIEW, VIEW_PATCH, 1)
    out = out.replace(ANCHOR_LAYER, LAYER + ANCHOR_LAYER, 1)
    out = out.replace(ANCHOR_TRUNC, CALL + ANCHOR_TRUNC, 1)
    if stacked or out.count(ANCHOR_SETTINGS) == 0:
        out = out.rstrip("\n") + ("\n\n# stacked race settings (scripts/build_race.py)\n"
                                  "_IMPL.chassis.cfg.update(%r)\n" % (settings,))
    else:
        extra = "".join(f", {k!r}: {v!r}" for k, v in sorted(settings.items()))
        out = out.replace(ANCHOR_SETTINGS, "'front_run': False" + extra + "}", 1)
    out = out.rstrip("\n") + "\n\n" + outer_block(outer_prefix)
    compile(out, "race_main.py", "exec")

    d = Path(out_root) / name
    d.mkdir(parents=True, exist_ok=True)
    target = d / "main.py"
    target.write_text(out)
    digest = hashlib.sha256(out.encode()).hexdigest()[:12]
    print(f"built {target} ({len(out):,} bytes, sha256 {digest}) settings={settings}")
    return target


# `race_layout` 0 keeps the layer inert (control); 1 enables the search.
VARIANTS = {
    # control: must be behaviour-identical to the champion (delta exactly 0)
    "control":      {"race_layout": 0},
    # the mechanism as briefed, best rival proxy
    "clone":        {"race_layout": 1, "race_hyp": "clone"},
    # other rival hypotheses
    "tape":         {"race_layout": 1, "race_hyp": "tape"},
    "minhyp":       {"race_layout": 1, "race_hyp": "min"},
    "nonehyp":      {"race_layout": 1, "race_hyp": "none"},
    # variants of the search itself
    "premium":      {"race_layout": 1, "race_hyp": "clone",
                     "race_items": ["MILK", "WOOL", "STRAWBERRY", "MELON"]},
    "mineobj":      {"race_layout": 1, "race_hyp": "clone", "race_objective": "mine"},
    "late":         {"race_layout": 1, "race_hyp": "clone", "race_start": 288},
    "greedy0":      {"race_layout": 1, "race_hyp": "clone", "race_min_gain": 0.0},
    "sells2":       {"race_layout": 1, "race_hyp": "clone", "race_min_sells": 2},
    "sells3":       {"race_layout": 1, "race_hyp": "clone", "race_min_sells": 3},
    "rivalfree":    {"race_layout": 1, "race_hyp": "clone", "race_rival_shed": "none"},
    "early":        {"race_layout": 1, "race_hyp": "clone", "race_start": 96},
    # same mechanism, but hooked AFTER the ~120 wrapper agents so the layout the
    # engine sees is the one the search chose
    "outer":        {"race_layout": 1, "race_hyp": "clone", "race_hook": "outer"},
    "outer_prem":   {"race_layout": 1, "race_hyp": "clone", "race_hook": "outer",
                     "race_items": ["MILK", "WOOL", "STRAWBERRY", "MELON"]},
    "outer_tape":   {"race_layout": 1, "race_hyp": "tape", "race_hook": "outer"},
    "outer_s3":     {"race_layout": 1, "race_hyp": "clone", "race_hook": "outer",
                     "race_min_sells": 2},
    # item-subset sweep around the best hook
    "outer_wm":     {"race_layout": 1, "race_hyp": "clone", "race_hook": "outer",
                     "race_items": ["WOOL", "MILK"]},
    "outer_wms":    {"race_layout": 1, "race_hyp": "clone", "race_hook": "outer",
                     "race_items": ["WOOL", "MILK", "STRAWBERRY"]},
    "outer_prem5":  {"race_layout": 1, "race_hyp": "clone", "race_hook": "outer",
                     "race_items": ["WOOL", "MILK", "STRAWBERRY", "MELON", "EGG"]},
    "outer_prem_g0": {"race_layout": 1, "race_hyp": "clone", "race_hook": "outer",
                      "race_items": ["WOOL", "MILK", "STRAWBERRY", "MELON"],
                      "race_min_gain": 0.0},
    "outer_prem_rs": {"race_layout": 1, "race_hyp": "clone", "race_hook": "outer",
                      "race_items": ["WOOL", "MILK", "STRAWBERRY", "MELON"],
                      "race_rival_shed": "none"},
    "prem_wm":      {"race_layout": 1, "race_hyp": "clone", "race_items": ["WOOL", "MILK"]},
    # both hooks: the in-chassis pass, then the outermost pass that repairs what
    # the ~120 wrapper agents did to the layout
    "both_prem":    {"race_layout": 1, "race_hyp": "clone", "race_hook": "both",
                     "race_items": ["WOOL", "MILK", "STRAWBERRY", "MELON"]},
    "both_prem_min": {"race_layout": 1, "race_hyp": "min", "race_hook": "both",
                      "race_items": ["WOOL", "MILK", "STRAWBERRY", "MELON"]},
}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--name", default=None)
    ap.add_argument("--out-root", default=None)
    ap.add_argument("--set", action="append", default=[])
    args = ap.parse_args()
    root = Path(args.out_root) if args.out_root else ROOT / "data" / "race"
    if args.name:
        settings = dict(VARIANTS.get(args.name, {}))
        for item in args.set:
            k, _, v = item.partition("=")
            try:
                settings[k] = int(v)
            except ValueError:
                if v in ("True", "False"):
                    settings[k] = v == "True"
                elif v.startswith("["):
                    settings[k] = json.loads(v)
                else:
                    settings[k] = v
        return 0 if build(settings, args.name, root) else 0
    made = [build(s, n, root) for n, s in VARIANTS.items()]
    (root / "variants.json").write_text(json.dumps(VARIANTS, indent=1))
    print(f"built {len(made)} variants under {root}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
