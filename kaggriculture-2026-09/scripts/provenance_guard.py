#!/usr/bin/env python
"""Guard: does any notebook published in the last day carry route data OTHER than ours?

For each slug: pull the .ipynb if not cached, then hash every route payload it contains --
base85 blobs found directly in the source, and (for base64/gzip/tar-embedded agents) the
blobs inside the decoded source.  Champion blob = 54fe156ea7206e38.

Usage: python scripts/provenance_guard.py --csv data/notebooks-t29.csv --limit 14
"""
import argparse, base64, csv, hashlib, json, re, subprocess, sys
from pathlib import Path
ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))
from notebook_extract import BLOB, CHAMPION_BLOB_SHA          # noqa: E402
from notebook_b64_extract import LONG, decode_payload          # noqa: E402

def blobs_of(text):
    return [hashlib.sha256(b.encode()).hexdigest()[:16] for b in BLOB.findall(text)]

def guard(nb_path, text):
    """Return the set of route-blob shas visible in this notebook (direct or embedded)."""
    found = set(blobs_of(text))
    for cand in sorted(set(LONG.findall(text)), key=len, reverse=True)[:2]:
        raw = re.sub(r"\s+", "", cand)
        try:
            data = base64.b64decode(raw + "=" * (-len(raw) % 4))
        except Exception:
            continue
        got = decode_payload(data)
        if got:
            found |= set(blobs_of(got[0].decode("utf-8", "replace")))
    return found

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--csv", default=str(ROOT / "data" / "notebooks-t29.csv"))
    ap.add_argument("--limit", type=int, default=14)
    ap.add_argument("--out", default=str(ROOT / "data" / "provenance-guard-t29.json"))
    args = ap.parse_args()
    rows = list(csv.DictReader(open(args.csv)))[: args.limit]
    res = {}
    for r in rows:
        slug = r["ref"]
        dest = ROOT / "data" / "cand" / (slug.split("/")[-1] + ".ipynb")
        if not dest.exists():
            subprocess.run([".venv/bin/python", "-m", "kaggle", "kernels", "pull", slug,
                            "-p", "data/cand"], cwd=ROOT, capture_output=True, text=True)
        if not dest.exists():
            print(f"{slug:58} PULL FAILED"); res[slug] = None; continue
        try:
            nb = json.loads(dest.read_text())
            text = "\n".join("".join(c.get("source") or []) for c in nb.get("cells", []))
        except Exception as exc:
            print(f"{slug:58} PARSE FAIL {exc!r}"); res[slug] = None; continue
        found = guard(dest, text)
        ours = CHAMPION_BLOB_SHA in found
        other = sorted(x for x in found if x != CHAMPION_BLOB_SHA)
        tag = ("OUR BLOB" if ours else "") + (f" + OTHER {other}" if other else "") or "no route blob exposed"
        print(f"{slug:58} {tag}")
        res[slug] = {"blobs": sorted(found), "ours": ours, "other": other}
    Path(args.out).write_text(json.dumps(res, indent=1))
    others = {k: v["other"] for k, v in res.items() if v and v["other"]}
    ours = [k for k, v in res.items() if v and v["ours"]]
    print(f"\ncandidates exposing our blob: {len(ours)}/{len(res)}")
    print(f"candidates exposing a DIFFERENT route blob: {others or 'NONE'}")
    print(f"wrote {args.out}")

if __name__ == "__main__":
    main()
