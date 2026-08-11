#!/usr/bin/env python3
"""
Render animated HTML replay of a saved PPO model using kaggle_environments'
built-in HTML renderer (env.render(mode="html")).

This is the SAME renderer Kaggle itself uses for replays in competitions.
The output is a single self-contained HTML file (20-25 MB) with:
  - Board visualization (10x10 grid)
  - Step-by-step animation
  - Action history
  - Money trajectory
  - Click-to-jump-to-step

Usage:
  python scripts/render_animated_html.py \
      --model_path models/ppo_v5_short.zip \
      --opponent random \
      --output eval_reports/my_animated.html
"""
import argparse
import os
import shutil
import sys
import tempfile
import zipfile

import numpy as np
import torch

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


def convert_to_npz(model_zip, npz_path):
    """SB3 .zip → numpy policy_np.npz (6 keys)."""
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


class SimpleActorNP:
    """Numpy inference matching KagricultureEnv.ObsProcessor.process output."""
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
        return int(np.argmax(self.forward(obs))) if deterministic else self.forward(obs)


ACTION_NAMES = {0: "HOLD", 1: "HIRE", 2: "SELL_WHEAT", 3: "BUY_WHEAT", 4: "PASS"}


def action_to_kaggle(action_idx, money, wheat):
    """Map internal action index (0-4) to Kaggle action dict."""
    if action_idx == 0:
        return {}  # HOLD
    elif action_idx == 1 and money >= 100:  # HIRE (legal gate)
        return {"market": [["HIRE"]]}
    elif action_idx == 2 and wheat > 0:  # SELL_WHEAT (legal gate)
        return {"market": [["SELL", "WHEAT", 1]]}
    elif action_idx == 3 and money >= 50:  # BUY_WHEAT (legal gate, simplified)
        return {"market": [["BUY_PRODUCT", "WHEAT", 1]]}
    elif action_idx == 4:
        return {"farmer": ["PASS"]}
    else:
        # Invalid action → fall back to HOLD
        return {}


def obs_to_32dim(raw_obs, step_count):
    """Convert Kaggle raw observation → 32-dim vector matching training."""
    farm = raw_obs.farms[0]
    private = raw_obs.private
    shed = private.shed if isinstance(private.shed, dict) else {}

    obs = np.zeros(32, dtype=np.float32)
    obs[0] = step_count / 720.0
    obs[1] = raw_obs.day / 30.0
    money = farm.get("money", 0)
    obs[2] = min(money, 100000) / 100000.0

    market = raw_obs.market
    prices = market.get("prices", {}) if hasattr(market, "get") else market.prices
    inventory = market.get("inventory", {}) if hasattr(market, "get") else market.inventory
    obs[3] = prices.get("WHEAT", 0) / 100.0
    obs[4] = prices.get("FERTILIZER", 0) / 100.0
    obs[5] = prices.get("MELON", 0) / 100.0
    obs[6] = prices.get("STRAWBERRY", 0) / 100.0
    obs[7] = inventory.get("WHEAT", 0) / 1000.0
    obs[8] = inventory.get("FERTILIZER", 0) / 1000.0
    obs[9] = inventory.get("MELON", 0) / 1000.0
    obs[10] = inventory.get("STRAWBERRY", 0) / 1000.0

    obs[11] = 0.0
    obs[12] = 0.0
    obs[13] = 0.0
    obs[14] = 0.0
    obs[15] = 0.0
    obs[16] = 0.0
    obs[17] = 0.0

    obs[21] = len(farm.get("hands", [])) / 5.0
    obs[22] = min(money, 100000) / 100000.0
    obs[23] = shed.get("WHEAT", 0) / 1000.0
    obs[24] = shed.get("FERTILIZER", 0) / 100.0
    obs[25] = farm.get("hires_today", 0) / 3.0

    if len(raw_obs.farms) > 1:
        opp_farm = raw_obs.farms[1]
        obs[26] = min(opp_farm.get("money", 0), 100000) / 100000.0

    return obs, money, shed.get("WHEAT", 0)


class TrainedAgent:
    """Wrap SimpleActorNP into a Kaggle-compatible agent(obs, config)."""
    def __init__(self, actor):
        self.actor = actor
        self.step_count = 0

    def __call__(self, obs, config=None):
        # Kaggle env reset returns obs as a dict with 'obs' key
        raw_obs = obs.get("obs", obs) if isinstance(obs, dict) else obs
        # Extract actual Struct from raw_obs
        if hasattr(raw_obs, "observation"):
            raw_obs = raw_obs.observation
        obs32, money, wheat = obs_to_32dim(raw_obs, self.step_count)
        self.step_count += 1
        action_idx = self.actor.get_action(obs32, deterministic=True)
        return action_to_kaggle(action_idx, money, wheat)


class RandomAgent:
    """Random opponent for testing."""
    def __init__(self, seed=42):
        import random
        self.rng = random.Random(seed)

    def __call__(self, obs, config=None):
        return self.rng.choice([
            {},
            {"market": [["HIRE"]]},
            {"market": [["SELL", "WHEAT", 1]]},
            {"farmer": ["PASS"]},
        ])


def render(model_zip, opponent, output_html, seed=42):
    """Run a match and render animated HTML."""
    # 1. Convert model.zip → npz
    with tempfile.TemporaryDirectory() as td:
        npz_path = os.path.join(td, "policy_nnp.npz")
        convert_to_npz(model_zip, npz_path)
        actor = SimpleActorNP(npz_path)

        # 2. Create agents
        p0 = TrainedAgent(actor)
        if opponent == "random":
            p1 = RandomAgent(seed=seed)
        else:
            raise NotImplementedError(f"opponent={opponent} not yet supported in animated mode")

        # 3. Run match with debug=True (needed for HTML replay)
        # Register kaggriculture env first (triggered by importing our env)
        from src.envs.kagriculture_env import KagricultureEnv  # noqa
        from kaggle_environments import make
        env = make(
            "kagriculture",
            configuration={"episodeSteps": 720, "seed": seed},
            debug=True,
        )
        print(f"Running match: trained model (P0) vs {opponent} (P1), seed={seed}...")
        env.run([p0, p1])

        # 4. Render HTML (kaggle_environments built-in renderer)
        print("Rendering animated HTML...")
        html = str(env.render(
            mode="html",
            playerNames=["Trained PPO", f"{opponent} opp"],
        ))
        # Note: render() returns the same env object — html is str

        # 5. Save
        with open(output_html, "w") as f:
            f.write(html)
        size_mb = os.path.getsize(output_html) / 1024 / 1024
        print(f"✓ wrote {output_html} ({size_mb:.1f} MB)")

        # 6. Print final stats
        final = env.steps[-1]
        p0_reward = float(final[0].reward or 0)
        p1_reward = float(final[1].reward or 0)
        result = "P0 (trained) win" if p0_reward > p1_reward else (
            "P1 (random) win" if p1_reward > p0_reward else "tie"
        )
        print(f"Result: P0={p0_reward:.0f} P1={p1_reward:.0f} → {result}")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--model_path", required=True)
    parser.add_argument("--opponent", default="random", choices=["random"])
    parser.add_argument("--output", required=True)
    parser.add_argument("--seed", type=int, default=42)
    args = parser.parse_args()
    render(args.model_path, args.opponent, args.output, args.seed)


if __name__ == "__main__":
    main()