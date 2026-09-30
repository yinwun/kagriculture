#!/usr/bin/env python
"""Run A vs B with route-selection + action-ledger probes.

Wraps each agent's Chassis.act so we can see which tape route was actually
replayed per step, plus the real op ledger (WATER/PASS/HARVEST/SELL...) after
every reactive layer has run.

Usage:
  python scripts/probe_run.py A/main.py B/main.py --seeds 8 --start 500
"""
import argparse
import collections
import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

PROBE = r'''
import atexit, collections, importlib.util, json, sys
BASE = r"__BASE__"
OUT = r"__OUT__"
spec = importlib.util.spec_from_file_location("base_agent", BASE)
mod = importlib.util.module_from_spec(spec)
sys.modules["base_agent"] = mod
spec.loader.exec_module(mod)

REC = []
CT = collections.Counter()
Cls = type(mod._IMPL.chassis)
_orig = Cls.act
_orig_ra = Cls._route_action

def _route_action(self, route, step):
    REC.append([step, route])
    return _orig_ra(self, route, step)

Cls._route_action = _route_action

def act(self, observation, configuration=None):
    out = _orig(self, observation, configuration)
    try:
        player = int(observation["player"])
        CT["HANDS" + str(len((observation["farms"][player].get("hands") or [])))] += 1
        for c in [out.get("farmer") or ["PASS"]] + list(out.get("hands") or []):
            CT[(c or ["PASS"])[0]] += 1
        for o in out.get("market") or []:
            if o and o[0] == "SELL":
                CT["SELL:" + str(o[1])] += int(o[2] or 0)
    except Exception:
        CT["PROBE_ERR"] += 1
    return out

Cls.act = act

def agent(observation, configuration=None):
    return mod.agent(observation, configuration)

agent.telemetry = getattr(mod.agent, "telemetry", {})

def _dump():
    try:
        with open(OUT, "w") as f:
            json.dump({"routes": REC, "counts": dict(CT),
                   "scale": getattr(getattr(mod, "agent", None), "scale_state", None),
                   "fert": getattr(getattr(mod, "agent", None), "fert_state", None),
                   "router": getattr(getattr(mod, "agent", None), "router_state_report", None),
                   "router2": getattr(getattr(mod, "agent", None), "router2_report", None)}, f)
    except Exception:
        pass

atexit.register(_dump)
'''

GAME = r"""
import json, sys, importlib.util as iu
def load(p, n):
    s = iu.spec_from_file_location(n, p)
    m = iu.module_from_spec(s)
    sys.modules[n] = m
    s.loader.exec_module(m)
    return m
a, b, seed = sys.argv[1], sys.argv[2], int(sys.argv[3])
out = sys.argv[4] if len(sys.argv) > 4 else ""
ma, mb = load(a, "probe_a"), load(b, "probe_b")
from kaggle_environments import make
env = make("kaggriculture", configuration={"episodeSteps": 720, "seed": seed})
env.run([ma.agent, mb.agent])
f = env.steps[-1]
if out:
    def _g(s, k):
        try:
            return getattr(s, k)
        except Exception:
            return s[k]
    json.dump({"steps": [[{"action": _g(s, "action"),
                           "observation": _g(s, "observation"),
                           "reward": _g(s, "reward"),
                           "status": _g(s, "status")} for s in turn]
                         for turn in env.steps],
               "rewards": [_g(x, "reward") for x in f],
               "statuses": [_g(x, "status") for x in f]},
              open(out, "w"))
print(json.dumps({"a": f[0]["reward"], "b": f[1]["reward"],
                  "sa": f[0]["status"], "sb": f[1]["status"]}))
"""


def make_probe(base, dest, out_path):
    p = Path(dest)
    p.mkdir(parents=True, exist_ok=True)
    src = PROBE.replace("__BASE__", os.path.abspath(base)).replace(
        "__OUT__", os.path.abspath(out_path))
    (p / "main.py").write_text(src)
    return str(p / "main.py")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("agent_a")
    ap.add_argument("agent_b")
    ap.add_argument("--seeds", type=int, default=8)
    ap.add_argument("--start", type=int, default=500)
    ap.add_argument("--top", type=int, default=3)
    ap.add_argument("--save-replay", default=None,
                    help="directory to write per-seed replay JSON into")
    args = ap.parse_args()

    tmp = Path(tempfile.mkdtemp(prefix="probe_"))
    adiff = []
    for i in range(args.seeds):
        seed = args.start + i
        oa, ob = tmp / f"a{seed}.json", tmp / f"b{seed}.json"
        pa = make_probe(args.agent_a, tmp / f"pa{seed}", oa)
        pb = make_probe(args.agent_b, tmp / f"pb{seed}", ob)
        outfile = ""
        if args.save_replay:
            Path(args.save_replay).mkdir(parents=True, exist_ok=True)
            outfile = str(Path(args.save_replay) / f"seed{seed}.json")
        r = subprocess.run([sys.executable, "-c", GAME, pa, pb, str(seed), outfile],
                           capture_output=True, text=True, cwd=str(ROOT))
        lines = [l for l in r.stdout.strip().splitlines() if l.startswith("{")]
        if not lines:
            print(f"seed {seed}: FAILED {r.stderr.strip().splitlines()[-1:]}")
            continue
        res = json.loads(lines[-1])
        A = json.loads(oa.read_text()) if oa.exists() else {"routes": [], "counts": {}}
        B = json.loads(ob.read_text()) if ob.exists() else {"routes": [], "counts": {}}
        ra = collections.Counter(x for _, x in A["routes"] if x is not None)
        rb = collections.Counter(x for _, x in B["routes"] if x is not None)
        d = (res["a"] or 0) - (res["b"] or 0)
        adiff.append(d)

        def led(C):
            return (f"WATER={C.get('WATER')} PASS={C.get('PASS')} "
                    f"HARVEST={C.get('HARVEST')} PLANT={C.get('PLANT')} "
                    f"CARE={C.get('CARE')}")

        def sells(C):
            return {k[5:]: v for k, v in sorted(C.items()) if k.startswith("SELL:")}

        print(f"seed {seed}: A={res['a']} B={res['b']} diff={d:+}")
        print(f"   A[{res['sa']}] routes {ra.most_common(args.top)} {led(A['counts'])}")
        print(f"      sells {sells(A['counts'])}")
        if A.get("scale"):
            print(f"      scale {A['scale']}")
        if A.get("fert"):
            print(f"      fert {A['fert']}")
        if A.get("router"):
            print(f"      router {A['router']}")
        if A.get("router2"):
            print(f"      router2 {A['router2']}")
        if B.get("scale"):
            print(f"      scaleB {B['scale']}")
        print(f"   B[{res['sb']}] routes {rb.most_common(args.top)} {led(B['counts'])}")
        print(f"      sells {sells(B['counts'])}")
    if adiff:
        print(f"\nmean diff A-B = {sum(adiff)/len(adiff):+,.0f}  "
              f"(A wins {sum(1 for x in adiff if x > 0)}, "
              f"B wins {sum(1 for x in adiff if x < 0)}, "
              f"ties {sum(1 for x in adiff if x == 0)})")


if __name__ == "__main__":
    main()
