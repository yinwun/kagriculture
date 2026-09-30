#!/usr/bin/env python
"""Extract the compressed route/tape table (`_R108_DATA`) from a public notebook
build of the same lineage, in the shape our own chassis replays.

Our champion loads `_R108_DATA = json.loads(zlib.decompress(base64.b85decode(<blob>)))`
with `_ROUTES = {int(k): [_R108_DATA['actions'][i] for i in ids] ...}`, and the public
builds of the same lineage (yhay81 shop-router data, Apache-2.0, via the notebook
composites) carry the same structure with newer snapshots.  This script decodes every
blob in a file, reports its shape, and writes the newest one as
`data/snapshot/<name>.json` with provenance.

Usage: .venv/bin/python scripts/extract_snapshot.py --file <notebook main.py> --name <short>
"""
from __future__ import annotations

import argparse
import base64
import hashlib
import json
import re
import zlib
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
BLOB = re.compile(r"base64\.b85decode\('([^']+)'\)")


def decode_all(path):
    src = Path(path).read_text()
    out = []
    for m in BLOB.finditer(src):
        try:
            data = json.loads(zlib.decompress(base64.b85decode(m.group(1))))
        except Exception as exc:                      # pragma: no cover
            out.append({"error": repr(exc), "len": len(m.group(1))})
            continue
        routes = data.get("routes") or {}
        acts = data.get("actions") or []
        out.append({
            "start": m.start(),
            "blob_chars": len(m.group(1)),
            "blob_sha256": hashlib.sha256(m.group(1).encode()).hexdigest()[:16],
            "keys": sorted(data.keys()),
            "routes": len(routes),
            "actions": len(acts),
            "route_ids": sorted(int(k) for k in routes.keys()),
            "route_lens": sorted({len(ids) for ids in routes.values()}),
            "max_step": max((int(i) for ids in routes.values() for i in ids), default=-1),
            "data": data,
            "blob": m.group(1),
        })
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--file", required=True)
    ap.add_argument("--name", required=True)
    ap.add_argument("--author", default="")
    ap.add_argument("--license", default="Apache-2.0")
    ap.add_argument("--ref", default="")
    ap.add_argument("--out-dir", default=str(ROOT / "data" / "snapshot"))
    a = ap.parse_args()
    cands = [c for c in decode_all(a.file) if "data" in c]
    print(f"{a.file}: {len(cands)} decodable blobs")
    for i, c in enumerate(cands):
        print(f"  blob {i} @{c['start']}: routes {c['routes']} actions {c['actions']} "
              f"ids {c['route_ids'][:6]}... lens {c['route_lens']} maxstep {c['max_step']} "
              f"sha {c['blob_sha256']}")
    if not cands:
        raise SystemExit("no decodable blob")
    # the LAST definition in the file is the one the module ends up using
    chosen = cands[-1]
    d = Path(a.out_dir)
    d.mkdir(parents=True, exist_ok=True)
    header = {
        "name": a.name, "source_file": str(Path(a.file).resolve()),
        "author": a.author, "license": a.license, "ref": a.ref,
        "extracted_by": "scripts/extract_snapshot.py",
        "blob_sha256": chosen["blob_sha256"], "blob_chars": chosen["blob_chars"],
        "routes": chosen["routes"], "actions": chosen["actions"],
        "route_ids": chosen["route_ids"], "route_lens": chosen["route_lens"],
        "max_step": chosen["max_step"], "keys": chosen["keys"],
    }
    (d / f"{a.name}.json").write_text(json.dumps({"header": header, **chosen["data"]}))
    (d / f"{a.name}.blob.txt").write_text(chosen["blob"])
    print(f"wrote {d / (a.name + '.json')} and .blob.txt (blob {chosen['blob_chars']:,} chars)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
