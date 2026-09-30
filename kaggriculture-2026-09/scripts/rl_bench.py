#!/usr/bin/env python
"""Where does PPO wall-clock actually go for this environment?

Three measurements, so the CPU-vs-GPU question is answered with numbers:
  A. engine-only throughput      : env.step with two no-op agents
  B. tape-agent throughput       : the realistic behavior policy
  C. network fwd+bwd cost        : a 2x256 MLP (116 -> 40), what PPO updates need
Then it projects a PPO run: rollout (env-bound, CPU-only, cannot use the GPU) vs
update (net-bound, GPU-able), under CPU and under a hypothetical GPU.

Usage: python scripts/rl_bench.py [--cores 100] [--pop 2000000]
"""
import argparse
import time

import numpy as np

PASS = {"farmer": ["PASS"], "hands": [], "market": []}


def engine_only(steps=1440):
    from kaggle_environments import make
    env = make("kaggriculture", configuration={"episodeSteps": 720, "seed": 1})
    env.reset()
    t0 = time.time()
    n = 0
    while not env.done and n < steps:
        env.step([PASS, PASS])
        n += 1
    dt = time.time() - t0
    return n / dt


def with_agents(seed=700):
    import sys
    from pathlib import Path
    sys.path.insert(0, str(Path(__file__).resolve().parent))
    import rl_env
    t0 = time.time()
    r = rl_env.run_episode(None, seed)
    dt = time.time() - t0
    return 720 / dt, r["reward"]


def net_cost(obs_dim=116, act_dim=40, hidden=256, batch=4096, iters=30):
    try:
        import torch
        import torch.nn as nn
        dev = "cuda" if torch.cuda.is_available() else "cpu"
        net = nn.Sequential(nn.Linear(obs_dim, hidden), nn.ReLU(),
                            nn.Linear(hidden, hidden), nn.ReLU(),
                            nn.Linear(hidden, act_dim)).to(dev)
        opt = torch.optim.Adam(net.parameters(), lr=3e-4)
        x = torch.randn(batch, obs_dim, device=dev)
        y = torch.randint(0, act_dim, (batch,), device=dev)
        for _ in range(5):                      # warmup
            loss = nn.functional.cross_entropy(net(x), y)
            opt.zero_grad(); loss.backward(); opt.step()
        if dev == "cuda":
            torch.cuda.synchronize()
        t0 = time.time()
        for _ in range(iters):
            loss = nn.functional.cross_entropy(net(x), y)
            opt.zero_grad(); loss.backward(); opt.step()
        if dev == "cuda":
            torch.cuda.synchronize()
        dt = (time.time() - t0) / iters
        params = sum(p.numel() for p in net.parameters())
        return {"device": dev, "torch": torch.__version__, "params": params,
                "sec_per_batch": dt, "samples_per_s": batch / dt}
    except Exception as exc:  # noqa: BLE001
        return {"device": "numpy(fallback)", "error": str(exc)[:80]}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--cores", type=int, default=100)
    ap.add_argument("--pop", type=int, default=2_000_000,
                    help="rollout steps per PPO iteration")
    ap.add_argument("--epochs", type=int, default=4)
    ap.add_argument("--minibatch", type=int, default=4096)
    args = ap.parse_args()

    eng = engine_only()
    tape, reward = with_agents()
    net = net_cost()
    print(f"A. engine only      : {eng:8,.0f} steps/s/core")
    print(f"B. tape policy      : {tape:8,.0f} steps/s/core  (reward {reward:,.0f})")
    print(f"C. net fwd+bwd      : {net}")

    # projection
    sim_sps = tape * args.cores
    rollout_h = args.pop / sim_sps / 3600
    if "samples_per_s" in net:
        upd_per_iter = args.pop * args.epochs / net["samples_per_s"]
        upd_h = upd_per_iter / 3600
        gpu_h = upd_h / 10.0            # a small MLP is ~10x faster on a GPU
    else:
        upd_h = gpu_h = float("nan")
    print(f"\nrollout steps/s (CPU x{args.cores}) : {sim_sps:,.0f}")
    print(f"PPO iteration of {args.pop:,} steps:")
    print(f"   rollout (env, CPU only, GPU cannot help): {rollout_h:6.2f} h")
    print(f"   update  (net, CPU)                      : {upd_h:6.2f} h")
    print(f"   update  (net, hypothetical GPU)         : {gpu_h:6.2f} h")
    if upd_h == upd_h:
        total_cpu = rollout_h + upd_h
        total_gpu = rollout_h + gpu_h
        print(f"   TOTAL CPU {total_cpu:6.2f} h  vs  GPU {total_gpu:6.2f} h"
              f"   -> GPU speedup {total_cpu/total_gpu:4.2f}x")
        print(f"   GPU share of wall clock: {100*gpu_h/total_gpu:.1f}%")


if __name__ == "__main__":
    main()
