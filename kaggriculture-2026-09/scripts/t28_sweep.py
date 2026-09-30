#!/usr/bin/env python
"""Task 28: per-item late-window forward sweep + per-component ablations, measured.

Builds each variant from the composite+race base with the same builder as comp_straw
(item swapped / component dropped), verifies the rebuild of comp_straw is byte-identical
(control), duels each against data/composite/comp_straw/main.py on two unused panels
(IS 9500-9529, OOS 9600-9629), and prints one compact table plus the JSON paths.
"""
import hashlib, json, subprocess, sys
from pathlib import Path
ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))
import build_composite_layers as B

STRAW = {"STRAWBERRY": 312}
ITEMS = {
    "comp_straw_wheat":  "WHEAT",
    "comp_straw_milk":   "MILK",
    "comp_straw_carrot": "CARROT",
    "comp_straw_tomato": "TOMATO",
    "comp_straw_egg":    "EGG",
    "comp_straw_fert":   "FERTILIZER",
}
def fwd(items, starts):
    return {**B.FWD_WOOL, "forward_items": items, "forward_start_by_item": starts}

B.VARIANTS.update({"comp_straw": {"race": B.RACE_PREM,
                                  "fwd": fwd(["WOOL", "STRAWBERRY"], STRAW)}})
for name, item in ITEMS.items():
    B.VARIANTS[name] = {"race": B.RACE_PREM,
                        "fwd": fwd(["WOOL", "STRAWBERRY", item], {**STRAW, item: 312})}
B.VARIANTS["comp_nowool"] = {"race": B.RACE_PREM, "fwd": fwd(["STRAWBERRY"], STRAW)}
B.VARIANTS["comp_norace"] = {"race": None, "fwd": fwd(["WOOL", "STRAWBERRY"], STRAW)}

def sha(p): return hashlib.sha256(Path(p).read_bytes()).hexdigest()
committed = sha(ROOT / "data/composite/comp_straw/main.py")
print("building variants...", flush=True)
for name in list(ITEMS) + ["comp_nowool", "comp_norace", "comp_straw"]:
    B.build(name)
print(f"CONTROL comp_straw rebuild byte-identical: {sha(ROOT/'data/composite/comp_straw/main.py') == committed}", flush=True)

PAIRS = [("is", "9500-9529"), ("oos", "9600-9629")]
import os
ORDER = dict(abl=["comp_both","comp_nowool","comp_norace"], items=list(ITEMS),
             all=list(ITEMS)+["comp_nowool","comp_norace","comp_both"])
targets = ORDER.get(os.environ.get("T28_SET","all"), ORDER["all"])
for name in targets:
    for panel, seeds in PAIRS:
        out = ROOT / "data" / "composite" / f"duel-t28-{name}-{panel}.json"
        if out.exists():
            continue
        cmd = [".venv/bin/python", "scripts/ab_duel.py", "--cand", f"data/composite/{name}/main.py",
               "--base", "data/composite/comp_straw/main.py", "--seeds", seeds,
               "--label", name, "--out", str(out)]
        subprocess.run(cmd, cwd=ROOT, capture_output=True, text=True)
        print(f"duelled {name} {panel}", flush=True)

print("\n=== TASK 28 SWEEP (cand vs comp_straw) ===")
hdr = f"{'variant':20} {'panel':4} {'delta':>8} {'%':>7} {'t':>7} {'W-L':>8} {'pos/neg':>8} {'err':>4} {'exc':>4}"
print(hdr)
rows = {}
for name in targets:
    for panel, _ in PAIRS:
        p = ROOT / "data" / "composite" / f"duel-t28-{name}-{panel}.json"
        if not p.exists():
            print(f"{name:20} {panel:4} MISSING"); continue
        d = json.loads(p.read_text())
        ps = [r["delta"] for r in d["per_seed"]]
        pct = 100 * d["delta"] / d["base_wallet"]
        print(f"{name:20} {panel:4} {d['delta']:>+8,.0f} {pct:>+6.2f}% {d['t']:>+7.2f} "
              f"{str(d['wins'])+'-'+str(d['losses']):>8} "
              f"{str(sum(1 for x in ps if x>0))+'/'+str(sum(1 for x in ps if x<0)):>8} "
              f"{d['errors']:>4} {d['cand_exceptions']:>4}")
        rows.setdefault(name, {})[panel] = d
print("\nGO/NO-GO (d>0, t>=3 both panels, delta>=+300):")
for name, dd in rows.items():
    if set(dd) < {"is", "oos"}:
        print(f"  {name:20} incomplete"); continue
    a, b = dd["is"], dd["oos"]
    go = a["delta"] > 0 and b["delta"] > 0 and a["t"] >= 3 and b["t"] >= 3 and min(a["delta"], b["delta"]) >= 300
    print(f"  {name:20} {'GO' if go else 'no-go'}   IS {a['delta']:+,.0f} (t={a['t']:+.2f})  OOS {b['delta']:+,.0f} (t={b['t']:+.2f})")
