#!/usr/bin/env python
"""Count position-preserving fertilization sites inside a tape.

The tape collects ~377 fertilizer and applies only ~104.  A unit that is
(a) carrying fertilizer, (b) standing on one of our crops that is inside its
effective window and not yet fertilized, and (c) whose tape op for that step is
PASS, can apply FERTILIZE at zero movement cost and without desynchronising the
script (the op does not change the unit's position, so every later relative move
still lands where the tape intended).

This script measures how many such free sites exist before we build anything.

Usage:
  python scripts/tape_fert.py --route 105 --count
  python scripts/tape_fert.py --route 105 --build --out data/tapeopt/fertins
"""
import argparse
import base64
import collections
import copy
import json
import sys
import zlib
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))
from tape_sim2 import load_blob, cmd_of, MOVES  # noqa: E402

CROPS = {"WHEAT": (2, 4), "CARROT": (2, 3), "MELON": (10, 12),
         "TOMATO": (8, 8), "STRAWBERRY": (10, 10)}
ONGOING = ("TOMATO", "STRAWBERRY")


def window_start(max_day):
    return (max_day + 1) // 2


def simulate_with_inventory(tape, nhand):
    """Day-aware simulation that also tracks each unit's fertilizer/wheat carrying."""
    rows = {k: [] for k in range(nhand + 1)}
    live = {}
    for step, a in enumerate(tape):
        if step % 24 == 0:
            live = {0: (4, 4)}
            hired = 0
            inv = {0: collections.Counter()}
        for o in (a.get("market") or []):
            if isinstance(o, list) and o and o[0] == "HIRE":
                hired += 1
                if hired <= nhand:
                    live[hired] = (4, 4)
                    inv[hired] = collections.Counter()
        for k in range(nhand + 1):
            c = cmd_of(a, k)
            pos = live.get(k)
            bag = inv.get(k)
            if pos is None or bag is None:
                rows[k].append((step, None, c, None))
                continue
            if isinstance(c, list) and c:
                op = c[0]
                if op in MOVES:
                    dx, dy = MOVES[op]
                    q = (pos[0] + dx, pos[1] + dy)
                    if 0 <= q[0] < 10 and 0 <= q[1] < 10:
                        live[k] = q
                        pos = q
                elif op == "COLLECT_FERTILIZER":
                    bag["FERTILIZER"] += 1
                elif op == "FERTILIZE":
                    if bag["FERTILIZER"] > 0:
                        bag["FERTILIZER"] -= 1
                elif op == "PICKUP" and len(c) > 2:
                    bag[c[1]] += int(c[2])
                elif op == "DROP":
                    bag.clear()
            rows[k].append((step, pos, c, dict(bag)))
    return rows


def crop_windows(rows, nhand):
    """(pos, start_step, end_step, crop) from PLANT/HARVEST ops."""
    iv = collections.defaultdict(list)
    for k in range(nhand + 1):
        for step, pos, c, _bag in rows[k]:
            if not (isinstance(c, list) and c and pos is not None):
                continue
            if c[0] == "PLANT":
                iv[pos].append([step, None, c[1] if len(c) > 1 else None])
            elif c[0] == "HARVEST":
                for e in reversed(iv.get(pos, [])):
                    if e[1] is None:
                        e[1] = step
                        break
    for pos, lst in iv.items():
        for e in lst:
            if e[1] is None:
                e[1] = 10 ** 9
    return iv


def crop_at(iv, pos, step):
    for s, e, crop in iv.get(pos, ()):
        if s <= step < e:
            return s, e, crop
    return None


def find_sites(tape, nhand):
    """PASS-op steps where the unit already carries fertilizer on an in-window crop."""
    rows = simulate_with_inventory(tape, nhand)
    iv = crop_windows(rows, nhand)
    sites = []
    already = set()
    for k in range(nhand + 1):
        for step, pos, c, bag in rows[k]:
            if pos is None or not bag:
                continue
            if not (isinstance(c, list) and c and c[0] == "PASS"):
                continue
            hit = crop_at(iv, pos, step)
            if hit is None:
                continue
            s, e, crop = hit
            info = CROPS.get(crop)
            if info is None:
                continue
            first, maxd = info
            planted_day = s // 24
            day = step // 24
            age = day - planted_day
            if crop in ONGOING:
                useful = age >= 0          # production every interval; water+fert doubles it
            else:
                useful = window_start(maxd) <= age <= maxd
            if not useful or bag.get("FERTILIZER", 0) <= 0:
                continue
            if (pos, day) in already:
                continue
            already.add((pos, day))
            sites.append((k, step, pos, crop, day, age))
    return sites, rows


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--route", type=int, default=105)
    ap.add_argument("--count", action="store_true")
    ap.add_argument("--build", action="store_true")
    ap.add_argument("--all", action="store_true")
    ap.add_argument("--out", default="data/tapeopt/fertins")
    ap.add_argument("--tape", default=None)
    args = ap.parse_args()
    if args.tape:
        src = Path(args.tape).read_text()
        import re
        blob = re.search(r"b85decode\('([^']+)'\)", src).group(1)
        data = json.loads(zlib.decompress(base64.b85decode(blob)))
        m = re.search(r"b85decode\('([^']+)'\)", src)
    else:
        src, m, data = load_blob()
    routes, acts = data["routes"], data["actions"]
    rids = sorted(int(k) for k in routes) if (args.all or args.build) else [args.route]
    total_sites = 0
    report = []
    for rid in rids:
        tape = [acts[i] for i in routes[str(rid)]]
        nhand = max(len(a.get("hands") or []) for a in tape if isinstance(a, dict))
        sites, _rows = find_sites(tape, nhand)
        by_crop = collections.Counter(s[3] for s in sites)
        total_sites += len(sites)
        if not args.build:
            print(f"route {rid:>3}: {len(sites):4d} free FERTILIZE sites  {dict(by_crop)}")
        if args.build and sites:
            for k, step, pos, crop, day, age in sites:
                a = copy.deepcopy(tape[step])
                if k == 0:
                    a["farmer"] = ["FERTILIZE"]
                else:
                    hands = list(a.get("hands") or [])
                    while len(hands) < k:
                        hands.append(["PASS"])
                    hands[k - 1] = ["FERTILIZE"]
                    a["hands"] = hands
                tape[step] = a
            report.append((rid, len(sites), dict(by_crop)))
    if args.count or not args.build:
        print(f"TOTAL free sites over {len(rids)} routes: {total_sites}")
        return
    # rebuild the blob with the patched routes (copy-on-write into the library)
    index_of = {}
    for i, a in enumerate(acts):
        index_of.setdefault(json.dumps(a, sort_keys=True), i)
    for rid, n, _bc in report:
        tape = [None] * 0
        pass
    # (re-run the patch with dedup so routes point at real indices)
    added = 0
    for rid in rids:
        tape = [acts[i] for i in routes[str(rid)]]
        nhand = max(len(a.get("hands") or []) for a in tape if isinstance(a, dict))
        sites, _rows = find_sites(tape, nhand)
        for k, step, pos, crop, day, age in sites:
            a = copy.deepcopy(tape[step])
            if k == 0:
                a["farmer"] = ["FERTILIZE"]
            else:
                hands = list(a.get("hands") or [])
                while len(hands) < k:
                    hands.append(["PASS"])
                hands[k - 1] = ["FERTILIZE"]
                a["hands"] = hands
            tape[step] = a
        idxs = []
        for a in tape:
            key = json.dumps(a, sort_keys=True)
            if key not in index_of:
                index_of[key] = len(acts)
                acts.append(a)
                added += 1
            idxs.append(index_of[key])
        routes[str(rid)] = idxs
    data["actions"] = acts
    out_src = src[: m.start(1)] + base64.b85encode(zlib.compress(
        json.dumps(data, separators=(",", ":")).encode(), 9)).decode() + src[m.end(1):]
    d = ROOT / args.out
    d.mkdir(parents=True, exist_ok=True)
    (d / "main.py").write_text(out_src)
    print(f"inserted {total_sites} in-place FERTILIZE ops over {len(rids)} routes "
          f"({added} new action dicts); wrote {d/'main.py'} ({len(out_src):,} bytes)")


if __name__ == "__main__":
    main()
