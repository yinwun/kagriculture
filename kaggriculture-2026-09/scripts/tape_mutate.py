#!/usr/bin/env python
"""Tape mutation tool for V42-family agents.

The agent embeds one blob: {actions: [3982 shared action dicts],
routes: {route_id: [719 indices]}, shops: [{shops:[a,b], route:id}]}.

Because routes share the action library, editing an action in place would change
every route that references it. Safe mutation therefore means: APPEND a new
action to the library and repoint only the chosen route's steps at it.

Usage:
  python scripts/tape_mutate.py --list                 # route usage stats
  python scripts/tape_mutate.py --roundtrip            # verify no-op rebuild == baseline
  python scripts/tape_mutate.py --route 105 --step 300 --action '{"farmer":["PASS"],"hands":[],"market":[["SELL","WHEAT",5]]}' --out DIR
"""
import argparse
import base64
import copy
import hashlib
import json
import re
import zlib
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
BASE = ROOT / "data" / "v42clamp" / "main.py"
BLOB_RE = re.compile(r"b85decode\('([^']+)'\)")


def load(base=BASE):
    src = Path(base).read_text()
    m = BLOB_RE.search(src)
    blob_text = m.group(1)
    data = json.loads(zlib.decompress(base64.b85decode(blob_text)))
    return src, m, data


def dump_blob(data):
    raw = zlib.compress(json.dumps(data, separators=(",", ":")).encode(), 9)
    return base64.b85encode(raw).decode()


def rebuild(src, m, data):
    return src[: m.start(1)] + dump_blob(data) + src[m.end(1):]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--base", default=str(BASE))
    ap.add_argument("--list", action="store_true")
    ap.add_argument("--roundtrip", action="store_true")
    ap.add_argument("--route", type=int)
    ap.add_argument("--step", type=int)
    ap.add_argument("--action", type=str, help="JSON action dict to place")
    ap.add_argument("--out")
    args = ap.parse_args()

    src, m, data = load(args.base)
    routes, actions, shops = data["routes"], data["actions"], data["shops"]

    if args.list:
        use = Counter(r["route"] for r in shops)
        print(f"routes={len(routes)} actions={len(actions)} shops={len(shops)}")
        print(f"{'route':>6} {'#shops':>7}")
        for rid, n in use.most_common(12):
            print(f"{rid:>6} {n:>7}")
        return

    if args.roundtrip:
        out = rebuild(src, m, copy.deepcopy(data))
        same = out == src
        print(f"no-op rebuild identical to baseline: {same}")
        if not same:
            d = [i for i, (a, b) in enumerate(zip(src.splitlines(), out.splitlines())) if a != b]
            print("differing lines:", d[:5])
            print("baseline blob bytes:", len(m.group(1)), " rebuilt:", len(dump_blob(data)))
        return

    assert args.route is not None and args.step is not None and args.action and args.out
    rid = str(args.route)
    assert rid in routes, f"route {rid} not found"
    new_action = json.loads(args.action)
    actions.append(new_action)
    new_index = len(actions) - 1
    old_index = routes[rid][args.step]
    routes[rid][args.step] = new_index
    out_src = rebuild(src, m, data)
    d = Path(args.out)
    d.mkdir(parents=True, exist_ok=True)
    (d / "main.py").write_text(out_src)
    print(f"route {rid} step {args.step}: action {old_index} -> {new_index} (appended)")
    print(f"wrote {d / 'main.py'} ({len(out_src):,} bytes)")


if __name__ == "__main__":
    main()
