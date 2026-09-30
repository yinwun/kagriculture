#!/usr/bin/env python
"""Task 43 screen: smoke-gated paired duels of freshly extracted frontier engines vs pi_stack.

Panels 17000-17029 / 17100-17129 are fresh (unused by t35-t42).  Primary instrument is
`ab_duel.py --cand <frontier engine> --base data/candidate/pi_stack/main.py`; for the key
candidates an extra engine-vs-engine diagnostic against the bare V78 base (`pi_base`) is run,
because our layers are worth ~+593 on that base and the bar "beats pi_stack" is therefore
~600 coins above "beats V78".

Usage: .venv/bin/python scripts/t43_screen.py [--only NAME ...]
"""
from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
PI_STACK = "data/candidate/pi_stack/main.py"
PI_BASE = "data/cand/31415926535897932384626433832795058202884197169399-extracted-main.py"
P1, P2 = "17000-17029", "17100-17129"

# label -> extracted main
CANDS = {
    "t43-the2965": "data/frontier4/main/the-2965-master-hybrid-engine-main.py",
    "t43-harvestledger": "data/frontier4/main/kaggriculture-harvest-ledger-main.py",
    "t43-demandpreserving": "data/frontier4/main/demand-preserving-turn-sale-timing-main.py",
    "t43-songoffire": "data/frontier4/main/a-song-of-ice-and-fire-fixed-flexible-main.py",
    "t43-multiroute": "data/frontier4/main/kaggriculture-multi-route-farming-agent-main.py",
    "t43-graphrl": "data/frontier4/main/graph-reinforcement-learning-main.py",
    "t43-autonomous": "data/frontier4/main/kaggriculture-autonomous-ai-farming-agent-main.py",
    "t43-wheatseller": "data/frontier4/main/farmer-john-and-the-wheat-seller-main.py",
    "t43-2026v1-tape": "data/frontier4/main/kaggriculture-2026-v1-main.py",
    "t43-masterenginev5": "data/frontier4/main/kaggriculture-master-engine-v53e01d74d8f-main.py",
    "t43-poprobust": "data/frontier4/main/kaggriculture-population-robust-economy-main.py",
    "t43-idleseller": "data/frontier4/main/farmer-john-and-the-idle-seller-main.py",

    "t43-godsmode": "data/frontier4/gods_mode_driver.py",
    "t43-marketshock": "data/frontier4/main/marketshock_m1_wr1k-main.py",
    "t43-shepherds-fresh": "data/frontier4/main/the-shepherds-ledger-herd-safe-sovereign-main.py",
}
DIAG_BASE = ["t43-the2965", "t43-harvestledger", "t43-demandpreserving", "t43-songoffire",
             "t43-multiroute", "t43-graphrl", "t43-godsmode", "t43-marketshock", "t43-shepherds-fresh"]


def duel(cand: str, base: str, seeds: str, label: str, out: Path) -> dict | None:
    if not out.exists():
        subprocess.run([".venv/bin/python", "scripts/ab_duel.py", "--cand", cand, "--base", base,
                        "--seeds", seeds, "--label", label, "--out", str(out)],
                       cwd=ROOT, capture_output=True, text=True)
    if not out.exists():
        return None
    return json.loads(out.read_text())


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--only", nargs="*", default=None)
    a = ap.parse_args()
    outdir = ROOT / "data" / "frontier4" / "duels"
    outdir.mkdir(parents=True, exist_ok=True)
    res: dict = {"vs_pi_stack": {}, "vs_pi_base": {}}
    names = a.only or list(CANDS)
    for name in names:
        cand = CANDS[name]
        for panel, seeds in (("p1", P1), ("p2", P2)):
            o = outdir / f"{name}-vs-pistack-{panel}.json"
            d = duel(cand, PI_STACK, seeds, name, o)
            if d:
                res["vs_pi_stack"].setdefault(name, {})[panel] = d
                print(f"{name:24} vs pi_stack {panel}: d={d['delta']:+,.0f} t={d['t']:+.2f} "
                      f"W-L {d['wins']}-{d['losses']} exc={d['cand_exceptions']}/{d['base_exceptions']} "
                      f"err={d['errors']}", flush=True)
        if name in DIAG_BASE:
            for panel, seeds in (("p1", P1), ("p2", P2)):
                o = outdir / f"{name}-vs-pibase-{panel}.json"
                d = duel(cand, PI_BASE, seeds, name, o)
                if d:
                    res["vs_pi_base"].setdefault(name, {})[panel] = d
                    print(f"{name:24} vs pi_base  {panel}: d={d['delta']:+,.0f} t={d['t']:+.2f} "
                          f"W-L {d['wins']}-{d['losses']} exc={d['cand_exceptions']}/{d['base_exceptions']} "
                          f"err={d['errors']}", flush=True)
    prev_path = ROOT / "data" / "frontier4" / "screen.json"
    if prev_path.exists():
        prev = json.loads(prev_path.read_text())
        for sect in ("vs_pi_stack", "vs_pi_base"):
            for name, dd in (prev.get(sect) or {}).items():
                res[sect].setdefault(name, {}).update(dd)
    prev_path.write_text(json.dumps(res, indent=1))
    print("=== BAR: beats pi_stack (delta>0, t>=3 on BOTH panels) ===")
    for name, dd in res["vs_pi_stack"].items():
        if set(dd) == {"p1", "p2"}:
            x, y = dd["p1"], dd["p2"]
            ok = x["delta"] > 0 and y["delta"] > 0 and x["t"] >= 3 and y["t"] >= 3
            print(f"  {name:24} {'GO' if ok else 'no-go'}  p1 {x['delta']:+,.0f} (t={x['t']:+.2f})  "
                  f"p2 {y['delta']:+,.0f} (t={y['t']:+.2f})")
    print("=== engine-vs-engine: beats bare V78 base ===")
    for name, dd in res["vs_pi_base"].items():
        if set(dd) == {"p1", "p2"}:
            x, y = dd["p1"], dd["p2"]
            ok = x["delta"] > 0 and y["delta"] > 0 and x["t"] >= 3 and y["t"] >= 3
            print(f"  {name:24} {'STRONGER' if ok else 'weaker  '}  p1 {x['delta']:+,.0f} (t={x['t']:+.2f})  "
                  f"p2 {y['delta']:+,.0f} (t={y['t']:+.2f})")
    return 0


if __name__ == "__main__":
    sys.exit(main())
