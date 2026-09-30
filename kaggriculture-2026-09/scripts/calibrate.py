#!/usr/bin/env python
"""Calibration harness: which local metric predicts the ladder?

Every ladder A/B we run produces one new (local metric vector, ladder score)
pair. This script stores those pairs and reports, for each local metric, how
well it ranks the agents by ladder score (Spearman) and how it correlates
(Pearson). As the calibration set grows past ~10 points the answer becomes
usable; until then it is reported as provisional.

Usage:
  python scripts/calibrate.py --add '{"agent": "...", "ladder": 2666.0, "pool_bank": 88000}'
  python scripts/calibrate.py --report
"""
import argparse
import json
import statistics
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
STORE = ROOT / "data" / "calibration.json"

# seed set: ladder outcomes we already know (score while tracked)
SEED = [
    {"agent": "v37base",  "ladder": 2632.1, "note": "v37 baseline"},
    {"agent": "v37clamp", "ladder": 2674.2, "note": "v37 + clamp_sells"},
    {"agent": "v40",      "ladder": 2572.1, "note": "V40"},
    {"agent": "v40clamp", "ladder": 2587.9, "note": "V40 + clamp_sells"},
    {"agent": "fr",       "ladder": 2493.5, "note": "v37+clamp+front_run"},
    {"agent": "frsort",   "ladder": 2242.8, "note": "v37+clamp+front_run+sort"},
]


def load():
    if STORE.exists():
        return json.loads(STORE.read_text())
    return {"points": SEED}


def save(data):
    STORE.parent.mkdir(parents=True, exist_ok=True)
    STORE.write_text(json.dumps(data, indent=1))


def pearson(a, b):
    ma, mb = statistics.mean(a), statistics.mean(b)
    num = sum((x - ma) * (y - mb) for x, y in zip(a, b))
    den = (sum((x - ma) ** 2 for x in a) * sum((y - mb) ** 2 for y in b)) ** 0.5
    return num / den if den else 0.0


def spearman(a, b):
    def rank(v):
        order = sorted(range(len(v)), key=lambda i: v[i])
        r = [0.0] * len(v)
        for pos, i in enumerate(order):
            r[i] = pos
        return r
    return pearson(rank(a), rank(b))


def report(data):
    pts = [p for p in data["points"] if "ladder" in p]
    keys = sorted({k for p in pts for k in p if k not in ("agent", "ladder", "note")})
    n = len(pts)
    print(f"校准集: n={n}{'  (provisional: n<10)' if n < 10 else ''}")
    print(f"{'agent':<12} {'ladder':>8}  " + "  ".join(f"{k:>16}" for k in keys))
    for p in sorted(pts, key=lambda x: -x["ladder"]):
        vals = "  ".join(f"{p.get(k, float('nan')):>16,.3f}" if isinstance(p.get(k), (int, float)) else f"{'-':>16}" for k in keys)
        print(f"{p['agent']:<12} {p['ladder']:>8,.1f}  {vals}")
    if n >= 3:
        print(f"\n{'metric':<20} {'pearson':>9} {'spearman':>9}")
        rows = []
        for k in keys:
            xs = [p[k] for p in pts if isinstance(p.get(k), (int, float))]
            ys = [p["ladder"] for p in pts if isinstance(p.get(k), (int, float))]
            if len(xs) < 3:
                continue
            rows.append((abs(pearson(xs, ys)), k, pearson(xs, ys), spearman(xs, ys)))
        for _, k, r, s in sorted(rows, reverse=True):
            flag = "  <-- 可用" if abs(s) >= 0.8 and n >= 10 else ""
            print(f"{k:<20} {r:>+9.3f} {s:>+9.3f}{flag}")
        need = 0.81
        print(f"\n提示: n={n} 时 Pearson 需 |r|>=~{need:.2f} 才显著;n>=10 后看 spearman。")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--add", type=str, help="JSON object with agent/ladder/metrics")
    ap.add_argument("--report", action="store_true")
    ap.add_argument("--from-pool-eval", type=str, help="merge data/pool_eval.json metrics")
    args = ap.parse_args()

    data = load()
    if args.add:
        p = json.loads(args.add)
        data["points"] = [q for q in data["points"] if q.get("agent") != p.get("agent")] + [p]
        save(data)
        print("added", p.get("agent"))
    if args.from_pool_eval:
        pe = json.loads((ROOT / args.from_pool_eval).read_text())
        for cname, v in pe.get("candidates", {}).items():
            bank = statistics.mean([v["pool_bank_half1"], v["pool_bank_half2"]])
            entry = next((q for q in data["points"] if q.get("agent") == cname), {"agent": cname})
            entry["pool_bank"] = bank
            entry["noise_pct"] = v["split_half_gap_pct"]
            for oname, ov in v["per_opponent"].items():
                entry[f"bank_{oname}"] = ov["bank"]; entry[f"oppbank_{oname}"] = ov["opp_bank"]
            data["points"] = [q for q in data["points"] if q.get("agent") != cname] + [entry]
        save(data)
        print(f"merged {len(pe.get('candidates', {}))} candidates from {args.from_pool_eval}")
    if args.report or not args.add:
        report(data)


if __name__ == "__main__":
    main()
