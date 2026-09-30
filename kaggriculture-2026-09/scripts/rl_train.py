#!/usr/bin/env python
"""PPO over the residual override space, with the tape family as the behavior policy.

Why this shape (measured, see REPORT-top5-and-planner.md §16):
  * the environment is the bottleneck: 692 steps/s/core engine-only, 120 with the
    tape policy on the other seat, while a 2x256 MLP does 857k samples/s on CPU;
  * so the GPU is irrelevant here (projected speedup 1.05x) and the win comes from
    keeping the policy cheap and using all 104 cores;
  * learning the whole game is hopeless (our from-scratch planner sits at ~5% of
    the tape), so the policy only decides WHEN to override one unit's action or add
    one market order on top of the tape.

Reward: the per-step change of our wallet.  Its sum over a game is exactly
final_money - 3000, i.e. the competition objective, so the dense signal is exact
rather than shaped.

Usage (single process, for debugging):
  python scripts/rl_train.py --workers 2 --games-per-worker 2 --iters 2 --local
Usage (on the 104-core box):
  python scripts/rl_train.py --workers 96 --games-per-worker 16 --iters 200 \
      --out /work/rl_ckpt.pt --log /work/rl_train.log
"""
import argparse
import copy
import io
import json
import os
import sys
import time
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))

K_ACTIONS = 64          # padded menu size
REWARD_SCALE = 1.0 / 1000.0


def _build_net(dim, hidden=256, noop_bias=6.0, alt_bias=0.0):
    import torch
    import torch.nn as nn
    net = nn.Sequential(nn.Linear(dim, hidden), nn.ReLU(),
                        nn.Linear(hidden, hidden), nn.ReLU(),
                        nn.Linear(hidden, K_ACTIONS))
    with torch.no_grad():
        # start as "never override": index 0 is the no-op, so the initial policy
        # is (almost) the production tape and PPO only moves away where it pays
        net[-1].bias.zero_()
        net[-1].bias[0] = noop_bias
        if alt_bias:
            net[-1].bias[1:4] = alt_bias
    return net


def _weights_bytes(net):
    import torch
    buf = io.BytesIO()
    torch.save(net.state_dict(), buf)
    return buf.getvalue()


def _rollout_job(job):
    """Worker: play games with the shipped weights, return transitions."""
    (wbytes, seeds, opponent_path, opp_settings, tape_path, space) = job
    import torch
    # 96 workers x torch's default thread count = ~10,000 threads fighting for 104
    # cores (load average hit 1,198 and no iteration finished); one thread each
    torch.set_num_threads(1)
    import rl_env
    from kaggle_environments import make

    net = _build_net(rl_env.FEATURE_DIM, noop_bias=6.0, alt_bias=0.0)
    net.load_state_dict(torch.load(io.BytesIO(wbytes), map_location="cpu"))
    net.eval()
    tape = rl_env.build_agent(Path(tape_path), None, "beh")
    opp = rl_env.build_agent(Path(opponent_path), opp_settings, "opp")

    F, M, A, R, D, LP, V = [], [], [], [], [], [], []
    stats = {"games": 0, "reward": 0.0, "overrides": 0, "steps": 0}
    for seed in seeds:
        env = make("kaggriculture", configuration={"episodeSteps": 720, "seed": seed})
        env.reset()
        money_prev = env.steps[-1][0]["observation"]["farms"][0]["money"]
        while not env.done:
            o0 = env.steps[-1][0]["observation"]
            o1 = env.steps[-1][1]["observation"]
            c0 = copy.deepcopy(o0)
            c1 = copy.deepcopy(o1)
            turn = len(env.steps) - 1
            c0["player"], c1["player"] = 0, 1
            c0["step"] = c1["step"] = turn
            base0 = tape(c0)
            base1 = opp(c1)
            if space == "market":
                menu = rl_env.market_menu(c0, 0, base0)
            else:
                menu = rl_env.override_menu(c0, 0, base0, pass_only=True)
            feats = rl_env.encode(c0, 0)
            mask = np.zeros(K_ACTIONS, dtype=np.float32)
            mask[:min(len(menu), K_ACTIONS)] = 1.0
            with torch.no_grad():
                logits = net(torch.from_numpy(feats).unsqueeze(0))[0]
                masked = logits + torch.from_numpy(
                    np.where(mask > 0, 0.0, -1e8).astype(np.float32))
                dist = torch.distributions.Categorical(logits=masked)
                act = dist.sample()
                lp = float(dist.log_prob(act))
                val = float(masked.max())  # placeholder; a real critic is added below
            a0 = (rl_env.apply_market_override(base0, int(act), c0, 0, menu)
                  if space == "market"
                  else rl_env.apply_override(base0, int(act), c0, 0, menu))
            env.step([a0, base1])
            money_now = env.steps[-1][0]["observation"]["farms"][0]["money"]
            F.append(feats); M.append(mask); A.append(int(act))
            # scale: the raw per-step delta is O(1e3) coins, so returns reach 1e5
            # and the value loss explodes to NaN (measured on the first run)
            R.append(float(money_now - money_prev) * REWARD_SCALE)
            D.append(1.0 if env.done else 0.0)
            LP.append(lp); V.append(val)
            stats["overrides"] += 1 if int(act) != 0 else 0
            stats["steps"] += 1
            money_prev = money_now
        stats["games"] += 1
        stats["reward"] += float(env.steps[-1][0]["reward"] or 0)
    return {"f": np.asarray(F, dtype=np.float32), "m": np.asarray(M, dtype=np.float32),
            "a": np.asarray(A, dtype=np.int64), "r": np.asarray(R, dtype=np.float32),
            "d": np.asarray(D, dtype=np.float32), "lp": np.asarray(LP, dtype=np.float32),
            "stats": stats}


def gae(rewards, dones, values, gamma=0.9995, lam=0.95):
    """Standard GAE(lambda).

    delta_t = r_t + gamma * V_{t+1} - V_t      (V_{t+1} is the NEXT value)
    A_t     = delta_t + gamma * lam * A_{t+1}

    The first version used A_{t+1} in place of V_{t+1}, which makes the recursion
    A_t = (r-v) + gamma*(1+lam)*A_{t+1} with gamma*(1+lam) = 1.949 > 1 -- it
    diverges and every update was skipped as non-finite (709 steps -> inf).
    """
    n = len(rewards)
    adv = np.zeros(n, dtype=np.float64)
    next_value = 0.0
    last_adv = 0.0
    for t in reversed(range(n)):
        nonterm = 1.0 - float(dones[t])
        delta = float(rewards[t]) + gamma * next_value * nonterm - float(values[t])
        last_adv = delta + gamma * lam * nonterm * last_adv
        adv[t] = last_adv
        next_value = float(values[t])
    return adv.astype(np.float32), (adv + np.asarray(values, dtype=np.float64)).astype(np.float32)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--workers", type=int, default=8)
    ap.add_argument("--games-per-worker", type=int, default=4)
    ap.add_argument("--iters", type=int, default=10)
    ap.add_argument("--seed0", type=int, default=5000)
    ap.add_argument("--opponent", default=",".join([
        str(ROOT / "data" / "league" / d / "main.py") for d in (
            "ahmedberatozer_kaggriculture-v40-plans-that-fit-the-shops",
            "ahmedberatozer_kaggriculture-v38-smarter-feed-stronger-margins",
            "ahmedberatozer_kaggriculture-v39-ready-before-the-rush",
            "ahmedberatozer_kaggriculture-v41-review-candidate",
            "aurax7_kaggriculture-shop-router-reactive-v5")]),
        help="comma list; rotated per iteration so the policy generalises")
    ap.add_argument("--tape", default=str(ROOT / "data" / "league" /
                    "ahmedberatozer_kaggriculture-v42-production-that-fits-the-marke" / "main.py"))
    ap.add_argument("--opp-settings", default=None, help="JSON settings patch for the opponent")
    ap.add_argument("--out", default=str(ROOT / "data" / "rl_ckpt.pt"))
    ap.add_argument("--log", default=str(ROOT / "data" / "rl_train.log"))
    ap.add_argument("--lr", type=float, default=1e-4)
    ap.add_argument("--epochs", type=int, default=4)
    ap.add_argument("--minibatch", type=int, default=4096)
    ap.add_argument("--clip", type=float, default=0.2)
    ap.add_argument("--entropy", type=float, default=0.002)
    ap.add_argument("--value-coef", type=float, default=0.5)
    ap.add_argument("--noop-bias", type=float, default=2.0,
                    help="initial logit for 'keep the tape action'")
    ap.add_argument("--alt-bias", type=float, default=0.5,
                    help="initial logit for the alternative actions (exploration)")
    ap.add_argument("--anchor", type=float, default=0.01,
                    help="L2 pull of the output logits toward the initial no-op bias")
    ap.add_argument("--init-ckpt", default=None)
    ap.add_argument("--local", action="store_true", help="force a single process pool of 1")
    ap.add_argument("--space", default="market", choices=["market", "unit"],
                    help="residual action space: market order scaling (safe, measured) "
                         "or unit ops (measured to be inert)")
    ap.add_argument("--yardstick", type=int, default=6,
                    help="workers always playing a fixed opponent/seeds")
    ap.add_argument("--yard-games", type=int, default=4)
    ap.add_argument("--yard-seed0", type=int, default=7000)
    ap.add_argument("--yard-opponent", default=str(
        ROOT / "data" / "league" /
        "ahmedberatozer_kaggriculture-v40-plans-that-fit-the-shops" / "main.py"))
    args = ap.parse_args()
    import torch
    import torch.nn as nn
    import multiprocessing as mp
    torch.set_num_threads(1)
    import rl_env

    net = _build_net(rl_env.FEATURE_DIM, noop_bias=args.noop_bias, alt_bias=args.alt_bias)
    anchor_logits = net[-1].bias.detach().clone()      # initial no-op-favouring bias
    critic = nn.Sequential(nn.Linear(rl_env.FEATURE_DIM, 256), nn.ReLU(),
                           nn.Linear(256, 256), nn.ReLU(), nn.Linear(256, 1))
    if args.init_ckpt and Path(args.init_ckpt).exists():
        sd = torch.load(args.init_ckpt, map_location="cpu")
        net.load_state_dict(sd["net"]); critic.load_state_dict(sd["critic"])
        print(f"resumed from {args.init_ckpt}")
    opt = torch.optim.Adam(list(net.parameters()) + list(critic.parameters()), lr=args.lr)
    logf = open(args.log, "a")
    procs = 1 if args.local else max(1, args.workers)
    print(f"PPO: {procs} workers x {args.games_per_worker} games = "
          f"{procs*args.games_per_worker} games/iter "
          f"(~{procs*args.games_per_worker*720:,} steps)", flush=True)

    for it in range(args.iters):
        t0 = time.time()
        wb = _weights_bytes(net)
        opp_settings = json.loads(args.opp_settings) if args.opp_settings else None
        opp_list = [o for o in args.opponent.split(",") if o.strip()]
        args.opponent_used = opp_list[it % max(1, len(opp_list))]
        # a fixed yardstick: a few workers always play the SAME opponent on the
        # SAME seeds, so their mean wallet is comparable across iterations.  The
        # rotating-arm mean is not (different opponents have different scales),
        # which is exactly how the first collapse went unnoticed.
        yard_n = max(1, args.yardstick) if args.yardstick else 0
        yard_seeds = [args.yard_seed0 + s for s in range(args.yard_games)]
        jobs, yard_idx = [], []
        for w in range(procs):
            base = args.seed0 + it * procs * args.games_per_worker + w * args.games_per_worker
            if w < yard_n:
                yard_idx.append(len(jobs))
                jobs.append((wb, yard_seeds[:args.yard_games], args.yard_opponent,
                             opp_settings, args.tape, args.space))
            else:
                jobs.append((wb, list(range(base, base + args.games_per_worker)),
                             args.opponent_used, opp_settings, args.tape, args.space))
        if procs == 1:
            outs = [_rollout_job(jobs[0])]
        else:
            with mp.Pool(procs) as pool:
                outs = pool.map(_rollout_job, jobs)
        roll_dt = time.time() - t0
        F = np.concatenate([o["f"] for o in outs]); M = np.concatenate([o["m"] for o in outs])
        if not np.isfinite(F).all():
            bad = np.argwhere(~np.isfinite(F))[:3]
            print(f"  !! non-finite features at {bad.tolist()}", flush=True)
        A = np.concatenate([o["a"] for o in outs]); R = np.concatenate([o["r"] for o in outs])
        D = np.concatenate([o["d"] for o in outs]); LP = np.concatenate([o["lp"] for o in outs])
        G = sum(o["stats"]["games"] for o in outs)
        mean_rew = sum(o["stats"]["reward"] for o in outs) / max(1, G)
        ovr = sum(o["stats"]["overrides"] for o in outs) / max(1, len(R))
        if yard_idx:
            yg = sum(outs[i]["stats"]["games"] for i in yard_idx)
            yard_rew = sum(outs[i]["stats"]["reward"] for i in yard_idx) / max(1, yg)
            yard_ovr = (sum(outs[i]["stats"]["overrides"] for i in yard_idx)
                        / max(1, sum(len(outs[i]["r"]) for i in yard_idx)))
        else:
            yard_rew = float("nan"); yard_ovr = float("nan")
        # values from the critic (the actor's max-logit was only a placeholder)
        with torch.no_grad():
            Vv = critic(torch.from_numpy(F)).squeeze(-1).numpy()
        if it == 0:
            print(f"  [dbg] R min/max {R.min():.3g}/{R.max():.3g} finite={np.isfinite(R).all()} | "
                  f"Vv {Vv.min():.3g}/{Vv.max():.3g} finite={np.isfinite(Vv).all()} | "
                  f"D sum {D.sum():.0f} n {len(R)}", flush=True)
        # guard: any non-finite reward poisons the whole return recursion
        R = np.nan_to_num(R, nan=0.0, posinf=0.0, neginf=0.0)
        Vv = np.nan_to_num(Vv, nan=0.0, posinf=0.0, neginf=0.0)
        adv, ret = gae(R, D, Vv)
        ret = np.clip(ret, -1e3, 1e3)
        if not (np.isfinite(adv).all() and np.isfinite(ret).all()):
            print(f"  !! non-finite adv/ret: adv {np.nanmax(np.abs(adv)):.3g} "
                  f"ret {np.nanmax(np.abs(ret)):.3g}", flush=True)
        adv = (adv - adv.mean()) / (adv.std() + 1e-6)
        F_t = torch.from_numpy(F); M_t = torch.from_numpy(M); A_t = torch.from_numpy(A)
        LP_t = torch.from_numpy(LP); ADV_t = torch.from_numpy(adv.astype(np.float32))
        RET_t = torch.from_numpy(ret.astype(np.float32))
        n = len(F)
        idx = np.arange(n)
        pl = vl = el = 0.0
        skipped = 0
        t1 = time.time()
        for ep in range(args.epochs):
            np.random.shuffle(idx)
            for s in range(0, n, args.minibatch):
                b = idx[s:s + args.minibatch]
                logits_raw = net(F_t[b])
                logits = logits_raw + torch.from_numpy(
                    np.where(M[b] > 0, 0.0, -1e8).astype(np.float32))
                dist = torch.distributions.Categorical(logits=logits)
                lp = dist.log_prob(A_t[b])
                ratio = torch.exp(lp - LP_t[b])
                s1 = ratio * ADV_t[b]
                s2 = torch.clamp(ratio, 1 - args.clip, 1 + args.clip) * ADV_t[b]
                pi_loss = -torch.min(s1, s2).mean()
                v = critic(F_t[b]).squeeze(-1)
                v_loss = nn.functional.mse_loss(v, RET_t[b])
                ent = dist.entropy().mean()
                anchor = ((logits_raw - anchor_logits) ** 2).mean()
                loss = (pi_loss + args.value_coef * v_loss - args.entropy * ent
                        + args.anchor * anchor)
                if not torch.isfinite(loss):
                    skipped += 1
                    if skipped == 1:
                        print(f"  !! NaN loss: pi {float(pi_loss)} v {float(v_loss)} "
                              f"ent {float(ent)} | logits {float(logits.abs().max())} "
                              f"lp {float(lp.abs().max())} lp0 {float(LP_t[b].abs().max())} "
                              f"ret {float(RET_t[b].abs().max())} adv {float(ADV_t[b].abs().max())} "
                              f"ratio {float(ratio.max())}", flush=True)
                    continue
                opt.zero_grad(); loss.backward()
                nn.utils.clip_grad_norm_(list(net.parameters()) + list(critic.parameters()), 0.5)
                opt.step()
                pl += float(pi_loss); vl += float(v_loss); el += float(ent)
        upd_dt = time.time() - t1
        nb = max(1, (n + args.minibatch - 1) // args.minibatch * args.epochs)
        msg = (f"iter {it:4d} | YARDSTICK {yard_rew:9,.0f} @{yard_ovr:4.1%} "
               f"| vs {Path(args.opponent_used).parent.name[-14:]:14s} "
               f"| games {G:5d} steps {n:8,d} | rot wallet {mean_rew:9,.0f} "
               f"| override rate {ovr:5.1%} | rollout {roll_dt:6.1f}s update {upd_dt:5.1f}s "
               f"| pi {pl/nb:+.4f} v {vl/nb:.1f} ent {el/nb:.3f} skipped {skipped}")
        print(msg, flush=True); logf.write(msg + "\n"); logf.flush()
        torch.save({"net": net.state_dict(), "critic": critic.state_dict(),
                    "iter": it, "args": vars(args)}, args.out)


if __name__ == "__main__":
    main()
