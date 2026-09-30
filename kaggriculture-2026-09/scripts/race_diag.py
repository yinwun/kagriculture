#!/usr/bin/env python
"""Run one game with a built `data/race/<variant>/main.py` and report what the
race layer actually did: how many steps it searched, how many it changed, the
simulated gain it claims, and whether the layout it emitted survived the ~120
wrapper agents that sit outside the chassis (they may prepend orders, which
shifts every slot we chose).

Usage: .venv/bin/python scripts/race_diag.py --variant clone --seed 9000
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--variant", default="clone")
    ap.add_argument("--seed", type=int, default=9000)
    ap.add_argument("--base", default=str(ROOT / "data" / "tapeopt" / "rgcs" / "main.py"))
    args = ap.parse_args()
    from kaggle_environments import make

    def load(p):
        ns = {"__name__": "race_diag_mod"}
        exec(compile(Path(p).read_text(), p, "exec"), ns)
        return ns

    cand = load(str(ROOT / "data" / "race" / args.variant / "main.py"))
    base = load(args.base)
    seen = {}
    cand_agent = cand["agent"]

    def wrap(obs):
        act = cand_agent(obs)
        seen[int(obs["step"])] = [list(o) for o in (act.get("market") or [])]
        return act

    env = make("kaggriculture", configuration={"episodeSteps": 720, "seed": args.seed})
    env.run([wrap, base["agent"]])
    d = cand["_IMPL"].chassis.diagnostics
    g = lambda k: d.get(k) or 0
    final = [env.steps[-1][i]["reward"] for i in (0, 1)]
    hook = cand["_IMPL"].chassis.cfg.get("race_hook", "chassis")
    if hook == "outer":
        st = cand.get("_RACE_STATES", {}).get(0, {}).get("race", {})
    else:
        st = cand["_IMPL"].chassis.players.get(0, {}).get("race", {})
    emitted = st.get("emitted", {})
    survived = sum(1 for s, m in emitted.items()
                   if m == [list(o) for o in seen.get(s, [])])
    print(f"variant {args.variant} seed {args.seed}: final {final} "
          f"delta {final[0]-final[1]:+,.0f}")
    print(f"   hook: {hook}")
    print(f"   layer: tried {g('race_tried')} considered {g('race_considered')} "
          f"reorders {g('race_reorders')} claimed gain {g('race_gain'):.1f} "
          f"errors {g('race_errors')} layer_fallbacks {g('layer_fallbacks')} "
          f"entry_fallbacks {g('entry_fallbacks')}")
    print(f"   emitted layouts that survived the wrapper chain unchanged: "
          f"{survived} of {len(emitted)}")
    for s in sorted(emitted)[:3]:
        print(f"      step {s}: emitted {emitted[s]}")
        print(f"                final  {seen.get(s)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
