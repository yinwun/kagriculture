#!/usr/bin/env python
"""Extract the agent source (and its route blob / opening) straight from a .ipynb.

Building these composites is expensive; the extractive questions (has the route blob
changed? what is the step-0 opening?) only need the SOURCE text, which sits in the
notebook's `%%writefile main.py` cells.  This pulls those cells out, hashes every
base85+zlib route blob against our champion's, and reports opening-like constants.

Usage: .venv/bin/python scripts/notebook_extract.py data/cand/<nb>.ipynb
"""
from __future__ import annotations

import argparse
import base64
import hashlib
import json
import re
import zlib
from pathlib import Path

BLOB = re.compile(r"base64\.b85decode\('([^']+)'\)")
CHAMPION_BLOB_SHA = "54fe156ea7206e38"
WRITEFILE = re.compile(r"^%%writefile\s+(\S+)")


def cells(path):
    nb = json.loads(Path(path).read_text())
    out = {}
    for c in nb.get("cells", []):
        if c.get("cell_type") != "code":
            continue
        src = "".join(c.get("source") or [])
        m = WRITEFILE.search(src.split("\n", 1)[0])
        if m:
            out.setdefault(m.group(1), []).append(src)
        elif "def agent(" in src and "main.py" not in out:
            out.setdefault("main.py", []).append(src)
    return {k: "\n".join(v) for k, v in out.items()}


def analyse(path):
    srcs = cells(path)
    print(f"=== {Path(path).name}: writefile cells {list(srcs)}")
    total = sum(len(v) for v in srcs.values())
    print(f"    source chars {total:,}")
    for name, src in srcs.items():
        for i, blob in enumerate(BLOB.findall(src)):
            sha = hashlib.sha256(blob.encode()).hexdigest()[:16]
            same = "SAME AS OUR CHAMPION" if sha == CHAMPION_BLOB_SHA else "DIFFERENT"
            try:
                data = json.loads(zlib.decompress(base64.b85decode(blob)))
                info = f"routes {len(data.get('routes') or {})} actions {len(data.get('actions') or [])}"
            except Exception as exc:
                info = f"decode failed {exc!r}"
            print(f"    [{name}] blob {i}: sha {sha} ({same}) {info} chars {len(blob):,}")
        # opening-like constants and step-0 tape edits
        for m in re.finditer(r"^(_?\w*OPENING\w*)\s*=\s*(\[.*?\])\s*$", src, re.M):
            print(f"    [{name}] {m.group(1)} = {m.group(2)[:160]}")
        for m in re.finditer(r"[^\n]*(WHEAT',\s*\d+)[^\n]*", src):
            line = m.group(0).strip()
            if "BUY_PRODUCT" in line and "SELL" in line and len(line) < 300:
                print(f"    [{name}] opening-like line: {line[:200]}")
    return srcs


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("notebooks", nargs="+")
    a = ap.parse_args()
    for p in a.notebooks:
        analyse(p)
