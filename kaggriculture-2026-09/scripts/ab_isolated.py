#!/usr/bin/env python
"""Run A/B games with one OS process per game (isolates agent global state).

Usage:
  python scripts/ab_isolated.py A/main.py B/main.py --seeds 6
"""
import argparse
import json
import os
import subprocess
import sys
import statistics

GAME = r"""
import json, sys
from kaggle_environments import make
a, b, seed = sys.argv[1], sys.argv[2], int(sys.argv[3])
env = make("kaggriculture", configuration={"episodeSteps": 720, "seed": seed})
env.run([a, b])
f = env.steps[-1]
print(json.dumps({"a": f[0]["reward"], "b": f[1]["reward"],
                  "sa": f[0]["status"], "sb": f[1]["status"]}))
"""


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("agent_a")
    ap.add_argument("agent_b")
    ap.add_argument("--seeds", type=int, default=6)
    ap.add_argument("--start", type=int, default=500)
    args = ap.parse_args()

    A, B = os.path.abspath(args.agent_a), os.path.abspath(args.agent_b)
    aw = bw = t = 0
    diffs = []
    for i in range(args.seeds):
        seed = args.start + i
        out = subprocess.run([sys.executable, "-c", GAME, A, B, str(seed)],
                             capture_output=True, text=True)
        if out.returncode != 0:
            print(f"  seed {seed}: FAILED {out.stderr.strip().splitlines()[-1][:80]}")
            continue
        r = json.loads(out.stdout.strip().splitlines()[-1])
        aw += r["a"] > r["b"]
        bw += r["b"] > r["a"]
        t += r["a"] == r["b"]
        diffs.append(r["a"] - r["b"])
        print(f"  seed {seed}: A={r['a']:>9,.0f} B={r['b']:>9,.0f} "
              f"{'A' if r['a'] > r['b'] else 'B' if r['b'] > r['a'] else 'tie'}")
    print(f"\n{os.path.basename(os.path.dirname(A))} wins {aw}/{args.seeds}, "
          f"{os.path.basename(os.path.dirname(B))} wins {bw}, ties {t}")
    if diffs:
        print(f"mean bank diff A-B = {statistics.mean(diffs):+,.0f}")


if __name__ == "__main__":
    main()
