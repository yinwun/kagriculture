#!/usr/bin/env python
"""Diagnose a remote/local kaggriculture run: who played, how much, how fast.

Checks the things that silently break a ported setup:
  * which kaggle-environments version is actually imported;
  * whether the two agents are distinct objects (sharing one instance between
    both seats is the classic aliasing bug and produces near-zero rewards);
  * the action ledger of each seat (so "agent returned nothing" is visible);
  * wall-clock split between import, agent build and the game itself.

Usage:
  python scripts/remote_debug.py --seed 700 [--agent <main.py>] [--repeat 5]
"""
import argparse
import collections
import importlib.util
import json
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
V42 = (ROOT / "data" / "league" /
       "ahmedberatozer_kaggriculture-v42-production-that-fits-the-marke" / "main.py")


def load(path, tag):
    spec = importlib.util.spec_from_file_location(f"agent_{tag}", str(path))
    mod = importlib.util.module_from_spec(spec)
    sys.modules[f"agent_{tag}"] = mod
    spec.loader.exec_module(mod)
    return mod.agent


def ledger(env, player):
    ops = collections.Counter()
    for turn in env.steps:
        a = turn[player].get("action") or {}
        for c in [a.get("farmer")] + list(a.get("hands") or []):
            if isinstance(c, list) and c:
                ops[c[0]] += 1
        for o in (a.get("market") or []):
            if isinstance(o, list) and o:
                ops["MKT:" + o[0]] += 1
    return ops


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--seed", type=int, default=700)
    ap.add_argument("--agent", default=str(V42))
    ap.add_argument("--opponent", default=str(V42))
    ap.add_argument("--repeat", type=int, default=1)
    args = ap.parse_args()

    t0 = time.time()
    import kaggle_environments as ke
    from kaggle_environments import make
    t_import = time.time() - t0
    print(f"kaggle_environments {ke.__version__} from {Path(ke.__file__).parent}")
    print(f"import time {t_import:.1f}s | python {sys.version.split()[0]}")

    t0 = time.time()
    a = load(Path(args.agent), "cand")
    b = load(Path(args.opponent), "opp")
    t_build = time.time() - t0
    print(f"agent build {t_build:.1f}s | distinct objects: {a is not b}")
    print(f"agent modules: {getattr(a, '__module__', '?')} / {getattr(b, '__module__', '?')}")

    for i in range(args.repeat):
        seed = args.seed + i
        t0 = time.time()
        env = make("kaggriculture", configuration={"episodeSteps": 720, "seed": seed})
        env.run([a, b])
        dt = time.time() - t0
        f = env.steps[-1]
        ra, rb = f[0]["reward"], f[1]["reward"]
        la, lb = ledger(env, 0), ledger(env, 1)
        shops = (env.steps[6 * 24][0]["observation"].get("town") or {}).get("unlocked_shops")
        print(f"\nseed {seed}: P0 {ra} [{f[0]['status']}]  P1 {rb} [{f[1]['status']}]  "
              f"game {dt:.1f}s  shops@d6 {shops}")
        for name, lg in (("P0", la), ("P1", lb)):
            top = " ".join(f"{k}:{v}" for k, v in lg.most_common(8))
            print(f"   {name}: total ops {sum(lg.values())} | {top}")


if __name__ == "__main__":
    main()
