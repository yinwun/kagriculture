#!/usr/bin/env python
"""Emit the markdown tables for REPORT-improve-to-2400.md."""
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
REF = "56642424"
eps = json.loads((ROOT / "data" / f"pi-episodes-{REF}.json").read_text())
attr = json.loads((ROOT / "data" / f"pi-attr-{REF}.json").read_text())
strength = json.loads((ROOT / "data" / f"pi-opp-strength-{REF}.json").read_text())
gs = {g["episodeId"]: g for g in attr["games"] if g["gate"]}
for e in eps:
    g = gs.get(e["eid"])
    if g:
        e["g"] = g
out = []
out.append("| # | episode | seat | our reward | opp reward | margin | opp team | opp LB score | opp own W-L | opp own WR | class |")
out.append("|---|---|---|---|---|---|---|---|---|---|---|")
for i, e in enumerate(sorted(eps, key=lambda x: x["margin"]), 1):
    g = e.get("g") or {}
    s = strength.get(str(e["opp_sub"])) or {}
    wr = f"{s['wins']/s['games']:.3f}" if s.get("games") else "?"
    wl = f"{s['wins']}-{s['losses']}" if s.get("games") else "?"
    cl = "**LOSS**" if e["margin"] <= 0 else ("close win" if e["margin"] < 2000 else "big win")
    out.append(f"| {i} | {e['eid']} | {e['my_seat']} | {e['my']:,.0f} | {e['opp']:,.0f} | "
               f"{e['margin']:+,.0f} | {e['opp_team']} | {e["opp_score"] if e["opp_score"] is not None else float("nan"):.1f} | {wl} | {wr} | {cl} |")
Path(ROOT / "data" / "pi-episode-table.md").write_text("\n".join(out) + "\n")
print("\n".join(out[:6]))
print(f"... {len(out)-2} rows -> data/pi-episode-table.md")
