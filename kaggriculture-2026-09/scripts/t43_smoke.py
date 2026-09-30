#!/usr/bin/env python
"""Task 43 smoke gate: 720-step self-play on a fresh seed, statuses + nonzero counters.

Usage: .venv/bin/python scripts/t43_smoke.py data/frontier4/main/*.py
"""
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SMOKE = """
import sys
from pathlib import Path
from kaggle_environments import make
p = sys.argv[1]
ns = {"__name__": "m"}
exec(compile(Path(p).read_text(), p, "exec"), ns)
e = make("kaggriculture", configuration={"episodeSteps": 720, "seed": 17000})
errs = {"n": 0, "last": ""}
inner = ns["agent"]
def wrap(obs, *a, **k):
    try:
        return inner(obs, *a, **k)
    except BaseException as exc:
        errs["n"] += 1
        errs["last"] = f"{type(exc).__name__}: {exc}"[:120]
        raise
e.run([wrap, wrap])
st = [str(e.steps[-1][i]["status"]) for i in (0, 1)]
rw = [round(float(e.steps[-1][i]["reward"] or 0)) for i in (0, 1)]
d = getattr(ns.get("_IMPL"), "chassis", None)
diag = {k: int(v) for k, v in (d.diagnostics.items() if d else []) if v}
print("RESULT", st, rw, "exceptions", errs["n"], errs["last"], "diag", diag)
"""


def main():
    for p in sys.argv[1:]:
        r = subprocess.run([".venv/bin/python", "-c", SMOKE, p], cwd=ROOT, capture_output=True, text=True,
                           timeout=1200)
        out = (r.stdout or "") + (r.stderr or "")
        line = next((l for l in out.splitlines() if l.startswith("RESULT")), None)
        print(f"{Path(p).stem[:46]:46} {line or out.strip().splitlines()[-1][:150] if out.strip() else 'NO OUTPUT'}",
              flush=True)


if __name__ == "__main__":
    main()
