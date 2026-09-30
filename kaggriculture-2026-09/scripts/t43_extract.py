#!/usr/bin/env python
"""Task 43: extract runnable main.py + decoded route-payload hash from any pulled .ipynb.

Handles every payload shape seen on the kaggriculture frontier:
  1. `%%writefile main.py` cells (optionally several, concatenated)
  2. a single cell that defines `agent(`
  3. a long base64 blob of full source / gzip / tar (delegates to notebook_b64_extract)
  4. `FILES = {"main.py": "<base85>", ...}` dicts (base85 of source, zlib, or gzip)
Also reports the decoded route-table sha256 (the Task-40 provenance instrument,
champion blob 54fe156ea7206e38) and any engine version strings from markup.

Usage: .venv/bin/python scripts/t43_extract.py data/frontier4/nb/*/*.ipynb
"""
from __future__ import annotations

import argparse
import ast
import base64
import gzip
import hashlib
import io
import json
import lzma
import re
import sys
import tarfile
import zlib
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from notebook_extract import BLOB, CHAMPION_BLOB_SHA  # noqa: E402
from notebook_b64_extract import decode_payload, LONG  # noqa: E402

PY_HEADS = (b"#", b"import", b"from", b'"""', b"'''", b"@", b"def ")
DICT_ENTRY = re.compile(r"(['\"])([A-Za-z0-9_./-]+\.py)\1\s*:\s*(['\"])([A-Za-z0-9!#$%&()*+\-;<=>?@^_`{|}~ ]{2000,})\3")


def _maybe_unwrap(data: bytes) -> bytes:
    for dec in (zlib.decompress, gzip.decompress):
        try:
            return dec(data)
        except Exception:
            pass
    try:
        t = tarfile.open(fileobj=io.BytesIO(data))
        names = t.getnames()
        member = "main.py" if "main.py" in names else next((x for x in names if x.endswith(".py")), None)
        if member:
            return t.extractfile(member).read()
    except Exception:
        pass
    return data


def _is_py(data: bytes) -> bool:
    return data.lstrip().startswith(PY_HEADS)


def route_hashes(src: str) -> list[tuple[str, str]]:
    out = []
    for b in BLOB.findall(src):
        sha = hashlib.sha256(b.encode()).hexdigest()[:16]
        try:
            d = json.loads(zlib.decompress(base64.b85decode(b)))
            kind = f"ROUTE TABLE routes={len(d.get('routes') or {})} actions={len(d.get('actions') or [])}" \
                if d.get("routes") else f"dict keys={list(d)[:4]}"
        except Exception:
            try:
                d = json.loads(base64.b85decode(b))
                kind = f"ROUTE TABLE routes={len(d.get('routes') or {})} actions={len(d.get('actions') or {})}" \
                    if d.get("routes") else f"dict keys={list(d)[:4]}"
            except Exception as exc:
                kind = f"not-JSON ({type(exc).__name__})"
        out.append((sha, kind))
    return out


def embedded_blob_hashes(src: str) -> list[str]:
    """route blobs hidden inside a decoded payload (double-encoded notebooks)."""
    return sorted({hashlib.sha256(b.encode()).hexdigest()[:16] for b in BLOB.findall(src)})


def writefile_source(nb: dict) -> str | None:
    parts = []
    for c in nb.get("cells", []):
        if c.get("cell_type") != "code":
            continue
        src = "".join(c.get("source") or [])
        first = src.split("\n", 1)[0]
        if first.startswith("%%writefile"):
            body = src.split("\n", 1)[1] if "\n" in src else ""
            if first.split()[-1].endswith(".py") and not first.split()[-1].startswith("test"):
                parts.append(body)
    return "\n".join(parts) if parts else None


def agent_cell_source(nb: dict) -> str | None:
    for c in nb.get("cells", []):
        if c.get("cell_type") != "code":
            continue
        src = "".join(c.get("source") or [])
        if "def agent(" in src:
            return src
    return None


def dict_payload_source(nb: dict) -> tuple[str | None, str | None]:
    """FILES = {...base85...} pattern: return (main source, file name)."""
    txt = "\n".join("".join(c.get("source") or []) for c in nb.get("cells", []))
    for m in DICT_ENTRY.finditer(txt):
        name, blob = m.group(2), m.group(4)
        if name != "main.py":
            continue
        raw = base64.b85decode(re.sub(r"\s+", "", blob))
        data = _maybe_unwrap(raw)
        if _is_py(data):
            return data.decode("utf-8", "replace"), name
    return None, None


PAYLOAD_VAR = re.compile(r"(?i)(payload|archive|blob|b85|b64|source|agent|main)")


def _unwrap_any(raw: bytes) -> bytes:
    """Try every container seen in the wild; return the first that yields .py source or a tar."""
    def is_tar(b: bytes):
        try:
            return tarfile.open(fileobj=io.BytesIO(b))
        except Exception:
            return None
    if is_tar(raw):
        return raw
    for dec in (lzma.decompress, zlib.decompress, gzip.decompress,
                lambda b: lzma.decompress(b, format=lzma.FORMAT_ALONE),
                lambda b: zlib.decompress(b, -15), lambda b: zlib.decompress(b, 47)):
        try:
            out = dec(raw)
        except Exception:
            continue
        if is_tar(out) or _is_py(out):
            return out
    return raw


def _from_container(data: bytes) -> bytes | None:
    t = None
    try:
        t = tarfile.open(fileobj=io.BytesIO(data))
    except Exception:
        pass
    if t is not None:
        names = t.getnames()
        member = "main.py" if "main.py" in names else next((x for x in names if x.endswith(".py")), None)
        if member:
            return t.extractfile(member).read()
    return data if _is_py(data) else None


def joined_payload_source(nb: dict) -> tuple[str | None, str | None]:
    """Payloads assembled across cells: `X = ''.join((...))`, `X = '...'`, `X.append('...')`.

    Catches the two shapes t40 and the first pass of this tool missed:
    `MAIN_BLOB = ''.join(('chunk', 'chunk', ...))` and
    `ARCHIVE_PARTS = []` + `ARCHIVE_PARTS.append('chunk')` in later cells.
    """
    parts: dict[str, list[str]] = {}
    order: list[str] = []
    for c in nb.get("cells", []):
        if c.get("cell_type") != "code":
            continue
        try:
            tree = ast.parse("".join(c.get("source") or []))
        except SyntaxError:
            continue

        def add(name: str, s: str):
            if name not in parts:
                parts[name] = []
                order.append(name)
            parts[name].append(s)

        for node in tree.body:
            if isinstance(node, ast.Assign) and len(node.targets) == 1 and isinstance(node.targets[0], ast.Name):
                name, val = node.targets[0].id, node.value
                if isinstance(val, ast.Constant) and isinstance(val.value, str):
                    parts[name] = [val.value]
                    if name not in order:
                        order.append(name)
                elif isinstance(val, ast.Call):
                    strs = [a.value for a in ast.walk(val)
                            if isinstance(a, ast.Constant) and isinstance(a.value, str)]
                    if strs and isinstance(val.func, ast.Attribute) and val.func.attr == "join":
                        parts[name] = strs
                        if name not in order:
                            order.append(name)
                elif isinstance(val, ast.Name) and val.id in parts:
                    parts[name] = list(parts[val.id])
                    if name not in order:
                        order.append(name)
            elif isinstance(node, ast.Expr) and isinstance(node.value, ast.Call):
                call = node.value
                if (isinstance(call.func, ast.Attribute) and call.func.attr in ("append", "extend", "add")
                        and isinstance(call.func.value, ast.Name) and call.args):
                    arg = call.args[0]
                    if isinstance(arg, ast.Constant) and isinstance(arg.value, str):
                        add(call.func.value.id, arg.value)
                    elif isinstance(arg, (ast.Tuple, ast.List)):
                        for e in arg.elts:
                            if isinstance(e, ast.Constant) and isinstance(e.value, str):
                                add(call.func.value.id, e.value)
            elif isinstance(node, ast.AugAssign) and isinstance(node.target, ast.Name):
                if isinstance(node.value, ast.Constant) and isinstance(node.value.value, str):
                    add(node.target.id, node.value.value)
    for name in order:
        s = "".join(parts[name])
        if len(s) < 3000:
            continue
        body = re.sub(r"\s+", "", s)
        for enc, dec in (("b85", base64.b85decode), ("a85", base64.a85decode), ("b64", base64.b64decode)):
            try:
                raw = dec(body + "=" * (-len(body) % 4) if enc == "b64" else body)
            except Exception:
                continue
            got = _from_container(_unwrap_any(raw))
            if got:
                return got.decode("utf-8", "replace"), f"joined:{name}:{enc}"
    return None, None


def string_payload_source(nb: dict) -> tuple[str | None, str | None, str | None]:
    """Decode a payload stored as a (possibly implicit-concatenated) Python string literal.

    Covers `PAYLOAD_B85 = (...)`, `ARCHIVE_B85 = \"\"\"...\"\"\"`, `_PAYLOAD = (...)` etc.
    Returns (source, how, declared_sha256).
    """
    declared = None
    for c in nb.get("cells", []):
        if c.get("cell_type") != "code":
            continue
        src = "".join(c.get("source") or [])
        try:
            tree = ast.parse(src)
        except SyntaxError:
            continue
        consts: list[tuple[str, str]] = []
        for node in ast.walk(tree):
            if isinstance(node, ast.Assign):
                for tgt in node.targets:
                    name = tgt.id if isinstance(tgt, ast.Name) else None
                    if not name:
                        continue
                    val = node.value
                    if isinstance(val, ast.Constant) and isinstance(val.value, str):
                        consts.append((name, val.value))
                    elif isinstance(val, ast.JoinedStr):
                        continue
        for m in re.finditer(r"EXPECTED_(?:MAIN_)?SHA256\s*=\s*['\"]([0-9a-f]{64})['\"]", src):
            declared = m.group(1)
        for name, s in consts:
            if len(s) < 3000:
                continue
            if not PAYLOAD_VAR.search(name) and not any(
                    k in name.upper() for k in ("PAYLOAD", "ARCHIVE", "SOURCE", "AGENT", "BLOB", "MAIN", "DATA", "B85", "B64")):
                continue
            body = re.sub(r"\s+", "", s)
            for enc, dec in (("b85", base64.b85decode), ("a85", base64.a85decode),
                             ("b64", base64.b64decode)):
                try:
                    raw = dec(body + "=" * (-len(body) % 4) if enc == "b64" else body)
                except Exception:
                    continue
                got = _from_container(_unwrap_any(raw))
                if got:
                    return got.decode("utf-8", "replace"), f"str:{name}:{enc}", declared
    return None, None, declared


def analyse(path: Path, out_dir: Path) -> dict:
    nb = json.loads(path.read_text())
    cells = nb.get("cells", [])
    txt = "\n".join("".join(c.get("source") or []) for c in cells)
    md = "\n".join("".join(c.get("source") or []) for c in cells if c.get("cell_type") == "markdown")
    rec: dict = {"notebook": str(path), "stem": path.stem,
                 "chars": len(txt), "vnums_md": sorted(set(re.findall(r"[Vv](\d{2,3})\b", md)))}
    src = None
    how = None
    src = writefile_source(nb)
    if src:
        how = "writefile"
    if not src:
        src, how = dict_payload_source(nb)
    if not src:
        src, how, declared = string_payload_source(nb)
        if src:
            rec["declared_sha256"] = declared
    if not src:
        src, how = joined_payload_source(nb)
    if not src:
        got, expected = None, None
        for cand in sorted(set(LONG.findall(txt)), key=len, reverse=True):
            raw = re.sub(r"\s+", "", cand)
            try:
                data = base64.b64decode(raw + "=" * (-len(raw) % 4))
            except Exception:
                continue
            got = decode_payload(data)
            if got:
                break
        if got:
            src = got[0].decode("utf-8", "replace")
            how = "b64:" + got[1]
    if not src:
        src = agent_cell_source(nb)
        if src:
            how = "agent-cell"
    rec["how"] = how
    if not src:
        rec["status"] = "no-runnable-source"
        return rec
    dest = out_dir / f"{path.stem}-main.py"
    dest.write_text(src)
    rec["out"] = str(dest)
    rec["bytes"] = len(src)
    rec["sha256"] = hashlib.sha256(src.encode()).hexdigest()
    dec = rec.get("declared_sha256")
    if dec:
        rec["declared_match"] = rec["sha256"].startswith(dec[:16]) or dec.startswith(rec["sha256"][:16])
    try:
        compile(src, str(dest), "exec")
        rec["compile"] = "OK"
    except SyntaxError as exc:
        rec["compile"] = f"FAIL {exc}"
    rec["route_blobs"] = route_hashes(src)
    rec["embedded_blobs"] = embedded_blob_hashes(src)
    # engine version strings inside the source
    vers = re.findall(r"(?i)\bV(\d{2,3})\b", src[:4000])
    rec["source_vnums_head"] = sorted(set(vers))
    rec["blob_is_ours"] = any(b == CHAMPION_BLOB_SHA for b, _ in rec["route_blobs"]) or \
        CHAMPION_BLOB_SHA in rec["embedded_blobs"]
    rec["status"] = "runnable"
    return rec


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("notebooks", nargs="+")
    ap.add_argument("--out-dir", default="data/frontier4/main")
    ap.add_argument("--json", default="data/frontier4/extract.json")
    a = ap.parse_args()
    out_dir = Path(a.out_dir); out_dir.mkdir(parents=True, exist_ok=True)
    recs = []
    for p in a.notebooks:
        try:
            rec = analyse(Path(p), out_dir)
        except Exception as exc:  # noqa: BLE001
            rec = {"notebook": p, "stem": Path(p).stem, "status": f"ERROR {type(exc).__name__}: {exc}"}
        recs.append(rec)
        blobs = ",".join(b + ("=OURS" if b == CHAMPION_BLOB_SHA else "") for b, _ in rec.get("route_blobs") or []) or "-"
        print(f"{rec['stem'][:48]:48} {rec['status']:22} {rec.get('how') or '-':14} "
              f"{rec.get('bytes', 0):>9,} blobs {blobs} mdV {rec.get('vnums_md')}", flush=True)
    Path(a.json).write_text(json.dumps(recs, indent=1))
    print("wrote", a.json)
    return 0


if __name__ == "__main__":
    sys.exit(main())
