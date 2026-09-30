#!/usr/bin/env python
"""Wrap the PPO checkpoint into a playable agent: tape + learned overrides.

Used for evaluation (scripts/par_eval.py --pool) and as the basis for exporting a
stdlib-only submission once the policy beats the tape.

Usage:
  python scripts/rl_agent.py --eval-ckpt /work/rl_ckpt.pt --seeds 4000-4019
  python scripts/rl_agent.py --build-main --ckpt /work/rl_ckpt.pt --out data/tapeopt/rl/main.py
"""
import argparse
import copy
import io
import json
import sys
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))
import rl_env  # noqa: E402
from rl_train import K_ACTIONS, _build_net  # noqa: E402

V42 = (ROOT / "data" / "league" /
       "ahmedberatozer_kaggriculture-v42-production-that-fits-the-marke" / "main.py")


def _plain(x):
    """Force the action to plain Python types.

    kaggle-environments deep-copies every action, so a leaked numpy/torch object
    (or worse, a module reference) aborts the game with
    "TypeError: cannot pickle 'module' object".
    """
    if isinstance(x, dict):
        return {k: _plain(v) for k, v in x.items()}
    if isinstance(x, (list, tuple)):
        return [_plain(v) for v in x]
    if isinstance(x, (str, int, float, bool)) or x is None:
        return x
    return str(x)


class RLAgent:
    """Deterministic (argmax) or sampled residual policy on top of the tape."""

    def __init__(self, ckpt, tape_path=V42, temperature=0.0, tape_settings=None,
                 space="market"):
        import torch
        self.torch = torch
        self.net = _build_net(rl_env.FEATURE_DIM)
        sd = torch.load(ckpt, map_location="cpu")
        self.net.load_state_dict(sd["net"] if "net" in sd else sd)
        self.net.eval()
        self.tape = rl_env.build_agent(Path(tape_path), tape_settings, "tape")
        self.temperature = temperature
        self.space = space
        self.stats = {"steps": 0, "overrides": 0}

    # callable, because env.run()/env.step() hand non-callables straight into the
    # action pipeline -- an uncallable agent holding a torch module aborted the
    # game with "TypeError: cannot pickle 'module' object"
    def act(self, observation, configuration=None):
        t = self.torch
        obs = copy.deepcopy(observation)
        player = int(obs.get("player") or 0)
        if "step" not in obs or obs.get("step") is None:
            obs["step"] = 0
        base = self.tape(copy.deepcopy(obs))
        try:
            menu = (rl_env.market_menu(obs, player, base) if self.space == "market"
                    else rl_env.override_menu(obs, player, base, pass_only=True))
            feats = rl_env.encode(obs, player)
            mask = np.zeros(K_ACTIONS, dtype=np.float32)
            mask[:min(len(menu), K_ACTIONS)] = 1.0
            with t.no_grad():
                logits = self.net(t.from_numpy(feats).unsqueeze(0))[0]
                logits = logits + t.from_numpy(np.where(mask > 0, 0.0, -1e8).astype(np.float32))
                if self.temperature > 0:
                    pick = int(t.distributions.Categorical(logits=logits / self.temperature).sample())
                else:
                    pick = int(t.argmax(logits))
            self.stats["steps"] += 1
            self.stats["overrides"] += 1 if pick else 0
            out = (rl_env.apply_market_override(base, pick, obs, player, menu)
                   if self.space == "market"
                   else rl_env.apply_override(base, pick, obs, player, menu))
            return _plain(out)
        except Exception:
            return _plain(base)

    def __call__(self, observation, configuration=None):
        return self.act(observation, configuration)


def _eval_chunk(job):
    """Worker: paired rl-vs-tape over a chunk of held-out towns."""
    ckpt, seeds, opponent = job
    import multiprocessing
    from kaggle_environments import make
    pol = RLAgent(ckpt)
    base = rl_env.build_agent(V42, None, "base")
    opp = rl_env.build_agent(Path(opponent), None, "opp")
    out = []
    for s in seeds:
        env = make("kaggriculture", configuration={"episodeSteps": 720, "seed": s})
        env.run([pol, opp])
        rl_r = env.steps[-1][0]["reward"] or 0
        env = make("kaggriculture", configuration={"episodeSteps": 720, "seed": s})
        env.run([base, opp])
        tape_r = env.steps[-1][0]["reward"] or 0
        out.append((s, rl_r, tape_r, rl_r - tape_r))
    return out


def _eval_parallel(ckpt, seeds, opponent, procs):
    import multiprocessing as mp
    n = max(1, procs)
    step = max(1, -(-len(seeds) // n))
    jobs = [(ckpt, seeds[i:i + step], opponent) for i in range(0, len(seeds), step)]
    with mp.Pool(len(jobs)) as pool:
        res = pool.map(_eval_chunk, jobs)
    rows = [r for chunk in res for r in chunk]
    rows.sort()
    return rows


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--eval-ckpt", default=None)
    ap.add_argument("--ckpt", default=None)
    ap.add_argument("--seeds", default="4000-4009")
    ap.add_argument("--opponent", default=str(ROOT / "data" / "league" /
                    "ahmedberatozer_kaggriculture-v40-plans-that-fit-the-shops" / "main.py"))
    ap.add_argument("--procs", type=int, default=1)
    ap.add_argument("--build-main", action="store_true")
    ap.add_argument("--out", default="data/tapeopt/rl/main.py")
    args = ap.parse_args()

    if args.eval_ckpt:
        from kaggle_environments import make
        seeds = []
        for part in args.seeds.split(","):
            if "-" in part:
                a, b = part.split("-")
                seeds.extend(range(int(a), int(b) + 1))
            else:
                seeds.append(int(part))
        if args.procs > 1:
            rows = _eval_parallel(args.eval_ckpt, seeds, args.opponent, args.procs)
        else:
            rows = _eval_chunk((args.eval_ckpt, seeds, args.opponent))
        d = []
        for s, rl_r, tape_r, delta in rows:
            d.append(delta)
            print(f"seed {s}: rl {rl_r:9,.0f}  tape {tape_r:9,.0f}  delta {delta:+9,.0f}", flush=True)
        mu = sum(d) / len(d)
        sd = (sum((x - mu) ** 2 for x in d) / max(1, len(d) - 1)) ** 0.5
        print(f"\nmean delta {mu:+,.0f} (t={mu/(sd/len(d)**0.5) if sd else 0:+.2f}) "
              f"wins {sum(1 for x in d if x>0)}/{len(d)} medians "
              f"{sorted(d)[len(d)//2]:+,.0f}")
        return

    if args.build_main:
        raise SystemExit("pure-python export not implemented yet; evaluate first")


if __name__ == "__main__":
    main()
