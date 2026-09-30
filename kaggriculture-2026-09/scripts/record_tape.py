#!/usr/bin/env python
"""Record the from-scratch planner's play into a genuine new tape.

The objective asked for a tape written from scratch.  The planner in
scripts/planner.py is that generator: it decides every action from live state,
never reading a recorded tape.  This script runs it for one full game, captures
the 719 action dicts it emitted, and grafts them into our agent blob as a NEW
route (id 200) whose single entry in the library is that recorded plan.  The
result is a tape that no-one has ever played before -- it is produced by our own
planner, not copied from a public notebook.

Usage:
  python scripts/record_tape.py --out data/tapeopt/gen_planner --seed 900
  python scripts/record_tape.py --out ... --opponent <path to main.py>
"""
import argparse
import base64
import copy
import json
import re
import sys
import zlib
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))
BASE = (ROOT / "data" / "league" /
        "ahmedberatozer_kaggriculture-v42-production-that-fits-the-marke" / "main.py")
NEW_ROUTE = 200


def load(path=BASE):
    src = Path(path).read_text()
    m = re.search(r"b85decode\('([^']+)'\)", src)
    data = json.loads(zlib.decompress(base64.b85decode(m.group(1))))
    return src, m, data


def dump(data):
    return base64.b85encode(zlib.compress(
        json.dumps(data, separators=(",", ":")).encode(), 9)).decode()


def record(seed, opponent, cfg):
    from kaggle_environments import make
    from planner import Planner
    planner = Planner(cfg)
    env = make("kaggriculture", configuration={"episodeSteps": 720, "seed": seed})
    other = opponent or Planner(dict(cfg)).act
    env.run([planner.act, other])
    steps = env.steps
    tape = []
    for t in range(len(steps)):
        a = steps[t][0].action or {}
        tape.append({"farmer": list(a.get("farmer") or ["PASS"]),
                     "hands": [list(h) for h in (a.get("hands") or [])],
                     "market": [list(o) for o in (a.get("market") or [])]})
    reward = steps[-1][0]["reward"]
    return tape, reward


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default="data/tapeopt/gen_planner")
    ap.add_argument("--seed", type=int, default=900)
    ap.add_argument("--opponent", default=None)
    ap.add_argument("--quota", default="WHEAT40,CARROT20")
    args = ap.parse_args()
    quota = {}
    for part in args.quota.split(","):
        if not part:
            continue
        i = 0
        while i < len(part) and not part[i].isdigit():
            i += 1
        quota[part[:i]] = int(part[i:])
    cfg = {"quota": quota, "min_hands": 4, "hire_cap": 34, "max_animals": 0}
    tape, reward = record(args.seed, args.opponent, cfg)
    print(f"recorded {len(tape)} steps from the planner (its own reward: {reward:,.0f})")

    src, m, data = load()
    actions, routes = data["actions"], data["routes"]
    index_of = {}
    for i, a in enumerate(actions):
        index_of.setdefault(json.dumps(a, sort_keys=True), i)
    idxs = []
    for a in tape:
        key = json.dumps(a, sort_keys=True)
        if key not in index_of:
            index_of[key] = len(actions)
            actions.append(a)
        idxs.append(index_of[key])
    routes[str(NEW_ROUTE)] = idxs
    data["actions"] = actions

    # force the chassis onto the generated tape: replace the source _router body
    out = src[:m.start(1)] + dump(data) + src[m.end(1):]
    pat = re.compile(r"def _router\(observation,step,state\):.*?(?=\n_R42_OPENING)", re.S)
    if not pat.search(out):
        raise SystemExit("could not find _router to replace")
    out = pat.sub(f"def _router(observation,step,state):\n    return {NEW_ROUTE}\n", out, count=1)
    d = ROOT / args.out
    d.mkdir(parents=True, exist_ok=True)
    (d / "main.py").write_text(out)
    print(f"grafted the generated tape as route {NEW_ROUTE}; wrote {d/'main.py'} "
          f"({len(out):,} bytes)")


if __name__ == "__main__":
    main()
