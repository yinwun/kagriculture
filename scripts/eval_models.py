#!/usr/bin/env python3
"""
Evaluate all saved models against a local Kaggriculture env.

For each .zip model, run N episodes (default 3), capture action distribution
and win_rate. Output a single markdown table so you can see which ones
actually trigger trade actions (HIRE/SELL_WHEAT/BUY_WHEAT) vs just HOLD/PASS.

Usage:
  python scripts/eval_models.py                                # all models, 3 ep each
  python scripts/eval_models.py --num_episodes 5              # more episodes
  python scripts/eval_models.py --pattern ppo_v4_short        # specific files
  python scripts/eval_models.py --opponent trained             # vs trained opponent
  python scripts/eval_models.py --output eval_all.md          # write markdown
"""

import argparse
import collections
import glob
import json
import os
import shutil
import sys
import tempfile
import time
import zipfile
from datetime import datetime

import numpy as np
import torch

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from src.envs.kagriculture_env import KagricultureEnv  # noqa — registers kagriculture


def convert_to_npz(model_zip, npz_path):
    """SB3 .zip → policy_np.npz (6 keys)."""
    with tempfile.TemporaryDirectory() as td:
        with zipfile.ZipFile(model_zip) as z:
            z.extractall(td)
        pth = os.path.join(td, "policy.pth")
        if not os.path.exists(pth):
            raise FileNotFoundError(f"policy.pth missing in {model_zip}")
        sd = torch.load(pth, map_location="cpu", weights_only=True)
        out = {}
        keys = (
            "mlp_extractor.policy_net.0.weight", "mlp_extractor.policy_net.0.bias",
            "mlp_extractor.policy_net.2.weight", "mlp_extractor.policy_net.2.bias",
            "action_net.weight", "action_net.bias",
        )
        for k in keys:
            if k not in sd:
                raise KeyError(f"missing key {k} in {pth}")
            out[k] = sd[k].numpy().astype(np.float32)
        np.savez(npz_path, **out)
    return npz_path


def find_models(pattern):
    """Find all .zip models matching pattern, in models/ and eval_reports/."""
    candidates = set()
    for path in glob.glob(f"models/{pattern}*.zip"):
        candidates.add(os.path.abspath(path))
    for path in glob.glob(f"eval_reports/*/{pattern}*.zip"):
        candidates.add(os.path.abspath(path))
    # Default: all models
    if not candidates and pattern == "*":
        for path in glob.glob("models/*.zip"):
            candidates.add(os.path.abspath(path))
        for path in glob.glob("eval_reports/*/model.zip"):
            candidates.add(os.path.abspath(path))
    return sorted(candidates)


# ============================================================
# Eval: load npz, run episodes
# ============================================================

class SimpleActorNP:
    __slots__ = ("W1", "b1", "W2", "b2", "W_action", "b_action")

    def __init__(self, weights_path):
        data = np.load(weights_path)
        self.W1 = data["mlp_extractor.policy_net.0.weight"]
        self.b1 = data["mlp_extractor.policy_net.0.bias"]
        self.W2 = data["mlp_extractor.policy_net.2.weight"]
        self.b2 = data["mlp_extractor.policy_net.2.bias"]
        self.W_action = data["action_net.weight"]
        self.b_action = data["action_net.bias"]

    def forward(self, obs):
        x = np.dot(self.W1, obs) + self.b1
        x = np.maximum(0, x)
        x = np.dot(self.W2, x) + self.b2
        x = np.maximum(0, x)
        return np.dot(self.W_action, x) + self.b_action

    def get_action(self, obs, deterministic=True):
        logits = self.forward(obs)
        return int(np.argmax(logits)) if deterministic else logits


def action_class_from_str(action):
    if action == [] or action == {}:
        return 0
    if action == [{"market": [["HIRE"]]}]:
        return 1
    if action == [{"market": [["SELL", "WHEAT", 1]]}]:
        return 2
    if action == [{"market": [["BUY_PRODUCT", "WHEAT", 1]]}]:
        return 3
    if action == [{"farmer": ["PASS"]}]:
        return 4
    return -1


ACTION_NAMES = {0: "HOLD", 1: "HIRE", 2: "SELL_WHEAT", 3: "BUY_WHEAT", 4: "PASS"}


def eval_one_model(model_zip, num_episodes, opponent, npz_dir):
    """Run num_episodes episodes with the given model. Return summary dict."""
    npz_path = os.path.join(npz_dir, "policy_np.npz")
    convert_to_npz(model_zip, npz_path)

    actor = SimpleActorNP(npz_path)

    from kaggle_environments import make
    env = make("kagriculture", debug=False)

    total_actions = 0
    action_counts = {i: 0 for i in range(-1, 5)}
    wins = 0

    for ep_i in range(num_episodes):
        env.reset(num_agents=2)
        action_log = []
        won = False
        try:
            for step in range(720):
                if env.done:
                    break
                obs = env.state[0].observation
                money = obs.farms[0].get("money", 0)
                day = obs.day
                hour = obs.hour
                # Build 32-dim obs using same formula as KagricultureEnv
                farm = obs.farms[0]
                private = obs.private
                shed = private.shed if isinstance(private.shed, dict) else {}
                # Inline obs construction (matches ObsProcessor.process)
                obs32 = np.zeros(32, dtype=np.float32)
                obs32[0] = step / 720.0
                obs32[1] = day / 30.0
                obs32[2] = min(money, 100000) / 100000.0
                market = obs.market
                prices = market.get("prices", {}) if hasattr(market, "get") else market.prices
                inventory = market.get("inventory", {}) if hasattr(market, "get") else market.inventory
                obs32[3] = prices.get("WHEAT", 0) / 100.0
                obs32[4] = prices.get("FERTILIZER", 0) / 100.0
                obs32[5] = prices.get("MELON",  0) / 100.0
                obs32[6] = prices.get("STRAWBERRY", 0) / 100.0
                obs32[7] = inventory.get("WHEAT", 0) / 1000.0
                obs32[8] = inventory.get("FERTILIZER", 0) / 1000.0
                obs32[9] = inventory.get("MELON", 0) / 1000.0
                obs32[10] = inventory.get("STRAWBERRY", 0) / 1000.0
                # plantable/plants/total/weed: skip tile scan for speed
                # (would need full kagriculture_env._count_* helpers)
                obs32[11] = 0.0  # plantable
                obs32[12] = 0.0  # plants_ready
                obs32[13] = 0.0  # total_plants
                obs32[14] = 0.0  # weed_density
                obs32[15] = 0.0  # cows
                obs32[16] = 0.0  # sheep
                obs32[17] = 0.0  # unfed
                # 18-20 reserved
                obs32[21] = len(farm.get("hands", [])) / 5.0
                obs32[22] = min(money, 100000) / 100000.0
                obs32[23] = shed.get("WHEAT", 0) / 1000.0
                obs32[24] = shed.get("FERTILIZER", 0) / 100.0
                obs32[25] = farm.get("hires_today", 0) / 3.0
                # opponent estimate
                if len(obs.farms) > 1:
                    obs32[26] = min(obs.farms[1].get("money", 0), 100000) / 100000.0
                    obs32[27] = 0.0  # visible_plants
                    obs32[28] = 0.0  # visible_animals

                action_idx = actor.get_action(obs32, deterministic=True)
                # Map index to Kaggle action
                if action_idx == 0:
                    action = []
                elif action_idx == 1:
                    action = [{"market": [["HIRE"]]}]
                elif action_idx == 2:
                    action = [{"market": [["SELL", "WHEAT", 1]]}]
                elif action_idx == 3:
                    action = [{"market": [["BUY_PRODUCT", "WHEAT", 1]]}]
                elif action_idx == 4:
                    action = [{"farmer": ["PASS"]}]
                else:
                    action = []
                action_log.append(action)

                # Opponent
                if opponent == "random":
                    import random as _r
                    opp_options = [{}, {"market": [["HIRE"]]},
                                   {"market": [["SELL", "WHEAT", 1]]},
                                   {"farmer": ["PASS"]}]
                    opp_action = _r.choice(opp_options)
                else:
                    opp_action = {}

                env.step([action, opp_action])
        except Exception:
            pass

        # Final win
        if env.done:
            try:
                p0_money = env.state[0].observation.farms[0].get("money", 0)
                p1_money = env.state[0].observation.farms[1].get("money", 0)
                if p0_money > p1_money:
                    won = True
                    wins += 1
            except Exception:
                pass

        for a in action_log:
            cls = action_class_from_str(a)
            action_counts[cls] += 1
            total_actions += 1

    trade_count = sum(action_counts[a] for a in [1, 2, 3])
    safe_count = action_counts[0] + action_counts[4]
    return {
        "model": model_zip,
        "episodes": num_episodes,
        "wins": wins,
        "win_rate": wins / num_episodes if num_episodes else 0.0,
        "total_actions": total_actions,
        "action_counts": action_counts,
        "trade_count": trade_count,
        "safe_count": safe_count,
        "trade_frac": trade_count / total_actions if total_actions > 0 else 0.0,
        "safe_frac": safe_count / total_actions if total_actions > 0 else 0.0,
    }


def render_markdown(results, opponent, num_episodes):
    lines = []
    lines.append(f"# Saved Model Evaluation")
    lines.append("")
    lines.append(f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}  ")
    lines.append(f"Opponent: `{opponent}`  ·  Episodes per model: {num_episodes}  ·  Action space: 5")
    lines.append("")
    lines.append("## Trade-action summary (HIRE + SELL_WHEAT + BUY_WHEAT)")
    lines.append("")
    lines.append("| Model | Trade % | Safe % | Win rate | Wins / Total |")
    lines.append("|---|---|---|---|---|")
    for r in sorted(results, key=lambda x: -x["trade_frac"]):
        model_short = os.path.basename(os.path.dirname(r["model"])) + "/" + os.path.basename(r["model"])
        if "models/" in r["model"]:
            model_short = os.path.basename(r["model"])
        lines.append(
            f"| `{model_short}` | "
            f"**{r['trade_frac']:.2%}** | "
            f"{r['safe_frac']:.2%} | "
            f"{r['win_rate']:.2%} | "
            f"{r['wins']}/{r['episodes']} |"
        )
    lines.append("")
    lines.append("## Detailed action counts")
    lines.append("")
    lines.append("| Model | HOLD | HIRE | SELL | BUY | PASS | OTHER | Total |")
    lines.append("|---|---|---|---|---|---|---|---|")
    for r in sorted(results, key=lambda x: -x["trade_frac"]):
        model_short = os.path.basename(os.path.dirname(r["model"])) + "/" + os.path.basename(r["model"])
        if "models/" in r["model"]:
            model_short = os.path.basename(r["model"])
        ac = r["action_counts"]
        lines.append(
            f"| `{model_short}` | "
            f"{ac[0]} | {ac[1]} | {ac[2]} | {ac[3]} | {ac[4]} | {ac[-1]} | "
            f"{r['total_actions']} |"
        )
    lines.append("")
    lines.append("## How to read this")
    lines.append("")
    lines.append("- **Trade %** > 5% means the model triggered HIRE/SELL/BUY actions at least sometimes")
    lines.append("- **Safe %** > 95% means the model collapsed to HOLD/PASS only (PASS-every-step bug)")
    lines.append("- **Win rate** = fraction of episodes won (info['won'] at episode end)")
    return "\n".join(lines)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--pattern", default="*",
                        help="Glob pattern (default: all)")
    parser.add_argument("--num_episodes", type=int, default=3)
    parser.add_argument("--opponent", default="random",
                        choices=["random", "trained"])
    parser.add_argument("--output", default=None,
                        help="Write markdown summary to this path")
    args = parser.parse_args()

    models = find_models(args.pattern)
    if not models:
        print(f"No models found matching pattern {args.pattern!r}")
        return

    print(f"Evaluating {len(models)} models × {args.num_episodes} episodes vs {args.opponent} opponent")
    print(f"{'='*70}")

    results = []
    with tempfile.TemporaryDirectory() as npz_dir:
        for m in models:
            t0 = time.time()
            try:
                r = eval_one_model(m, args.num_episodes, args.opponent, npz_dir)
            except Exception as e:
                print(f"  ✗ {os.path.basename(m)}: {e}")
                continue
            elapsed = time.time() - t0
            trade_pct = f"{r['trade_frac']:.2%}"
            win_pct = f"{r['win_rate']:.2%}"
            ac = r["action_counts"]
            print(
                f"  {os.path.basename(m):<40} "
                f"trade={trade_pct:>7}  win={win_pct:>7}  "
                f"[H={ac[0]} HIRE={ac[1]} SELL={ac[2]} BUY={ac[3]} P={ac[4]}]  "
                f"{elapsed:.1f}s"
            )
            results.append(r)

    print()
    md = render_markdown(results, args.opponent, args.num_episodes)
    print(md)

    if args.output:
        with open(args.output, "w") as f:
            f.write(md)
        print(f"\nMarkdown written to {args.output}")


if __name__ == "__main__":
    main()