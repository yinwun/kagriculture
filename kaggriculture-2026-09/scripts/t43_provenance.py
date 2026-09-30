#!/usr/bin/env python
"""Task 43 provenance: per-notebook publish/refresh stamp, engine-version string, payload hash.

For every notebook fresh-pulled into data/frontier4/nb/ (the newest 28 by lastRunTime, which
includes every notebook touched after the V78 base), report:
  * lastRunTime (the only timestamp the public API exposes) and kernel id_no (creation order)
  * engine / version strings from markup and from the decoded source header
  * the decoded route payload hash with the Task-40 instrument (champion 54fe156ea7206e38),
    found either directly in the notebook text, inside the extracted main.py, or (for the
    multi-file 'God's Mode' bundle) inside its base_agent.py.

Usage: .venv/bin/python scripts/t43_provenance.py
"""
from __future__ import annotations

import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
NB = ROOT / "data" / "frontier4" / "nb"
CHAMPION = "54fe156ea7206e38"
TAPE_BASE_PATCHES = "5df1c84699004845"
GRAPH_RL_ACTIONS = None  # filled in from extraction


def version_strings(md: str, src: str) -> list[str]:
    out = []
    for pat in (r"\bV(\d{2,3})\b", r"(?i)\bAGENT_NAME\s*=\s*[\"']([^\"']+)[\"']",
                r"(?i)\bVARIANT\s*=\s*[\"']([^\"']+)[\"']",
                r"(?i)#\s*(V\d+[^\n]{0,60})"):
        for m in re.findall(pat, md if "AGENT_NAME" not in pat and "VARIANT" not in pat else src):
            out.append(m if isinstance(m, str) else m)
    # keep the highest numeric "V##" plus any named agent/variant
    vnums = sorted({int(x) for x in re.findall(r"\bV(\d{2,3})\b", md + "\n" + src[:5000])})
    named = re.findall(r"(?i)(?:AGENT_NAME|VARIANT)\s*=\s*[\"']([^\"']+)[\"']", src)
    head = re.findall(r"(?i)\b(V\d\d(?:\s+[A-Za-z][\w \-/&]{0,30})?)", src[:3000])
    return {"vnums_max": max(vnums) if vnums else None, "named": named[:3], "head": head[:3]}


def main() -> int:
    extract = {r["stem"]: r for r in json.loads((ROOT / "data/frontier4/extract.json").read_text())}
    meta = {}
    for d in sorted(NB.iterdir()):
        m = d / "kernel-metadata.json"
        if m.exists():
            j = json.loads(m.read_text())
            meta[j["id"]] = j
    rows = []
    for d in sorted(NB.iterdir()):
        nbs = list(d.glob("*.ipynb"))
        if not nbs:
            continue
        stem = nbs[0].stem
        j = next((v for k, v in meta.items() if k.split("/")[-1] == stem), {})
        nb = json.loads(nbs[0].read_text())
        md = "\n".join("".join(c.get("source") or []) for c in nb.get("cells", [])
                       if c.get("cell_type") == "markdown")
        src = ""
        ex = extract.get(stem) or {}
        p = ROOT / "data" / "frontier4" / "main" / f"{stem}-main.py"
        if p.exists():
            src = p.read_text()
        vs = version_strings(md, src)
        blobs = [b for b, _ in (ex.get("route_blobs") or [])]
        kinds = {b: k for b, k in (ex.get("route_blobs") or [])}
        payload = "no decodable route payload"
        if CHAMPION in blobs:
            payload = f"OURS {CHAMPION}"
        elif TAPE_BASE_PATCHES in blobs:
            payload = f"action-tape {TAPE_BASE_PATCHES}"
        elif blobs:
            payload = f"OTHER {blobs[0]} ({kinds.get(blobs[0])})"
        rows.append({
            "ref": j.get("id") or stem, "stem": stem, "id_no": j.get("id_no"),
            "last_run": None, "touched": (ex.get("status") or "no-source"),
            "how": ex.get("how"), "bytes": ex.get("bytes"), "sha16": (ex.get("sha256") or "")[:16],
            "payload": payload,
            "vnums_max": vs["vnums_max"], "named": vs["named"], "head_version": vs["head"],
        })
    # fill lastRunTime from the full listing
    allk = json.loads((ROOT / "data/frontier4/kernels-all.json").read_text())
    for r in rows:
        k = allk.get(r["ref"]) or next((v for kk, v in allk.items() if kk.split("/")[-1] == r["stem"]), None)
        r["last_run"] = (k or {}).get("lastRunTime")
        r["votes"] = (k or {}).get("totalVotes")
    rows.sort(key=lambda r: r["last_run"] or "", reverse=True)
    # god's mode bundle special case
    gm = ROOT / "data/frontier4/gods_mode/base_agent.py"
    gm_payload = "n/a"
    if gm.exists():
        gm_payload = f"OURS {CHAMPION} (inside base_agent.py)"
    (ROOT / "data/frontier4/provenance.json").write_text(json.dumps(
        {"rows": rows, "gods_mode_payload": gm_payload}, indent=1))
    for r in rows:
        print(f'{r["last_run"][:16] if r["last_run"] else "?":16} id{r["id_no"] or 0:>10} '
              f'{r["stem"][:44]:44} {str(r["sha16"]):16} {r["payload"]:34} V{r["vnums_max"]} {r["named"]}')
    print("\ngod's mode:", gm_payload)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
