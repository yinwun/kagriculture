#!/usr/bin/env python
"""Apply the ONLY tape-level difference found between our lineage and the public
frontier build: the step-0 opening market sequence.

Diff of the effective route tapes (`_IMPL.chassis.routes`, task 10):
  our champion / tetsutani : BUY_PRODUCT WHEAT 5, BUY_PRODUCT WHEAT 10, SELL WHEAT 60
  the-2945 frontier        : BUY_PRODUCT WHEAT 13, BUY_PRODUCT WHEAT 30, SELL WHEAT 30
in 41 of 41 routes at exactly one step (step 0); every other step is identical, and the
underlying compressed route data (`_R108_DATA`) is byte-identical in all three files
(sha256 54fe156ea7206e38).  So there is no newer upstream snapshot to extract: this is
the whole extractable plan-data delta.  Applied as an outermost step-0 override on top of
a built base.  Usage: python scripts/build_opening.py --base data/forward/wool_drain1_outerprem/main.py
"""
from __future__ import annotations

import argparse
import hashlib
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

PATCH = '''

# ===========================================================================
# frontier opening (scripts/build_opening.py): the step-0 market sequence of the
# public build thomastschinkel/the-2945-farm-96-vs-the-top-10-public-bots
# (Apache-2.0 lineage data; the only tape-level difference it has from our own
# routes -- see data/snapshot/ and REPORT-snapshot.md).
# ===========================================================================
_OPENING_PARENT = agent
_OPENING_ORDERS = [["BUY_PRODUCT", "WHEAT", 13], ["BUY_PRODUCT", "WHEAT", 30],
                   ["SELL", "WHEAT", 30]]


def _opening_agent(observation, configuration=None):
    result = _OPENING_PARENT(observation, configuration)
    try:
        if int(observation["step"]) == 0 and isinstance(result, dict):
            result = dict(result, market=[list(o) for o in _OPENING_ORDERS])
    except Exception:
        pass
    return result


agent = _opening_agent
agent.telemetry = getattr(_OPENING_PARENT, "telemetry", {})
'''


def build(base, name, out_root=None):
    src = Path(base).read_text()
    assert "_opening_agent" not in src, "base already has an opening override"
    out = src.rstrip("\n") + "\n" + PATCH
    compile(out, "opening_main.py", "exec")
    root = Path(out_root) if out_root else ROOT / "data" / "snapshot"
    d = root / name
    d.mkdir(parents=True, exist_ok=True)
    (d / "main.py").write_text(out)
    print(f"built {d / 'main.py'} sha256 {hashlib.sha256(out.encode()).hexdigest()[:12]} base={base}")
    return d / "main.py"


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--base", default=str(ROOT / "data" / "forward" / "wool_drain1_outerprem" / "main.py"))
    ap.add_argument("--name", default="opening")
    a = ap.parse_args()
    build(a.base, a.name)
