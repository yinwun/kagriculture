#!/usr/bin/env python
"""Herd-swap variants of the champion (data/tapeopt/rgcs/main.py) — CRUDE first cut.

Purpose: the public frontier (`the-2945-farm-96-...`) ends 0.8 geese and 0.6 sheep
away from our champion on average, most on the 23 of 30 duel towns whose shop draw
contains a YARN_STORE, and those towns carry almost all of its +4,407.  Before
building anything clever we test the mechanism causally: rewrite the champion's own
tape-level animal program (the tapes are the farm plan) so that it keeps sheep
instead of geese/cows, then duel exactly the YARN_STORE towns and the non-YARN_STORE
towns separately.

Why a tape rewrite and not a new layer: our champion's animals are bought, built and
placed by the frozen route tapes (`BUY_ANIMAL`, `BUILD_COOP`/`BUILD_PASTURE`,
`PICKUP`/`PLACE`), and the pasture/coop tile layout, the feed budget and the care
route that follow are all per-tile scripted.  Rewriting the *animal kind* in place is
therefore exact and cheap: a pasture hosts a sheep exactly where a coop hosted a
goose, every animal eats WHEAT, and `FEED`/`CARE` are animal-agnostic.  The patch
below mutates the chassis' route actions in place at import time (the chassis shallow
copies the route lists, so in-place dict mutation is visible to it and to the wrapper
agents that read `_IMPL.chassis.routes` directly).

Every lever is OFF by default: `herd_geese = 0, herd_cows = 0` leaves the file
behaviourally identical to the champion (the `control` variant).

Usage: python scripts/build_herd.py            # writes data/herd/<name>/main.py
"""
from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
CHAMPION = ROOT / "data" / "tapeopt" / "rgcs" / "main.py"

ANCHOR_SETTINGS = "'front_run': False}"

PATCH = '''

# ===========================================================================
# herd swap (scripts/build_herd.py): rewrite the tape-level animal program so the
# farm keeps SHEEP where the tape planned GEESE and/or COWS.  The tapes own the
# animal plan -- BUY_ANIMAL in the market list, BUILD_COOP/BUILD_PASTURE on the
# tile, PICKUP/PLACE for the animal itself -- and a pasture hosts a sheep exactly
# where a coop hosted a goose, so substituting the animal kind (and the structure
# verb) keeps the pen layout, feed budget and care route intact.
# ===========================================================================
def _herd_swap_routes(routes, cfg):
    """Rewrite each route's animal plan in place; returns a small report."""
    n_geese = int(cfg.get("herd_geese", 0) or 0)
    n_cows = int(cfg.get("herd_cows", 0) or 0)
    target = cfg.get("herd_target", "SHEEP")
    if target not in ("SHEEP", "COW"):
        target = "SHEEP"
    swap_coop = bool(cfg.get("herd_coop_to_pasture", n_geese > 0))
    report = {"geese": 0, "cows": 0, "coops": 0, "routes": 0}
    if n_geese <= 0 and n_cows <= 0:
        return report

    for _rid, tape in routes.items():
        # the budget is PER ROUTE: only one route is ever replayed in a game, and
        # the router picks it from the shop draw, so a global budget would spend
        # itself on routes the game never uses (measured: it silently made this
        # lever a no-op on every seed).
        done = {"geese": 0, "cows": 0}

        def _kind(item):
            if item == "GOOSE" and done["geese"] < n_geese:
                done["geese"] += 1
                report["geese"] += 1
                return target
            if item == "COW" and done["cows"] < n_cows:
                done["cows"] += 1
                report["cows"] += 1
                return target
            return None

        report["routes"] += 1
        for act in tape:
            if not isinstance(act, dict):
                continue
            market = act.get("market")
            if isinstance(market, list):
                for order in market:
                    if (isinstance(order, list) and len(order) >= 2
                            and order[0] == "BUY_ANIMAL"):
                        new = _kind(order[1])
                        if new:
                            order[1] = new
            cmds = [act.get("farmer")] + list(act.get("hands") or [])
            for cmd in cmds:
                if not (isinstance(cmd, list) and cmd):
                    continue
                if cmd[0] == "BUILD_COOP" and swap_coop and target != "GOOSE":
                    cmd[0] = "BUILD_PASTURE"
                    report["coops"] += 1
                elif cmd[0] in ("PICKUP", "PLACE") and len(cmd) >= 2 \\
                        and cmd[1] in ("GOOSE", "COW"):
                    # keep the choreography consistent with the (rewritten) buy plan
                    if cmd[1] == "GOOSE" and report["geese"] > 0:
                        cmd[1] = "SHEEP"
                    elif cmd[1] == "COW" and report["cows"] > 0:
                        cmd[1] = "SHEEP"
    return report


_HERD_REPORT = _herd_swap_routes(_IMPL.chassis.routes, _IMPL.chassis.cfg)
'''


def build(settings, name, out_root=None):
    src = CHAMPION.read_text()
    assert src.count(ANCHOR_SETTINGS) == 1, "settings anchor not unique"
    assert "_herd_swap_routes" not in src, "champion already has a herd patch"
    extra = "".join(f", {k!r}: {v!r}" for k, v in sorted(settings.items()))
    out = src.replace(ANCHOR_SETTINGS, "'front_run': False" + extra + "}", 1)
    out = out.rstrip("\n") + "\n" + PATCH
    compile(out, "herd_main.py", "exec")
    root = Path(out_root) if out_root else ROOT / "data" / "herd"
    d = root / name
    d.mkdir(parents=True, exist_ok=True)
    target = d / "main.py"
    target.write_text(out)
    print(f"built {target} ({len(out):,} bytes, "
          f"sha256 {hashlib.sha256(out.encode()).hexdigest()[:12]}) settings={settings}")
    return target


# `herd_geese` / `herd_cows` = how many of the tape's GOOSE / COW animals become
# SHEEP (per route); 0 = lever off.  `herd_coop_to_pasture` converts the structures.
# The route 0/2 plan buys 2 geese, 6 cows, 4 sheep; route 1 buys 0 geese, 4 cows,
# 8 sheep.
VARIANTS = {
    "control":       {"herd_geese": 0, "herd_cows": 0},
    "g2s":           {"herd_geese": 2},
    "g2s_partial":   {"herd_geese": 1},
    "c2s":           {"herd_cows": 6},
    "c2s_partial":   {"herd_cows": 3},
    "g2s_c2s":       {"herd_geese": 2, "herd_cows": 6},
    "c2s_keepcoop":  {"herd_cows": 6, "herd_coop_to_pasture": False},
    # the OTHER direction the public herd layer swaps in: geese -> COWS (milk)
    "g2c":           {"herd_geese": 2, "herd_target": "COW"},
    "g2c_partial":   {"herd_geese": 1, "herd_target": "COW"},
    "g2c_c2s":       {"herd_geese": 2, "herd_target": "COW", "herd_cows": 6},
}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--name", default=None)
    ap.add_argument("--out-root", default=None)
    ap.add_argument("--set", action="append", default=[])
    args = ap.parse_args()
    if args.name:
        settings = dict(VARIANTS.get(args.name, {}))
        for item in args.set:
            k, _, v = item.partition("=")
            settings[k] = int(v) if v.lstrip("-").isdigit() else (v == "True")
        build(settings, args.name, args.out_root)
        return 0
    for name, settings in VARIANTS.items():
        build(settings, name, args.out_root)
    (ROOT / "data" / "herd" / "variants.json").write_text(json.dumps(VARIANTS, indent=1))
    print(f"built {len(VARIANTS)} variants under data/herd/")
    return 0


if __name__ == "__main__":
    sys.exit(main())
