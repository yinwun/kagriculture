#!/usr/bin/env python
"""Task 32(B): smoke-test then duel the new public candidates vs comp_straw on unused panels."""
import json, subprocess, sys
from pathlib import Path
ROOT = Path(__file__).resolve().parent.parent
CANDS = ["kaggriculture-utils-v1", "cha22-agent", "graph-reinforcement-learning",
         "the-shepherds-ledger-herd-safe-sovereign", "kaggriculture-thomas-2944-candidate",
         "kaggriculture-herd-safe-sale-window-race-ca25"]
PANELS = [("is", "9900-9929"), ("oos", "10100-10129")]

def smoke(path):
    code = ("import json,sys\n"
            "from pathlib import Path\n"
            "from kaggle_environments import make\n"
            "p=sys.argv[1]; ns={'__name__':'m'}\n"
            "exec(compile(Path(p).read_text(),p,'exec'),ns)\n"
            "e=make('kaggriculture',configuration={'episodeSteps':720,'seed':9900}); e.run([ns['agent'],ns['agent']])\n"
            "r=[float(e.steps[-1][i]['reward'] or 0) for i in (0,1)]\n"
            "print('OK' if min(r)>3000 else 'DEAD', r)\n")
    r = subprocess.run([".venv/bin/python", "-c", code, path], cwd=ROOT, capture_output=True, text=True, timeout=600)
    out = (r.stdout or "").strip().splitlines()
    return (out[-1] if out else f"FAIL {r.stderr.strip().splitlines()[-1][:80] if r.stderr else ''}")

alive = {}
print("=== SMOKE (720-step mirror; DEAD = wallet stuck at 3,000) ===")
for c in CANDS:
    p = ROOT / "data" / "cand" / f"{c}-extracted-main.py"
    if not p.exists():
        print(f"{c:46} NO FILE"); continue
    res = smoke(str(Path("data/cand") / f"{c}-extracted-main.py"))
    print(f"{c:46} {res}")
    if res.startswith("OK"):
        alive[c] = True
print(f"\n{len(alive)} candidates alive: {list(alive)}")
print("\n=== DUELS vs comp_straw ===")
print(f"{'candidate':46} {'panel':4} {'delta':>8} {'t':>7} {'W-L':>8} {'wallet cand/base':>20} {'exc':>5} verdict")
res = {}
for c in alive:
    for panel, seeds in PANELS:
        out = ROOT / "data" / "composite" / f"duel-t32-{c}-{panel}.json"
        if not out.exists():
            subprocess.run([".venv/bin/python", "scripts/ab_duel.py", "--cand", f"data/cand/{c}-extracted-main.py",
                            "--base", "data/composite/comp_straw/main.py", "--seeds", seeds,
                            "--label", c[:18], "--out", str(out)], cwd=ROOT, capture_output=True, text=True)
        if not out.exists():
            print(f"{c:46} {panel:4} DUEL FAILED"); continue
        d = json.loads(out.read_text()); res.setdefault(c, {})[panel] = d
        print(f"{c:46} {panel:4} {d['delta']:>+8,.0f} {d['t']:>+7.2f} {str(d['wins'])+'-'+str(d['losses']):>8} "
              f"{str(round(d['cand_wallet']))+'/'+str(round(d['base_wallet'])):>20} {d['cand_exceptions']:>5} "
              f"{'GO' if d['delta']>0 and d['t']>=3 else 'no-go'}")
print("\n=== BAR: delta>0 and t>=3 on BOTH panels ===")
for c, dd in res.items():
    if set(dd) == {"is", "oos"}:
        a, b = dd["is"], dd["oos"]
        go = a["delta"] > 0 and b["delta"] > 0 and a["t"] >= 3 and b["t"] >= 3
        print(f"  {c:46} {'GO' if go else 'no-go'}  IS {a['delta']:+,.0f} (t={a['t']:+.2f})  OOS {b['delta']:+,.0f} (t={b['t']:+.2f})")
    else:
        print(f"  {c:46} incomplete")
