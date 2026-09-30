#!/usr/bin/env python
"""Sell-FORWARD variants of the champion (data/tapeopt/rgcs/main.py).

What the measurement says
-------------------------
On the same executed unit counts the public frontier out-earns us purely on price
(seed 9009: 1,582 vs 1,580 units, revenue 114,926 vs 108,664; WOOL 236 units at a
mean realised price of 113.4 vs 243 units at 95.4).  Its shed never accumulates (we
reach 22 wool in the shed and sell in bursts at tape-scheduled steps), and the wool
price is a pure function of the market inventory, which only the town drain
(`step % 4 == 0` shop consumption) pushes back up.  Selling in bursts therefore
walks down our own price curve and buys the rest back at the collapse; selling the
stock as it appears keeps the inventory at the drain rate and keeps the price near
its peak.  This layer sells the whole projected shed of the chosen items every step
instead of waiting for the tape's scheduled lot.

It runs last in the chassis' market chain (after `clamp_sells`, immediately before
the `action["market"][: max_orders]` truncation), so the quantities it adds are the
tape's plan plus the rest of the real stock.  It never asks for more than the
projected shed, so the engine never has to reject it; if the market list is already
full it merges into an existing SELL of the same item instead of adding an order.

Every lever is OFF by default (`forward_items = None`), so `control` is
behaviour-identical to the champion.  The champion file is never modified.

Usage: python scripts/build_forward.py            # writes data/forward/<name>/main.py
"""
from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
CHAMPION = ROOT / "data" / "tapeopt" / "rgcs" / "main.py"

# shops/interval table from the engine (kaggle_environments .../kaggriculture.py):
# a single-product shop consumes 2 units, any other shop 1 unit, every 4 steps.
SHOPS_BLOCK = '''
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

ANCHOR_TRUNC = '            action["market"] = action["market"][: cfg["max_orders"]]'
ANCHOR_SETTINGS = "'front_run': False}"

LAYER = '''
    # ---- layer: forward_sells -------------------------------------------------
    def _forward_sells(self, action, view, projected, step):
        """Sell the whole projected shed of the chosen items, every step.

        The tape releases its lots at fixed steps, so the shed accumulates between
        those steps and the lot then walks down its own price curve; the town drain
        is the only force that pushes the price back up.  Selling the stock as soon
        as it exists keeps the inventory at the drain rate instead of oscillating
        around it.  Quantities are bounded by the projected shed, so the engine
        never rejects these orders.
        """
        cfg = self.cfg
        items = cfg.get("forward_items")
        if not items:
            return
        if step < int(cfg.get("forward_start", 0) or 0):
            return
        if step > int(cfg.get("forward_stop", 718) or 718):
            return
        min_price = float(cfg.get("forward_min_price", 2) or 0)
        drawn = cfg.get("forward_drawdown")
        drain_keyed = bool(cfg.get("forward_drain"))
        if drain_keyed:
            shops = view.town
            mult = float(cfg.get("forward_drain_mult", 1.0) or 1.0)
        market = action.get("market") or []
        planned = {}
        for o in market:
            if isinstance(o, list) and len(o) >= 3 and o[0] == "SELL":
                planned[o[1]] = planned.get(o[1], 0) + max(0, _int(o[2]))
        for item in items:
            have = max(0, _int((projected or {}).get(item, 0)))
            cap = drawn
            if drain_keyed:
                # the town's own per-step demand for this item: a shop consumes 1
                # unit of each product it sells every 4 steps (2 if it sells a
                # single product), and the town centre 1 unit every 24 steps
                rate = 1.0 / 24.0
                for shop in shops:
                    prods = SHOPS.get(shop)
                    if prods and item in prods:
                        rate += (2 if len(prods) == 1 else 1) / 4.0
                cap = max(1, int(round(rate * mult)))
            if cap:
                # only sell the part of the stock the town can absorb this step
                have = min(have, int(cap))
            want = have - planned.get(item, 0)
            if want <= 0:
                continue
            if int(view.prices.get(item, 0)) < min_price:
                continue
            for o in market:
                if isinstance(o, list) and len(o) >= 3 and o[0] == "SELL" and o[1] == item:
                    o[2] = max(0, _int(o[2])) + want
                    want = 0
                    break
            if want <= 0:
                continue
            if len(market) >= cfg["max_orders"]:
                continue
            market.append(["SELL", item, want])
            self.diagnostics["forward_orders"] = self.diagnostics.get("forward_orders", 0) + 1
            self.diagnostics["forward_units"] = self.diagnostics.get("forward_units", 0) + want
        action["market"] = market

'''

VARIANTS = {
    "control":     {"forward_items": None},
    "wool":        {"forward_items": ["WOOL"]},
    "wool_milk":   {"forward_items": ["WOOL", "MILK"]},
    "premium":     {"forward_items": ["WOOL", "MILK", "STRAWBERRY", "MELON"]},
    "all":         {"forward_items": ["WHEAT", "CARROT", "TOMATO", "STRAWBERRY", "MELON",
                                      "EGG", "MILK", "WOOL", "FERTILIZER"]},
    "wool_d10":    {"forward_items": ["WOOL"], "forward_start": 240},
    "wool_d20":    {"forward_items": ["WOOL"], "forward_start": 480},
    "wool_g5":     {"forward_items": ["WOOL"], "forward_min_price": 5},
    "wool_draw1":  {"forward_items": ["WOOL"], "forward_drawdown": 1},
    "wool_draw2":  {"forward_items": ["WOOL"], "forward_drawdown": 2},
    "prem_draw2":  {"forward_items": ["WOOL", "MILK", "STRAWBERRY", "MELON"],
                    "forward_drawdown": 2},
    "wool_drain1": {"forward_items": ["WOOL"], "forward_drain": True},
    "wool_drain2": {"forward_items": ["WOOL"], "forward_drain": True, "forward_drain_mult": 2},
    "prem_drain1": {"forward_items": ["WOOL", "MILK", "STRAWBERRY", "MELON"],
                    "forward_drain": True},
}


def out_count(src, marker):
    return src.count(marker)


def build(settings, name, out_root=None, base_path=None):
    """Build a forward variant.  `base_path` stacks the layer on another built file
    (e.g. data/race/outer_prem/main.py) whose `_SETTINGS` anchor is already consumed;
    in that case the settings are applied by updating the chassis cfg at import."""
    base_path = Path(base_path) if base_path else CHAMPION
    src = base_path.read_text()
    assert src.count(ANCHOR_TRUNC) == 1, "market truncation anchor not unique"
    stacked = base_path != CHAMPION
    assert "_forward_sells" not in src, "base file already has a forward layer"
    if not stacked:
        assert src.count(ANCHOR_SETTINGS) == 1, "settings anchor not unique"
    marker = "\n# --------------------------------------------------------------------------- helpers"
    assert out_count(src, marker) == 1, "helpers marker not unique"
    out = src.replace(marker, SHOPS_BLOCK + marker, 1)
    # _View needs the town list (the champion's _View does not expose it)
    view_anchor = '        self.quadrants = len(list(_get(self.farm, "unlocked_quadrants", []) or []))'
    assert src.count(view_anchor) == 1, "_View anchor not unique"
    if "self.town = list(" not in src:
        out = out.replace(view_anchor, view_anchor +
                          '\n        self.town = list(_get(_get(observation, "town", {}) or {},'
                          ' "unlocked_shops", []) or [])', 1)
    out = out.replace(ANCHOR_TRUNC, LAYER_CALL + ANCHOR_TRUNC, 1)
    out = out.replace("    # ---- layer: clamp_sells ---------------------------------------------------",
                      LAYER + "    # ---- layer: clamp_sells ---------------------------------------------------", 1)
    extra = "".join(f", {k!r}: {v!r}" for k, v in sorted(settings.items()))
    if stacked:
        out = out.rstrip("\n") + ("\n\n# stacked forward settings (scripts/build_forward.py)\n"
                                   "_IMPL.chassis.cfg.update(%r)\n" % (settings,))
    else:
        out = out.replace(ANCHOR_SETTINGS, "'front_run': False" + extra + "}", 1)
    if settings.get("forward_drain") or settings.get("forward_items"):
        assert "self.town = list(" in out, "the _View town patch is missing"
    compile(out, "forward_main.py", "exec")
    root = Path(out_root) if out_root else ROOT / "data" / "forward"
    d = root / name
    d.mkdir(parents=True, exist_ok=True)
    (d / "main.py").write_text(out)
    print(f"built {d / 'main.py'} ({len(out):,} bytes, "
          f"sha256 {hashlib.sha256(out.encode()).hexdigest()[:12]}) settings={settings}")
    return d / "main.py"


LAYER_CALL = ("            if cfg.get('forward_items'):\n"
              "                self._forward_sells(action, view, projected, step)\n")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--name", default=None)
    ap.add_argument("--out-root", default=None)
    ap.add_argument("--set", action="append", default=[])
    ap.add_argument("--base", default=None, help="stack on this built file instead of the champion")
    args = ap.parse_args()
    if args.name:
        settings = dict(VARIANTS.get(args.name, {}))
        for item in args.set:
            k, _, v = item.partition("=")
            try:
                settings[k] = int(v)
            except ValueError:
                settings[k] = json.loads(v) if v.startswith("[") else v
        build(settings, args.name, args.out_root, base_path=args.base)
        return 0
    for name, settings in VARIANTS.items():
        build(settings, name, args.out_root)
    (ROOT / "data" / "forward" / "variants.json").write_text(json.dumps(VARIANTS, indent=1))
    print(f"built {len(VARIANTS)} variants under data/forward/")
    return 0


if __name__ == "__main__":
    sys.exit(main())
