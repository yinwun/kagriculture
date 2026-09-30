#!/usr/bin/env python
"""Wrap a FOREIGN composite base with OUR outermost layers.

Why outermost: a composite like `the-metav4-farm-submission-v13` runs its own
~88-agent wrapper chain and its own market machinery (`_v44y_lockstep`,
`_cs_*` rewrites, `_v92_p_*` forecast library).  Anything applied *inside* its
chassis is mangled by the wrappers above it (measured on our own lineage: with
the in-chassis hook only 4 of 12 chosen layouts reached the engine).  So the race
layer (scripts/race_layer.py, exact lockstep clearing replica) and a forward-sell
top-up are both applied as the LAST functions in the call chain.

The composite file is never modified; `data/tapeopt/rgcs/main.py` is never touched.

Usage:
  python scripts/build_composite_layers.py --variant all
"""
from __future__ import annotations

import argparse
import hashlib
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(Path(__file__).resolve().parent))
import build_race as BR  # noqa: E402

COMPOSITE = ROOT / "data" / "cand" / "the-metav4-farm-submission-v13-extracted-main.py"
OUT_ROOT = ROOT / "data" / "composite"
SETTINGS_ANCHOR = "'front_run': False}"

# our best-measured settings on our own base (Task 3/11: outer_prem, +597/+676)
RACE_PREM = {"race_layout": 1, "race_hyp": "clone", "race_hook": "outer",
             "race_items": ["MILK", "WOOL", "STRAWBERRY", "MELON"]}
RACE_OFF = {"race_layout": 0}
# our best-measured forward setting on our own base (wool_drain1, +790/+1,099)
FWD_WOOL = {"forward_items": ["WOOL"], "forward_drain": True}
FWD_OFF = {"forward_items": None}

FWD_LIB = '''

# ===========================================================================
# forward_sells hook (outermost) -- scripts/build_composite_layers.py
# Tops up SELL lots of `forward_items` to the projected shed AFTER every internal
# wrapper ran, bounded by the town's own drain rate so the lot never walks its own
# price curve down.  Inert when `forward_items` is None.
# ===========================================================================
_FWD_PARENT = agent


def _fwd_diag(key, n=1):
    try:
        d = _IMPL.chassis.diagnostics
        d[key] = d.get(key, 0) + n
    except Exception:
        pass


def _fwd_outer(observation, configuration=None):
    result = _FWD_PARENT(observation, configuration)
    try:
        cfg = _IMPL.chassis.cfg
        items = cfg.get("forward_items")
        if not items or not isinstance(result, dict):
            return result
        step = _int(_get(observation, "step", 0))
        if step < int(cfg.get("forward_start", 0) or 0):
            return result
        if step > int(cfg.get("forward_stop", 718) or 718):
            return result
        player = _int(_get(observation, "player", 0))
        view = _View(observation, player, cfg)
        market = list(result.get("market") or [])
        try:
            projected = _IMPL.chassis._projected_shed(result, view) or {}
        except Exception:
            _fwd_diag("forward_proj_errors")
            return result
        min_price = float(cfg.get("forward_min_price", 2) or 0)
        drain_keyed = bool(cfg.get("forward_drain"))
        drawn = cfg.get("forward_drawdown")
        planned = {}
        for o in market:
            if isinstance(o, list) and len(o) >= 3 and o[0] == "SELL":
                planned[o[1]] = planned.get(o[1], 0) + max(0, _int(o[2]))
        starts = cfg.get("forward_start_by_item") or {}
        for item in items:
            if step < int(starts.get(item, 0) or 0):
                continue
            have = max(0, _int(projected.get(item, 0)))
            cap = drawn
            if drain_keyed:
                rate = 1.0 / 24.0
                for shop in view.town:
                    prods = SHOPS.get(shop)
                    if prods and item in prods:
                        rate += (2 if len(prods) == 1 else 1) / 4.0
                cap = max(1, int(round(rate * float(cfg.get("forward_drain_mult", 1.0) or 1.0))))
            if cap:
                have = min(have, int(cap))
            want = have - planned.get(item, 0)
            if want <= 0:
                continue
            if int(view.prices.get(item, 0)) < min_price:
                continue
            merged = False
            for o in market:
                if isinstance(o, list) and len(o) >= 3 and o[0] == "SELL" and o[1] == item:
                    o[2] = max(0, _int(o[2])) + want
                    merged = True
                    break
            if not merged:
                if len(market) >= cfg["max_orders"]:
                    continue
                market.append(["SELL", item, want])
            _fwd_diag("forward_orders")
            _fwd_diag("forward_units", want)
            planned[item] = planned.get(item, 0) + want
        result["market"] = market
    except Exception:
        _fwd_diag("forward_errors")
    return result


agent = _fwd_outer
'''


def _module_defs(text):
    """Module-level names DEFINED by `text` (counts, so a redefinition in the built
    file shows up as count_new > count_old)."""
    import ast
    counts = {}
    tree = ast.parse(text)
    for node in tree.body:
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            counts[node.name] = counts.get(node.name, 0) + 1
        elif isinstance(node, ast.Assign):
            for t in node.targets:
                if isinstance(t, ast.Name):
                    counts[t.id] = counts.get(t.id, 0) + 1
        elif isinstance(node, ast.AnnAssign) and isinstance(node.target, ast.Name):
            counts[node.target.id] = counts.get(node.target.id, 0) + 1
    return counts


def check_collisions(base_text, out_text, allowed=("agent",)):
    """Fail loudly if our appended code DEFINES a module-level name the base already
    defines: that is the exact shape of the `_RACE_PARENT` bug (silent rebinding of
    a foreign build's own global -> infinite recursion, wallet stuck at 3,000)."""
    old, new = _module_defs(base_text), _module_defs(out_text)
    clashes = {n: (old[n], new[n]) for n in old if new.get(n, 0) > old[n] and n not in allowed}
    assert not clashes, f"appended code redefines base globals: {clashes}"
    return clashes


def _write(out: str, name: str, out_root=OUT_ROOT, base_text=None):
    if base_text is not None:
        check_collisions(base_text, out)
    compile(out, "composite_main.py", "exec")
    d = Path(out_root) / name
    d.mkdir(parents=True, exist_ok=True)
    target = d / "main.py"
    target.write_text(out)
    print(f"built {target} ({len(out):,} bytes, "
          f"sha256 {hashlib.sha256(out.encode()).hexdigest()})")
    return target


def build_fwd(settings, name, base_path=None, out_root=OUT_ROOT):
    """Append the outermost forward block to `base_path` (default: the composite)."""
    base = Path(base_path) if base_path else COMPOSITE
    src = base.read_text()
    assert "_fwd_outer" not in src, "base already has the forward outer hook"
    if "self.market_inv" not in src:
        assert src.count(BR.ANCHOR_VIEW) == 1, "_View anchor not unique"
        src = src.replace(BR.ANCHOR_VIEW, BR.VIEW_PATCH, 1)
    assert "self.town = list(" in src, "the _View town patch is missing"
    # a race-block base already carries our shop table (build_race injects it), and
    # appending it twice would redefine `SHOPS` -- the collision guard rejects that.
    # The marker must be OUR block's comment: a loose `"SHOPS = {"` also matches the
    # composite's `_OR2_SHOPS = {`, which skipped the table and made the layer raise
    # `NameError: SHOPS` on every step (measured: forward_errors 19,410).
    add_shops = "Town shop table, from the engine" not in src
    out = src.rstrip("\n") + "\n\n" + (BR.SHOPS_BLOCK if add_shops else "") + FWD_LIB
    if base == COMPOSITE or out.count(SETTINGS_ANCHOR) == 1:
        assert out.count(SETTINGS_ANCHOR) == 1, "settings anchor not unique"
        extra = "".join(f", {k!r}: {v!r}" for k, v in sorted(settings.items()))
        out = out.replace(SETTINGS_ANCHOR, "'front_run': False" + extra + "}", 1)
    else:
        out = out.rstrip("\n") + ("\n\n# stacked forward settings "
                                  "(scripts/build_composite_layers.py)\n"
                                  "_IMPL.chassis.cfg.update(%r)\n" % (settings,))
    return _write(out, name, out_root, base_text=src)


VARIANTS = {
    # both blocks present, every knob off: must be behaviour-identical to the composite
    "comp_control": {"race": RACE_OFF, "fwd": FWD_OFF},
    "comp_race":    {"race": RACE_PREM, "fwd": None},
    "comp_fwd":     {"race": None, "fwd": FWD_WOOL},
    "comp_both":    {"race": RACE_PREM, "fwd": FWD_WOOL},
    # Task 24: late-game (day 13+, step 312) strawberry liquidation, WOOL unchanged
    "comp_straw":   {"race": RACE_PREM, "fwd": {**FWD_WOOL, "forward_items": ["WOOL", "STRAWBERRY"],
                                                "forward_start_by_item": {"STRAWBERRY": 312}}},
    # separate variant, per instruction: milk only inside the same late-game window
    "comp_straw_milk": {"race": RACE_PREM,
                        "fwd": {**FWD_WOOL, "forward_items": ["WOOL", "STRAWBERRY", "MILK"],
                                "forward_start_by_item": {"STRAWBERRY": 312, "MILK": 312}}},
    # control for the Task-24 layer edit: WOOL only, must be byte-identical to comp_both
    "comp_both_ctl": {"race": RACE_PREM, "fwd": FWD_WOOL},
}


def build(name, out_root=OUT_ROOT):
    spec = VARIANTS[name]
    if spec["race"] is None:                      # forward only
        return build_fwd(spec["fwd"], name, out_root=out_root)
    # race block first (tested builder), then the forward block stacked on top.
    # `outer_prefix` renames the hook's globals: the composite defines its own
    # `_RACE_PARENT`, and rebinding it recursed (see build_race.outer_block).
    p = BR.build(spec["race"], name if spec["fwd"] is None else name + "_raceonly",
                 out_root=out_root, base_path=COMPOSITE, outer_prefix="_clr")
    check_collisions(COMPOSITE.read_text(), p.read_text())
    if spec["fwd"] is None:
        return p
    return build_fwd(spec["fwd"], name, base_path=p, out_root=out_root)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--variant", default="all", choices=sorted(VARIANTS) + ["all"])
    ap.add_argument("--out-root", default=str(OUT_ROOT))
    args = ap.parse_args()
    names = sorted(VARIANTS) if args.variant == "all" else [args.variant]
    for n in names:
        build(n, Path(args.out_root))


if __name__ == "__main__":
    main()
