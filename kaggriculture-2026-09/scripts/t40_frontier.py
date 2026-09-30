#!/usr/bin/env python
"""Task 40: fast frontier scan -- provenance (incl. route-table test on different payloads),
offline extraction, smoke, duels vs shep_v_cap24."""
import base64, csv, hashlib, json, re, subprocess, sys, zlib
from pathlib import Path
ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))
from notebook_extract import BLOB, CHAMPION_BLOB_SHA
from notebook_b64_extract import decode_payload, LONG
BASE = "data/candidate/shep_v_cap24/main.py"
PANELS = [("p1", "13000-13029"), ("p2", "13100-13129")]
def sh(cmd, t=3600): return subprocess.run(cmd, cwd=ROOT, capture_output=True, text=True, timeout=t)
def blob_kind(b85):
    """Is this b85 blob a route table (routes/actions) or something else?"""
    try:
        d = json.loads(zlib.decompress(base64.b85decode(b85)))
    except Exception:
        try:
            d = json.loads(base64.b85decode(b85))
        except Exception as exc:
            return f"not-JSON ({type(exc).__name__})"
    if isinstance(d, dict):
        r, a = d.get("routes"), d.get("actions")
        return f"ROUTE TABLE routes={len(r) if r else 0} actions={len(a) if a else 0}" if r else f"dict keys={list(d)[:4]}"
    return f"{type(d).__name__} len={len(d)}"
rows = list(csv.DictReader(open(ROOT / "data" / "notebooks-t40.csv")))[:20]
print("=== PROVENANCE (newest 20) ===", flush=True)
diff_flag, runnable = [], []
for r in rows:
    slug = r["ref"]; nb = ROOT / "data" / "cand" / (slug.split("/")[-1] + ".ipynb")
    if not nb.exists():
        sh([".venv/bin/python", "-m", "kaggle", "kernels", "pull", slug, "-p", "data/cand"], 600)
    if not nb.exists():
        print(f"  {slug[:52]:52} PULL FAILED"); continue
    try:
        text = "\n".join("".join(c.get("source") or []) for c in json.loads(nb.read_text()).get("cells", []))
    except Exception as exc:
        print(f"  {slug[:52]:52} PARSE FAIL {exc!r}"); continue
    found = {hashlib.sha256(b.encode()).hexdigest()[:16]: b for b in BLOB.findall(text)}
    for cand in sorted(set(LONG.findall(text)), key=len, reverse=True)[:1]:
        got = decode_payload(base64.b64decode(re.sub(r"\s+", "", cand) + "=="))
        if got:
            for b in BLOB.findall(got[0].decode("utf-8", "replace")):
                found[hashlib.sha256(b.encode()).hexdigest()[:16]] = b
    kinds = {s: blob_kind(b) for s, b in found.items()}
    ours = CHAMPION_BLOB_SHA in kinds
    other = {s: k for s, k in kinds.items() if s != CHAMPION_BLOB_SHA}
    tag = ("OURS" if ours else "no-blob") + (f" OTHER {other}" if other else "")
    print(f"  {slug[:52]:52} {tag}")
    if other: diff_flag.append((slug, other))
    for script in ("notebook_b64_extract.py", "notebook_to_main.py"):
        out = sh([".venv/bin/python", f"scripts/{script}", str(nb.relative_to(ROOT))], 600).stdout
        for line in out.splitlines():
            if "chars" in line and "->" in line:
                print(f"      extract: {line.strip()[:120]}")
    p = ROOT / "data" / "cand" / f"{nb.stem}-extracted-main.py"
    if p.exists(): runnable.append((slug, p))
print(f"\nDIFFERENT PAYLOADS: {[(s, k) for s, k in diff_flag] or 'NONE'}")
print(f"runnable extracted: {len(runnable)}")
SMOKE = ("import sys\nfrom pathlib import Path\nfrom kaggle_environments import make\n"
         "p=sys.argv[1]; ns={'__name__':'m'}; exec(compile(Path(p).read_text(),p,'exec'),ns)\n"
         "e=make('kaggriculture',configuration={'episodeSteps':720,'seed':13000}); e.run([ns['agent'],ns['agent']])\n"
         "r=[float(e.steps[-1][i]['reward'] or 0) for i in (0,1)]\nprint('OK' if min(r)>3000 else 'DEAD', r)\n")
print("\n=== SMOKE + DUELS vs cap24 ===")
res = {}
for slug, p in runnable:
    s = sh([".venv/bin/python", "-c", SMOKE, str(p.relative_to(ROOT))], 900)
    line = (s.stdout or s.stderr).strip().splitlines()
    v = line[-1] if line else "FAIL"
    print(f"  {slug[:46]:46} {v[:60]}", flush=True)
    if not v.startswith("OK"): continue
    for panel, seeds in PANELS:
        o = ROOT / "data" / "candidate" / f"duel-t40-{p.stem}-{panel}.json"
        if not o.exists():
            sh([".venv/bin/python", "scripts/ab_duel.py", "--cand", str(p.relative_to(ROOT)), "--base", BASE,
                "--seeds", seeds, "--label", p.stem[:16], "--out", str(o.relative_to(ROOT))])
        if o.exists():
            d = json.loads(o.read_text()); res.setdefault(slug, {})[panel] = d
            print(f"      {panel} d={d['delta']:+,.0f} t={d['t']:+.2f} W-L {d['wins']}-{d['losses']} "
                  f"exc={d['cand_exceptions']} err={d['errors']}", flush=True)
print("\n=== BAR (delta>0, t>=3 both panels) vs cap24 ===")
win = None
for slug, dd in res.items():
    if set(dd) == {"p1", "p2"}:
        a, b = dd["p1"], dd["p2"]
        go = a["delta"] > 0 and b["delta"] > 0 and a["t"] >= 3 and b["t"] >= 3
        if go: win = slug
        print(f"  {slug[:46]:46} {'GO' if go else 'no-go'}  p1 {a['delta']:+,.0f} (t={a['t']:+.2f})  p2 {b['delta']:+,.0f} (t={b['t']:+.2f})")
    else:
        print(f"  {slug[:46]:46} incomplete")
print(f"WINNER: {win or 'NONE'}")
json.dump({"diff": diff_flag, "res": {k: v for k, v in res.items()}, "winner": win},
          open(ROOT / "data" / "t40-frontier.json", "w"), default=str)
