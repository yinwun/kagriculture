#!/usr/bin/env python
"""Task 33: high-power validation of the shepherds-ledger candidate vs comp_straw.

Runs the two new 60-town panels (10200-10259, 10300-10359), then pools all four panels
(9900-9929, 10100-10129, 10200-10259, 10300-10359), reporting per-panel delta/t/W-L and the
pooled estimate with its t and the positive-town fraction, plus the action-mix diff.
"""
import json, statistics as st, subprocess
from pathlib import Path
ROOT = Path(__file__).resolve().parent.parent
CAND = "data/cand/the-shepherds-ledger-herd-safe-sovereign-extracted-main.py"
BASE = "data/composite/comp_straw/main.py"
PANELS = [("p1", "9900-9929", "data/composite/duel-t32-the-shepherds-ledger-herd-safe-sovereign-is.json"),
          ("p2", "10100-10129", "data/composite/duel-t32-the-shepherds-ledger-herd-safe-sovereign-oos.json"),
          ("p3", "10200-10259", "data/composite/duel-t33-shepherds-p3.json"),
          ("p4", "10300-10359", "data/composite/duel-t33-shepherds-p4.json")]

for name, seeds, out in PANELS[2:]:
    if Path(ROOT / out).exists():
        continue
    print(f"running {name} ({seeds})...", flush=True)
    subprocess.run([".venv/bin/python", "scripts/ab_duel.py", "--cand", CAND, "--base", BASE,
                    "--seeds", seeds, "--label", "shepherds", "--out", out], cwd=ROOT,
                   capture_output=True, text=True)

print("\n=== PER-PANEL (candidate vs comp_straw) ===")
allps, rows = [], []
for name, seeds, out in PANELS:
    p = ROOT / out
    if not p.exists():
        print(f"{name} {seeds:12} MISSING"); continue
    d = json.loads(p.read_text()); ps = [r["delta"] for r in d["per_seed"]]
    allps += ps
    rows.append((name, seeds, d, ps))
    print(f"{name} {seeds:12} n_towns {len(ps):3} games {d['games']:3} d={d['delta']:+8,.0f} "
          f"({100*d['delta']/d['base_wallet']:+.2f}%) t={d['t']:+6.2f} W-L {d['wins']}-{d['losses']} "
          f"wallet {round(d['cand_wallet'])}/{round(d['base_wallet'])} "
          f"pos {sum(1 for x in ps if x>0)}/{len(ps)} exc {d['cand_exceptions']}/{d['base_exceptions']} err {d['errors']}")
if len(allps) > 1:
    m = st.mean(allps); se = st.stdev(allps) / len(allps) ** 0.5
    print(f"\n=== POOLED four panels ===\n  towns {len(allps)}  delta {m:+,.0f}  t {m/se:+.2f}  "
          f"positive towns {sum(1 for x in allps if x>0)}/{len(allps)} ({100*sum(1 for x in allps if x>0)/len(allps):.1f}%)  "
          f"median {st.median(allps):+,.0f}  min {min(allps):+,.0f}  max {max(allps):+,.0f}")
    print(f"  BAR (d>0, t>=3 on BOTH new panels): " +
          ("CLEARED" if all(rows[i][2]['delta'] > 0 and rows[i][2]['t'] >= 3 for i in (2, 3) if i < len(rows))
           else "NOT cleared"))
# action mix
if rows:
    d = rows[-1][2]
    cm, bm = d["cand_mech"], d["base_mech"]
    keys = sorted(set(cm) | set(bm))
    print("\n=== action-mix diff (candidate - base), pooled over the last panel ===")
    for k in keys:
        dd = cm.get(k, 0) - bm.get(k, 0)
        if abs(dd) > max(40, 0.02 * max(bm.get(k, 0), 1)):
            print(f"  {k:22} {cm.get(k,0):8d} vs {bm.get(k,0):8d}  ({dd:+d})")
    print(f"  counters: cand={d['cand_diag']} base={d['base_diag']}")
