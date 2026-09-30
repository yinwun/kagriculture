#!/usr/bin/env python
"""Record a *layered* agent's game into a new tape route.

Motivation (measured): adding a work layer on top of a frozen tape loses money
because the layer acts on a state that has already diverged from the one the tape
was recorded in (sweep delta -1.5k..-5.5k on 200 towns).  But the layer's extra
work is exactly what the coverage audit says is missing (rank-1 waters ~1.0 of its
plants per day, the tape waters ~0.75).

So bake the layer into a new tape instead of bolting it on at run time: play the
layered agent for one full game, record its 719 actions, and graft them as a new
route.  The recorded tape is self-consistent by construction -- the layer's waters
are in the tape at the steps where they happened, and the rest of the choreography
was recorded *with* them, so nothing clashes.

Usage:
  python scripts/record_layered.py \
      --agent data/tapeopt/sweep/main.py --opp data/tapeopt/rgcs/main.py \
      --base data/tapeopt/rgcs/main.py --seed 900 --out data/tapeopt/layered
"""
import argparse
import base64
import json
import re
import zlib
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
NEW_ROUTE = 200


def load_base(path):
    src = Path(path).read_text()
    m = re.search(r"b85decode\('([^']+)'\)", src)
    data = json.loads(zlib.decompress(base64.b85decode(m.group(1))))
    return src, m, data


def dump_blob(data):
    return base64.b85encode(zlib.compress(
        json.dumps(data, separators=(",", ":")).encode(), 9)).decode()


def build_agent(path):
    ns = {"__name__": "rec_mod"}
    exec(compile(Path(path).read_text(), str(path), "exec"), ns)
    return ns["agent"]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--agent", default=str(ROOT / "data" / "tapeopt" / "sweep" / "main.py"))
    ap.add_argument("--opp", default=str(ROOT / "data" / "tapeopt" / "rgcs" / "main.py"))
    ap.add_argument("--base", default=str(ROOT / "data" / "tapeopt" / "rgcs" / "main.py"))
    ap.add_argument("--seed", type=int, default=900)
    ap.add_argument("--out", default=str(ROOT / "data" / "tapeopt" / "layered"))
    args = ap.parse_args()

    from kaggle_environments import make
    cand = build_agent(args.agent)
    opp = build_agent(args.opp)

    def seat0(obs, configuration=None):
        return cand(obs, configuration)

    def seat1(obs, configuration=None):
        return opp(obs, configuration)

    env = make("kaggriculture", configuration={"episodeSteps": 720, "seed": args.seed})
    env.run([seat0, seat1])
    steps = env.steps
    tape, verbs = [], {}
    for t in range(len(steps)):
        a = steps[t][0].action or {}
        rec = {"farmer": list(a.get("farmer") or ["PASS"]),
               "hands": [list(h) for h in (a.get("hands") or [])],
               "market": [list(o) for o in (a.get("market") or [])]}
        tape.append(rec)
        for cmd in [rec["farmer"]] + rec["hands"]:
            if isinstance(cmd, list) and cmd:
                verbs[cmd[0]] = verbs.get(cmd[0], 0) + 1
    reward = steps[-1][0]["reward"]
    print(f"recorded {len(tape)} steps from {Path(args.agent).parent.name} "
          f"(its reward {reward:,.0f}); verbs {dict(sorted(verbs.items(), key=lambda kv: -kv[1])[:10])}")

    src, m, data = load_base(args.base)
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

    out_src = src[:m.start(1)] + dump_blob(data) + src[m.end(1):]
    pat = re.compile(r"def _router\(observation,step,state\):.*?(?=\n_R42_OPENING)", re.S)
    if not pat.search(out_src):
        raise SystemExit("could not find _router to replace")
    out_src = pat.sub(f"def _router(observation,step,state):\n    return {NEW_ROUTE}\n", out_src, count=1)
    d = ROOT / args.out
    d.mkdir(parents=True, exist_ok=True)
    (d / "main.py").write_text(out_src)
    print(f"grafted as route {NEW_ROUTE}; wrote {d / 'main.py'} ({len(out_src):,} bytes)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
