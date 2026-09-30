#!/usr/bin/env python
"""Extract a RUNNABLE main.py from a .ipynb without executing the notebook.

Concatenates the `%%writefile main.py` cells (stripping the magic line), or falls back to
the single cell that defines `agent`, and prints the provenance: every base85+zlib route
blob's sha256 (vs our champion's 54fe156ea7206e38) and the opening-like constants.

Usage: python scripts/notebook_to_main.py data/cand/x.ipynb [more.ipynb ...]
"""
import argparse, hashlib, json, re, sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent))
from notebook_extract import BLOB, CHAMPION_BLOB_SHA, cells  # noqa: E402

def strip_magic(src):
    lines = src.split("\n")
    if lines and lines[0].startswith("%%"):
        return "\n".join(lines[1:])
    return src

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("notebooks", nargs="+")
    ap.add_argument("--out-dir", default="data/cand")
    args = ap.parse_args()
    for nb in args.notebooks:
        p = Path(nb)
        try:
            srcs = cells(p)
        except Exception as exc:
            print(f"[{p.name}] PARSE FAIL {exc!r}"); continue
        if "main.py" not in srcs:
            print(f"[{p.name}] no main.py cell (cells: {list(srcs)})"); continue
        src = strip_magic(srcs["main.py"])
        out = Path(args.out_dir) / f"{p.stem}-extracted-main.py"
        out.write_text(src)
        blobs = BLOB.findall(src)
        info = []
        for i, b in enumerate(blobs):
            sha = hashlib.sha256(b.encode()).hexdigest()[:16]
            try:
                data = json.loads(__import__("zlib").decompress(__import__("base64").b85decode(b)))
                detail = f"routes {len(data.get('routes') or {})} actions {len(data.get('actions') or [])}"
            except Exception as exc:
                detail = f"decode failed {exc!r}"
            info.append(f"blob{i} {sha}{'=OURS' if sha==CHAMPION_BLOB_SHA else ''} ({detail})")
        ops = re.findall(r"^(_?\w*OPENING\w*)\s*=\s*(\[[^\n]{0,120})", src, re.M)
        print(f"[{p.name}] chars {len(src):,} -> {out}")
        print(f"    blobs: {'; '.join(info) or 'none (plain source)'}")
        for name, val in ops[:3]:
            print(f"    {name} = {val[:110]}")
        print(f"    compile: ", end="")
        try:
            compile(src, str(out), "exec"); print("OK")
        except SyntaxError as exc:
            print(f"FAIL {exc}")

if __name__ == "__main__":
    main()
