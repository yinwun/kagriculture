#!/usr/bin/env python
"""Build `swapmelon`: champion choreography with the portfolio tilted to strawberry.

Why: the independent dissection of the current top two (destbreso, "Dissecting the
top two") found the chassis carries two portfolios -- A = melon 20 / strawberry 34,
B = melon 12 / strawberry 42 -- and that the winning mutation was biasing the choice
towards B, the "absorption-shaped" portfolio (less melon, whose book is shallow,
more strawberry, whose book is deep).  Our own 41-route library turns out to be 41
*choreographies of one portfolio*: every route plants strawberry 33 / melon 12 /
wheat ~163 (scripts/route_profile output).  So the portfolio axis is untested here,
and it is the one axis the analyses say decides the top of this ladder.

The patch rewrites the tape data in place, right after `_ROUTES` is built:

    PLANT MELON   -> PLANT STRAWBERRY
    BUY_SEED MELON-> BUY_SEED STRAWBERRY

Nothing else changes: same choreography, same sell schedule, same crew.  This
deliberately tests the *portfolio* effect alone, and is expected to need timing
repair (strawberry is ongoing with first_yield_day 10, melon one-shot with
max_yield_day 12), so a negative result is informative rather than surprising.

Usage:
  python scripts/build_swapmelon.py                    # -> data/tapeopt/swapmelon/main.py
  python scripts/build_swapmelon.py --from MELON --to TOMATO --out ...
"""
import argparse
import hashlib
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
CHAMPION = ROOT / "data" / "tapeopt" / "rgcs" / "main.py"

PATCH = '''
# --- portfolio swap: {frm} -> {to} (choreography untouched) -------------------
_SWAP_DIAG = {{"plant": 0, "seed": 0}}
for _swap_tape in _ROUTES.values():
    for _swap_step in _swap_tape:
        if not isinstance(_swap_step, dict):
            continue
        _u = [_swap_step.get("farmer") or []] + list(_swap_step.get("hands") or [])
        for _k, _c in enumerate(_u):
            if isinstance(_c, list) and len(_c) > 1 and _c[0] == "PLANT" and _c[1] == "{frm}":
                _new = ["PLANT", "{to}"]
                if _k == 0:
                    _swap_step["farmer"] = _new
                else:
                    _swap_step["hands"][_k - 1] = _new
                _SWAP_DIAG["plant"] += 1
        _mk = _swap_step.get("market")
        if _mk:
            for _o in _mk:
                if isinstance(_o, list) and len(_o) > 2 and _o[0] == "BUY_SEED" and _o[1] == "{frm}":
                    _o[1] = "{to}"
                    _SWAP_DIAG["seed"] += 1
del _swap_tape, _swap_step
'''


def build(out, frm="MELON", to="STRAWBERRY"):
    src = CHAMPION.read_text()
    assert "_SWAP_DIAG" not in src, "already patched"
    anchor = "_R108_SHOP_ROUTES={tuple(r['shops']):r['route'] for r in _R108_DATA['shops']}"
    assert src.count(anchor) == 1, "route anchor not found"
    src = src.replace(anchor, anchor + PATCH.format(frm=frm, to=to), 1)
    out = Path(out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(src)
    print(f"wrote {out} ({len(src):,} bytes, sha256 {hashlib.sha256(src.encode()).hexdigest()[:12]})")
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--from", dest="frm", default="MELON")
    ap.add_argument("--to", dest="to", default="STRAWBERRY")
    ap.add_argument("--out", default=None)
    args = ap.parse_args()
    out = args.out or str(ROOT / "data" / "tapeopt" /
                          ("swap" + args.frm.lower()[:4] + args.to.lower()[:4] + "/main.py"))
    build(out, args.frm, args.to)
    return 0


if __name__ == "__main__":
    sys.exit(main())
