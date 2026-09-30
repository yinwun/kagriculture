#!/usr/bin/env python
"""Generate ablation variants of a single-file kaggriculture agent.

The agent stores its layer switches in one literal:
    _SETTINGS={'hand_align': True, ..., 'front_run': False}

Each variant flips exactly one switch (or a chosen set) back on, so the change is
a single token. Usage:

    python scripts/make_variants.py <base main.py> <outdir> [flag ...]
    python scripts/make_variants.py <base main.py> <outdir> --all-off-flags
"""
import argparse
import re
import sys
from pathlib import Path

PAT = re.compile(r"_SETTINGS=\{(.*?)\}", re.S)


def parse(src):
    m = PAT.search(src)
    if not m:
        raise SystemExit("no _SETTINGS literal found")
    body = m.group(1)
    items = re.findall(r"'([a-z_]+)':\s*(True|False)", body)
    return m, dict(items)


def render(items):
    return "_SETTINGS={" + ", ".join(f"'{k}': {v}" for k, v in items.items()) + "}"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("base")
    ap.add_argument("outdir")
    ap.add_argument("flags", nargs="*")
    ap.add_argument("--all-off-flags", action="store_true")
    args = ap.parse_args()

    src = Path(args.base).read_text()
    _, items = parse(src)
    off = [k for k, v in items.items() if v == "False"]
    print(f"switches: {items}")
    print(f"currently OFF: {off}")

    targets = off if args.all_off_flags else args.flags
    outdir = Path(args.outdir)
    made = []
    for flag in targets:
        if flag not in items:
            print(f"  !! unknown flag {flag}")
            continue
        new = dict(items)
        new[flag] = "True"
        m = PAT.search(src)
        variant = src[: m.start()] + render(new) + src[m.end():]
        d = outdir / f"on_{flag}"
        d.mkdir(parents=True, exist_ok=True)
        (d / "main.py").write_text(variant)
        assert variant != src
        made.append(str(d / "main.py"))
        print(f"  wrote {d / 'main.py'}")

    if args.all_off_flags and len(off) > 1:
        new = dict(items)
        for k in off:
            new[k] = "True"
        m = PAT.search(src)
        variant = src[: m.start()] + render(new) + src[m.end():]
        d = outdir / "on_ALL"
        d.mkdir(parents=True, exist_ok=True)
        (d / "main.py").write_text(variant)
        made.append(str(d / "main.py"))
        print(f"  wrote {d / 'main.py'}")

    print("\n".join(made))
    return 0


if __name__ == "__main__":
    sys.exit(main())
