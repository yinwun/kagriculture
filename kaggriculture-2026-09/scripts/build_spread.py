#!/usr/bin/env python
"""Build `sell_spread` variants of the champion (data/tapeopt/rgcs/main.py).

Why this mechanism
------------------
The market price is a *pure function of `market.inventory`* (kaggriculture.py:
`market_price(item, inventory)`), and the town shops consume inventory on the
steps where `step % 4 == 0` (`_town_consume`).  A lot sold as one block therefore
walks down its own price curve, while the same lot split over several turns is
partly sold at prices the shop drain has restored.  The frontier notebook that
beats our champion by +4.4% (58-2 over 60 paired games) differs from it in almost
nothing except the number of SELL orders, which it issues 37.7% more often
(427 vs 310 per game), i.e. it spreads its sells.

The layer below caps each step's SELL quantity per item at a multiple of the
town's own per-step drain rate, carrying the remainder forward in a queue with a
deadline.  It is off by default (`sell_spread = 0`) and every variant here is a
copy; the champion file is never modified.

Usage:  python scripts/build_spread.py          # writes data/spread/<name>/main.py
"""
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
CHAMPION = ROOT / "data" / "tapeopt" / "rgcs" / "main.py"

SHOPS_BLOCK = '''
# Town shops and the drain interval, taken from the engine
# (kaggle_environments/envs/kaggriculture/kaggriculture.py): a shop instance of a
# single-product shop consumes 2 units, any other 1 unit, every `SHOP_INTERVAL`
# steps.  This is the only "free" demand in the game, so it is the rate at which a
# spread-out sale can be absorbed without moving the price.
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
SHOP_INTERVAL = 4

'''

LAYER = '''
    # ---- layer: sell_spread ---------------------------------------------------
    @staticmethod
    def _shop_drain(view, item):
        """Units of ``item`` the town consumes per step (its demand for the item).

        Shops drain on the steps where ``step % 4 == 0``; a shop selling exactly
        one product consumes 2 units, every other shop 1 unit.  This is demand we
        do not have to share with the rival, so it is the quantity that can be
        sold each step without depressing the price.
        """
        n = 0
        for shop in view.town:
            prods = SHOPS.get(shop)
            if prods and item in prods:
                n += 2 if len(prods) == 1 else 1
        return n / float(SHOP_INTERVAL)

    def _sell_spread(self, action, view, projected, step, st):
        """Spread each step's SELL lots over several steps instead of one block.

        The price is a pure function of the market inventory the town only ever
        consumes, so selling a lot in one step walks down its own price curve.  This
        layer caps a step's SELL of an item at a multiple of the town's per-step
        demand for it and carries the rest in a queue.

        The queue has a deadline (`sell_spread_h`), is flushed when the farm is poor
        (`sell_spread_cash`), when the shed is too full to keep harvesting into
        (`sell_spread_shed`), and from `sell_spread_stop_day` on, so delayed lots can
        never be stranded at the end of the game.  `sell_spread_min_frac` keeps a
        floor on how much of a lot is always sold, which bounds the deferral even
        when the town's demand for that item is zero.
        """
        cfg = self.cfg
        sp = cfg.get("sell_spread")
        if sp is None or float(sp) < 0:
            return                      # layer absent: the champion's default
        k = float(sp)                   # 0 = no town-demand term, >0 = demand-scaled
        pend = st.setdefault("spread_pending", {})
        market = action.get("market") or []
        day = step // cfg["turns_per_day"]
        liquidate = day >= int(cfg.get("sell_spread_stop_day", 28) or 28)
        shed_total = sum(max(0, _int(v)) for v in projected.values())
        shed_full = shed_total >= int(cfg.get("sell_spread_shed", 90) or 90)
        poor = view.money < float(cfg.get("sell_spread_cash", 0) or 0)
        floor_units = float(cfg.get("sell_spread_floor", 0) or 0)
        min_frac = float(cfg.get("sell_spread_min_frac", 0.34) or 0)
        horizon = int(cfg.get("sell_spread_h", 12) or 0)
        no_defer = liquidate or shed_full or poor
        avail = {i: max(0, _int(v)) for i, v in projected.items()}
        kept = []
        for o in market:
            if not (o and o[0] == "SELL" and len(o) >= 3):
                kept.append(o)
                continue
            item = o[1]
            drain = self._shop_drain(view, item) * k
            slot = pend.get(item) or {}
            queued = max(0, _int(slot.get("qty", 0)))
            due = slot.get("due")
            order = max(0, _int(o[2]))
            want = min(order + queued, avail.get(item, 0))
            allow = want
            if not no_defer and want > 0:
                # Sell at least `min_frac` of the lot, and at least the town's own
                # demand for the item (scaled by k), but never more than the lot.
                # An absolute floor is deliberately absent: a fixed unit floor is
                # item-blind and, with wheat lots of ~90, silently becomes the only
                # binding term (measured: k=1, k=3, k=8 and min_frac=0.5 then produce
                # byte-identical games).
                allow = max(min_frac * order, min(float(order), drain * k))
                if floor_units > 0:
                    allow = max(allow, min(float(order), floor_units))
                if due is not None and step >= due:
                    allow = want          # the deadline: flush the queue
            take = int(max(0, min(want, allow)))
            left = want - take
            if left > 0:
                pend[item] = {"qty": left,
                              "due": due if due is not None else step + horizon}
            else:
                pend[item] = {"qty": 0, "due": None}
            avail[item] = max(0, avail.get(item, 0) - take)
            kept.append(["SELL", item, take])
        action["market"] = kept

'''

ANCHOR_CLAMP = "    # ---- layer: clamp_sells ---------------------------------------------------"
ANCHOR_VIEW = '        self.quadrants = len(list(_get(self.farm, "unlocked_quadrants", []) or []))'
VIEW_PATCH = ANCHOR_VIEW + '\n        self.town = list(_get(_get(observation, "town", {}) or {}, "unlocked_shops", []) or [])'

ANCHOR_SETTINGS = "'front_run': False}"


def build(settings, name, out_root):
    src = CHAMPION.read_text()
    if "sell_spread" in src:
        raise SystemExit("the champion file already contains a sell_spread layer")
    assert src.count(ANCHOR_CLAMP) == 1, "clamp_sells anchor not unique"
    assert src.count(ANCHOR_SETTINGS) == 1, "settings anchor not unique"
    # the SHOPS table needs a home: after the constants block, before the helpers
    marker = "\n# --------------------------------------------------------------------------- helpers"
    assert src.count(marker) == 1, "helpers marker not unique"
    assert src.count(ANCHOR_VIEW) == 1, "_View anchor not unique"
    out = src.replace(marker, SHOPS_BLOCK + marker, 1)
    out = out.replace(ANCHOR_VIEW, VIEW_PATCH, 1)
    out = out.replace(ANCHOR_CLAMP, LAYER + ANCHOR_CLAMP, 1)
    extra = "".join(f", '{k}': {v!r}" for k, v in sorted(settings.items()))
    out = out.replace(ANCHOR_SETTINGS, "'front_run': False" + extra + "}", 1)
    # release the queue on the way out of the market chain, then re-bound by stock
    call = ("            if cfg.get('sell_spread', -1) >= 0:\n"
            "                self._sell_spread(action, view, projected, step, st)\n"
            "                self._clamp_sells(action, projected)\n")
    anchor_call = "            action[\"market\"] = action[\"market\"][: cfg[\"max_orders\"]]"
    assert out.count(anchor_call) == 1, "market truncation anchor not unique"
    out = out.replace(anchor_call, call + anchor_call, 1)
    d = out_root / name
    d.mkdir(parents=True, exist_ok=True)
    (d / "main.py").write_text(out)
    compile(out, str(d / "main.py"), "exec")
    return d / "main.py"


# `sell_spread` = multiplier on the town's per-step demand for the item
VARIANTS = {
    "f50h12":   {"sell_spread": 0, "sell_spread_min_frac": 0.5, "sell_spread_h": 12},
    "f70h12":   {"sell_spread": 0, "sell_spread_min_frac": 0.7, "sell_spread_h": 12},
    "f85h12":   {"sell_spread": 0, "sell_spread_min_frac": 0.85, "sell_spread_h": 12},
    "f50h4":    {"sell_spread": 0, "sell_spread_min_frac": 0.5, "sell_spread_h": 4},
    "f70h4":    {"sell_spread": 0, "sell_spread_min_frac": 0.7, "sell_spread_h": 4},
    "f70h24":   {"sell_spread": 0, "sell_spread_min_frac": 0.7, "sell_spread_h": 24},
    "f70k1":    {"sell_spread": 1, "sell_spread_min_frac": 0.7, "sell_spread_h": 12},
    "f70cash3k": {"sell_spread": 1, "sell_spread_min_frac": 0.7, "sell_spread_h": 12,
                  "sell_spread_cash": 3000},
    "f70shed70": {"sell_spread": 1, "sell_spread_min_frac": 0.7, "sell_spread_h": 12,
                  "sell_spread_shed": 70},
}


def main():
    roots = ROOT / "data" / "spread"
    made = []
    for name, settings in VARIANTS.items():
        made.append(build(settings, name, roots))
    print(f"built {len(made)} variants under data/spread/")
    for m in made:
        print("  ", m.parent.name)
    (roots / "variants.json").write_text(json.dumps(VARIANTS, indent=1))


if __name__ == "__main__":
    sys.exit(main())
