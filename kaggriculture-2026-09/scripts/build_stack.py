#!/usr/bin/env python
"""Stack the herd patch on top of a built race variant (for the additivity test).

Reads a `data/race/<base>/main.py`, appends the herd-swap patch from
`scripts/build_herd.py`, and forces the herd settings by updating the chassis cfg
at import time (the base file's `_SETTINGS` anchor is already consumed by the race
builder, so the settings cannot be injected textually).

Usage: python scripts/build_stack.py --base outer_prem --herd g2s
"""
import argparse
import hashlib
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))
import build_herd  # noqa: E402


def build(base, herd_name, name, out_root=None):
    src = (ROOT / "data" / "race" / base / "main.py").read_text()
    settings = build_herd.VARIANTS[herd_name]
    patch = build_herd.PATCH.replace(
        "_HERD_REPORT = _herd_swap_routes(_IMPL.chassis.routes, _IMPL.chassis.cfg)",
        "_IMPL.chassis.cfg.update(%r)\n"
        "_HERD_REPORT = _herd_swap_routes(_IMPL.chassis.routes, _IMPL.chassis.cfg)"
        % (settings,))
    out = src.rstrip("\n") + "\n" + patch
    compile(out, "stack_main.py", "exec")
    root = Path(out_root) if out_root else ROOT / "data" / "herd"
    d = root / name
    d.mkdir(parents=True, exist_ok=True)
    (d / "main.py").write_text(out)
    print(f"built {d / 'main.py'} sha256 {hashlib.sha256(out.encode()).hexdigest()[:12]} "
          f"base={base} herd={herd_name} {settings}")
    return d / "main.py"


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--base", default="outer_prem")
    ap.add_argument("--herd", default="g2s")
    ap.add_argument("--name", default=None)
    a = ap.parse_args()
    build(a.base, a.herd, a.name or f"stack_{a.herd}_{a.base}")
