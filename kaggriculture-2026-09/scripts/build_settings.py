#!/usr/bin/env python
"""Build a champion variant with extra _SETTINGS switches flipped on.

The layer switches were the only knobs where this family ever showed a measured
gain (room_guard+clamp_sells = +463, t=10.2 over 1,500 games), and the earlier
sweep covered only single switches and pairs.  This builder makes the leftover
combinations cheap to test under the paired protocol.

Usage:
  python scripts/build_settings.py --set terminal_liquidation=True --out data/tapeopt/rgcs_tl/main.py
  python scripts/build_settings.py --set dead_stock=True --set budget_guard=True --out ...
"""
import argparse
import hashlib
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
CHAMPION = ROOT / "data" / "tapeopt" / "rgcs" / "main.py"


def build(out, settings):
    src = CHAMPION.read_text()
    old = "'front_run': False}"
    assert src.count(old) == 1, "settings anchor not unique"
    extra = "".join(f", {k!r}: {v}" for k, v in settings.items())
    src = src.replace(old, "'front_run': False" + extra + "}", 1)
    out = Path(out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(src)
    print(f"wrote {out} ({len(src):,} bytes, sha256 {hashlib.sha256(src.encode()).hexdigest()[:12]}) "
          f"settings={settings}")
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--set", action="append", default=[], help="key=True")
    ap.add_argument("--out", required=True)
    args = ap.parse_args()
    settings = {}
    for item in args.set:
        k, _, v = item.partition("=")
        if v in ("True", "False"):
            settings[k] = v == "True"
        else:
            try:
                settings[k] = int(v)
            except ValueError:
                settings[k] = v
    build(args.out, settings)
    return 0


if __name__ == "__main__":
    sys.exit(main())
