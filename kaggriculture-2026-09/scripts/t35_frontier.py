#!/usr/bin/env python
"""Task 35(2): new-notebook provenance + duel runnable candidates vs shep_straw."""
import csv, json, subprocess, sys
from pathlib import Path
ROOT = Path(__file__).resolve().parent.parent
BASE = "data/candidate/shep_straw/main.py"
PANELS = [("p1", "10400-10429"), ("p2", "10500-10529")]
def sh(cmd, **kw): return subprocess.run(cmd, cwd=ROOT, capture_output=True, text=True, **kw)
print("=== provenance guard on the newest 16 ===", flush=True)
sh([".venv/bin/python", "scripts/provenance_guard.py", "--csv", "data/notebooks-t35.csv",
    "--limit", "16", "--out", "data/provenance-guard-t35.json"], timeout=3600)
print(Path("data/provenance-guard-t35.json").exists())
rows = list(csv.DictReader(open("data/notebooks-t35.csv")))[:16]
run = []
print("\n=== extraction ===", flush=True)
for r in rows:
    nb = ROOT / "data" / "cand" / (r["ref"].split("/")[-1] + ".ipynb")
    if not nb.exists():
        continue
    for script in ("notebook_b64_extract.py", "notebook_to_main.py"):
        out = sh([".venv/bin/python", f"scripts/{script}", str(nb.relative_to(ROOT))]).stdout.strip()
        for line in out.splitlines():
            if "chars" in line or "blob" in line or "no main.py" in line:
                print(f"  {r['ref'][:44]:44} {line[:150]}")
    p = ROOT / "data" / "cand" / f"{nb.stem}-extracted-main.py"
    if p.exists():
        run.append((r["ref"], p))
print("\n=== smoke + duels vs shep_straw ===")
code = ("import sys\nfrom pathlib import Path\nfrom kaggle_environments import make\n"
        "p=sys.argv[1]; ns={'__name__':'m'}; exec(compile(Path(p).read_text(),p,'exec'),ns)\n"
        "e=make('kaggriculture',configuration={'episodeSteps':720,'seed':10400}); e.run([ns['agent'],ns['agent']])\n"
        "r=[float(e.steps[-1][i]['reward'] or 0) for i in (0,1)]\nprint('OK' if min(r)>3000 else 'DEAD', r)\n")
res = {}
for slug, p in run:
    r = sh([".venv/bin/python", "-c", code, str(p.relative_to(ROOT))], timeout=900)
    out = (r.stdout or "").strip().splitlines()
    verdict = out[-1] if out else "FAIL " + (r.stderr.strip().splitlines()[-1][:70] if r.stderr else "")
    print(f"{slug[:44]:44} {verdict}")
    if not verdict.startswith("OK"):
        continue
    for panel, seeds in PANELS:
        o = ROOT / "data" / "candidate" / f"duel-t35-{p.stem}-{panel}.json"
        sh([".venv/bin/python", "scripts/ab_duel.py", "--cand", str(p.relative_to(ROOT)),
            "--base", BASE, "--seeds", seeds, "--label", p.stem[:16], "--out", str(o.relative_to(ROOT))], timeout=3600)
        if o.exists():
            d = json.loads(o.read_text()); res.setdefault(slug, {})[panel] = d
            print(f"  {panel} d={d['delta']:+,.0f} t={d['t']:+.2f} W-L {d['wins']}-{d['losses']} "
                  f"exc={d['cand_exceptions']}/{d['base_exceptions']} err={d['errors']}")
print("\n=== BAR (d>0, t>=3 both panels) vs shep_straw ===")
for slug, dd in res.items():
    if set(dd) == {"p1", "p2"}:
        a, b = dd["p1"], dd["p2"]
        go = a["delta"] > 0 and b["delta"] > 0 and a["t"] >= 3 and b["t"] >= 3
        print(f"  {slug[:44]:44} {'GO' if go else 'no-go'}  p1 {a['delta']:+,.0f} (t={a['t']:+.2f})  p2 {b['delta']:+,.0f} (t={b['t']:+.2f})")
    else:
        print(f"  {slug[:44]:44} incomplete")
