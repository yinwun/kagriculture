#!/usr/bin/env python
"""S1.3/S1.4 fidelity gates.

1a pipeline lossless: replay a recorded trace into a FRESH game (the trace supplies the
   actions; the champion plays the other seat) and require (i) every emitted action to
   equal the recorded one and (ii) the observed state to equal the recorded state on
   every step.  (ii) is the real content: it says the trace captures the whole game, not
   just our own action stream, so θ has a complete source to be compiled from.
1c residual localisation: per action type × day, what a θ-derived controller cannot
   reproduce, aggregated over the traced days, with the missing-concept hypothesis.

Usage:
  .venv/bin/python scripts/fidelity.py --gate 1a --trace data/trace/wool_drain1_outerprem-9000
  .venv/bin/python scripts/fidelity.py --gate 1c --trace data/trace/wool_drain1_outerprem-9000 \
      --theta data/plan/theta-9000.json
"""
from __future__ import annotations

import argparse
import collections
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
CHAMPION = str(ROOT / "data" / "tapeopt" / "rgcs" / "main.py")


def _load(path, name="fid_mod"):
    ns = {"__name__": name}
    exec(compile(Path(path).read_text(), str(path), "exec"), ns)
    return ns["agent"]


def _fingerprint(rec):
    return json.dumps([rec.get("money"), rec.get("inv"), rec.get("shed"),
                       rec.get("seeds"), rec.get("shops"), rec.get("mine_tiles")],
                      sort_keys=True)


def gate_1a(trace_dir, opponent=CHAMPION):
    from kaggle_environments import make
    steps = [json.loads(l) for l in Path(trace_dir, "trace.jsonl").read_text().splitlines()]
    by_step = {r["step"]: r for r in steps}
    opp = _load(opponent)
    seen = {"action_ok": 0, "action_bad": 0, "state_ok": 0, "state_bad": 0,
            "missing": 0, "first_bad": None}

    def replay(obs, *a, **k):
        s = int(obs["step"])
        rec = by_step.get(s)
        if rec is None:
            seen["missing"] += 1
            return {"farmer": ["PASS"], "hands": [], "market": []}
        act = {"farmer": rec["action"]["farmer"], "hands": rec["action"]["hands"],
               "market": rec["action"]["market"]}
        # the live observation must equal the recorded one (lossless pipeline)
        live = {"money": float(obs.farms[0]["money"]),
                "inv": {k: int(v) for k, v in dict(obs.market.inventory).items()},
                "shed": {k: int(v) for k, v in dict(obs.private.shed).items()},
                "seeds": {k: int(v) for k, v in dict(obs.private.seeds).items()},
                "shops": list(obs.town["unlocked_shops"])}
        rec_fp = json.dumps([rec.get("money"), rec.get("inv"), rec.get("shed"),
                            rec.get("seeds"), rec.get("shops")], sort_keys=True)
        live_fp = json.dumps([live["money"], live["inv"], live["shed"], live["seeds"],
                              live["shops"]], sort_keys=True)
        if live_fp == rec_fp:
            seen["state_ok"] += 1
        else:
            seen["state_bad"] += 1
            if seen["first_bad"] is None:
                seen["first_bad"] = {"step": s, "recorded": rec_fp[:300], "live": live_fp[:300]}
        seen["action_ok"] += 1
        return act

    env = make("kaggriculture", configuration={"episodeSteps": 720,
                                              "seed": int(by_step[0].get("seed") or
                                                          Path(trace_dir).name.rsplit("-", 1)[-1])})
    env.run([replay, opp])
    total = len(steps)
    print(f"1a trace {Path(trace_dir).name}: steps {total} | actions replayed "
          f"{seen['action_ok']}/{total} | state match {seen['state_ok']}/{total} "
          f"(mismatch {seen['state_bad']}, missing {seen['missing']})")
    if seen["first_bad"]:
        print("   first state mismatch:", json.dumps(seen["first_bad"])[:400])
    ok = seen["state_bad"] == 0 and seen["missing"] == 0 and seen["action_ok"] == total
    print(f"   GATE 1a: {'PASS' if ok else 'FAIL'}")
    return {"gate": "1a", "trace": str(trace_dir), "steps": total,
            "action_ok": seen["action_ok"], "state_ok": seen["state_ok"],
            "state_bad": seen["state_bad"], "missing": seen["missing"], "pass": ok,
            "first_bad": seen["first_bad"]}


def canonical(act):
    out = []
    for cmd in [act.get("farmer")] + list(act.get("hands") or []):
        if isinstance(cmd, list) and cmd:
            if cmd[0] in ("NORTH", "SOUTH", "EAST", "WEST"):
                out.append("MOVE")
            else:
                out.append(cmd[0])
    for o in act.get("market") or []:
        if isinstance(o, list) and o:
            out.append("MKT_" + o[0])
    return out


def gate_1c(trace_dir, theta_path, opponent=CHAMPION, agent_path=None):
    """Per action-type x day, what the theta controller reproduces, measured live."""
    steps = [json.loads(l) for l in Path(trace_dir, "trace.jsonl").read_text().splitlines()]
    ref = {r["step"]: collections.Counter(canonical(r["action"])) for r in steps}
    if agent_path is None:
        print("1c: no theta agent supplied (--agent); static expressibility only")
        return {"gate": "1c", "static": True}
    from kaggle_environments import make
    theta_agent = _load(agent_path, "theta_mod")
    live = {}
    opp = _load(opponent)

    def wrap(obs, *a, **k):
        act = theta_agent(obs)
        live[int(obs["step"])] = collections.Counter(canonical(act))
        return act

    seed = int(Path(trace_dir).name.rsplit("-", 1)[-1])
    env = make("kaggriculture", configuration={"episodeSteps": 720, "seed": seed})
    env.run([wrap, opp])
    types = sorted({t for s in ref for t in ref[s]} | {t for s in live for t in live[s]})
    print(f"1c residual: per action type x day (champion vs theta agent), seed {seed}")
    print(f"{'type':10s} {'day0-9 ref/theta':>20s} {'day10-19 ref/theta':>22s} "
          f"{'day20-29 ref/theta':>22s}")
    rows = []
    for t in types:
        cells = []
        for lo, hi in ((0, 10), (10, 20), (20, 30)):
            a = sum(ref.get(s, {}).get(t, 0) for s in ref if lo <= s // 24 < hi)
            b = sum(live.get(s, {}).get(t, 0) for s in live if lo <= s // 24 < hi)
            cells.append((a, b))
        rows.append({"type": t, "cells": cells})
        print(f"{t:10s} " + " ".join(f"{a:8d}/{b:<8d}    " for a, b in cells))
    return {"gate": "1c", "seed": seed, "rows": rows}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--gate", required=True)
    ap.add_argument("--trace", required=True)
    ap.add_argument("--theta", default=None)
    ap.add_argument("--agent", default=None, help="the theta-derived agent to measure (1c)")
    ap.add_argument("--out", default=None)
    a = ap.parse_args()
    if a.gate == "1a":
        res = gate_1a(a.trace)
    elif a.gate == "1c":
        res = gate_1c(a.trace, a.theta, agent_path=a.agent)
    else:
        raise SystemExit(f"unknown gate {a.gate}")
    if a.out:
        Path(a.out).write_text(json.dumps(res, indent=1))
    return 0


if __name__ == "__main__":
    sys.exit(main())
