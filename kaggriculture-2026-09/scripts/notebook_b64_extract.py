#!/usr/bin/env python
"""Decode an agent embedded as a long base64 payload inside a .ipynb (no notebook execution).

Shapes seen in the wild, all handled: raw base64 of the .py source, gzip(.py),
gzip(tar with main.py + LICENSE/NOTICE), zlib(.py).  Verifies EXPECTED_MAIN_SHA256 /
"SHA-256:" when the notebook declares one, and reports the route blob sha256 and opening
constants so provenance is checkable before any build.

Usage: python scripts/notebook_b64_extract.py data/cand/x.ipynb [...]
"""
import argparse, base64, gzip, hashlib, io, json, re, sys, tarfile, zlib
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from notebook_extract import BLOB, CHAMPION_BLOB_SHA  # noqa: E402

LONG = re.compile(r"[A-Za-z0-9+/=\n]{100000,}")
PY_HEADS = (b"#", b"import", b"from", b'"""', b"'''", b"@", b"def ")


def _py(blob):
    # startswith, not a 4-byte equality: real heads are b"# Kaggriculture ..." etc.
    return blob.lstrip().startswith(PY_HEADS)


def decode_payload(data):
    stages = [("raw", data)]
    for dec, name in ((gzip.decompress, "gzip"), (zlib.decompress, "zlib")):
        try:
            stages.append((name, dec(data)))
        except Exception:
            pass
    for name, blob in list(stages):
        if blob[:2] == b"\x1f\x8b":
            try:
                stages.append((name + "+gz", gzip.decompress(blob)))
            except Exception:
                pass
        try:
            t = tarfile.open(fileobj=io.BytesIO(blob))
            names = t.getnames()
            member = "main.py" if "main.py" in names else next((x for x in names if x.endswith(".py")), None)
            if member:
                stages.append((name + "+tar", t.extractfile(member).read()))
        except Exception:
            pass
    for name, blob in stages:
        if _py(blob):
            return blob, name
    return None


def extract(nb_path):
    nb = json.loads(Path(nb_path).read_text())
    txt = "\n".join("".join(c.get("source") or []) for c in nb.get("cells", []))
    m = (re.search(r"EXPECTED_MAIN_SHA256\s*[=:]\s*['\"]?([0-9a-f]{16,64})", txt)
         or re.search(r"SHA-256:\s*([0-9a-f]{16,64})", txt))
    expected = m.group(1) if m else None
    for cand in sorted(set(LONG.findall(txt)), key=len, reverse=True):
        raw = re.sub(r"\s+", "", cand)
        try:
            data = base64.b64decode(raw + "=" * (-len(raw) % 4))
        except Exception:
            continue
        got = decode_payload(data)
        if got:
            return got, expected
    return None, expected


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("notebooks", nargs="+")
    ap.add_argument("--out-dir", default="data/cand")
    args = ap.parse_args()
    for nb in args.notebooks:
        p = Path(nb)
        got, expected = extract(p)
        if got is None:
            print(f"[{p.stem}] no decodable .py payload"); continue
        out, enc = got
        src = out.decode("utf-8", "replace")
        sha = hashlib.sha256(src.encode()).hexdigest()
        dest = Path(args.out_dir) / f"{p.stem}-extracted-main.py"
        dest.write_text(src)
        bs = [hashlib.sha256(b.encode()).hexdigest()[:16] for b in BLOB.findall(src)]
        ops = re.findall(r"^(_?\w*OPENING\w*)\s*=\s*(\[[^\n]{0,100})", src, re.M)
        ok = ("expected matches" if expected and sha.startswith(expected[:16])
              else (f"DECLARED {expected[:16]}" if expected else "no declared hash"))
        print(f"[{p.stem}] {enc} chars {len(src):,} sha256 {sha[:16]} ({ok})")
        print(f"    route blobs: {[b + ('=OURS' if b == CHAMPION_BLOB_SHA else '') for b in bs] or 'none (plain source)'}")
        for n, v in ops[:2]:
            print(f"    {n} = {v[:100]}")
        try:
            compile(src, str(dest), "exec"); print("    compile OK")
        except SyntaxError as exc:
            print(f"    compile FAIL {exc}")


if __name__ == "__main__":
    main()
