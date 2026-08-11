#!/usr/bin/env python3
"""
Kagriculture RL — PPO training script.

Trains a PPO agent against the Kagriculture Gym env. Designed for the project's
Gate 1–4 evaluation flow (.claude/WORKFLOW.md):

  - EvalCallback tracks win-rate via info["won"] (NOT accumulated reward)
  - Periodic checkpoints survive crashes / interrupts
  - TensorBoard logs under --log_dir
  - Final evaluation produces a win-rate / mean-reward report

Usage:
  python scripts/train.py --total_steps 2500000
  python scripts/train.py --total_steps 1000000 --opponent random
  python scripts/train.py --resume_from models/ppo_v5.zip --total_steps 5000000
"""

import os
import sys
import time
import argparse
from datetime import datetime, timezone, timedelta

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from stable_baselines3 import PPO
from stable_baselines3.common.callbacks import (
    BaseCallback,
    CheckpointCallback,
)
from stable_baselines3.common.vec_env import SubprocVecEnv
from sb3_contrib import MaskablePPO
from sb3_contrib.common.maskable.policies import MaskableActorCriticPolicy
from sb3_contrib.common.wrappers import ActionMasker

from src.envs.kagriculture_env import KagricultureEnv


# ----------------------------------------------------------------------
# Logging helpers
# ----------------------------------------------------------------------

class DualLogger:
    """Write to stdout AND a log file in lockstep."""

    def __init__(self, path: str):
        os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
        self.path = path
        self._fh = open(path, "a", buffering=1)  # line-buffered

    def _ts(self) -> str:
        return datetime.now(timezone(timedelta(hours=8))).strftime("%Y-%m-%d %H:%M:%S")

    def log(self, msg: str = "") -> None:
        ts = self._ts(); print(f"[{ts}] {msg}")
        self._fh.write(f"[{ts}] {msg}" + "\n")

    def close(self) -> None:
        self._fh.close()


class RewardMonitor(BaseCallback):
    """Tracks per-episode reward / length from SB3's Monitor-wrapped info dict."""

    def __init__(self, log_every: int = 10, verbose: int = 1):
        super().__init__(verbose)
        self.log_every = log_every
        self.episode_rewards: list[float] = []
        self.episode_lengths: list[int] = []
        self._episodes_since_log = 0

    def _on_step(self) -> bool:
        infos = self.locals.get("infos", [])
        for info in infos:
            if "episode" in info:
                self.episode_rewards.append(info["episode"]["r"])
                self.episode_lengths.append(info["episode"]["l"])
                self._episodes_since_log += 1
                if self.verbose and self._episodes_since_log >= self.log_every:
                    n = self.log_every
                    mean_r = sum(self.episode_rewards[-n:]) / n
                    mean_l = sum(self.episode_lengths[-n:]) / n
                    print(
                        f"  [reward] last {n} eps: "
                        f"mean_r={mean_r:.3f} mean_len={mean_l:.0f} "
                        f"(step={self.num_timesteps})"
                    )
                    self._episodes_since_log = 0
        return True


class WinRateEvalCallback(BaseCallback):
    """
    Periodic win-rate evaluator.

    Runs N full episodes against the eval env and reports win-rate (via
    info["won"], set by KagricultureEnv when the episode ends). IMPORTANT:
    win/loss must come from info["won"] — accumulated dense reward is not
    a reliable win signal in this env (see log-session.md, Bug #1).
    """

    def __init__(
        self,
        eval_env,
        n_eval_episodes: int = 10,
        eval_freq: int = 10_000,
        best_model_save_path: str | None = None,
        log_path: str | None = None,
        eval_csv_name: str = "eval.csv",
        verbose: int = 1,
    ):
        super().__init__(verbose)
        self.eval_env = eval_env
        self.n_eval_episodes = n_eval_episodes
        self.eval_freq = eval_freq
        self.best_model_save_path = best_model_save_path
        self.log_path = log_path
        self.best_win_rate = -1.0
        self._next_eval_step = eval_freq
        self._start_time: float | None = None  # wall-clock anchor for FPS

        if best_model_save_path:
            os.makedirs(best_model_save_path, exist_ok=True)
        if log_path:
            os.makedirs(log_path, exist_ok=True)
            self._log_fh = open(os.path.join(log_path, eval_csv_name), "a", buffering=1)
            if self._log_fh.tell() == 0:
                self._log_fh.write("step,win_rate,mean_reward,fps\n")
        else:
            self._log_fh = None

    def _ts(self) -> str:
        return datetime.now(timezone(timedelta(hours=8))).strftime("%Y-%m-%d %H:%M:%S")

    def _on_step(self) -> bool:
        if self._start_time is None:
            self._start_time = time.time()
        if self.num_timesteps < self._next_eval_step:
            return True
        self._next_eval_step += self.eval_freq
        self._evaluate()
        return True

    def _evaluate(self) -> None:
        wins = 0
        total_reward = 0.0
        for _ in range(self.n_eval_episodes):
            obs = self.eval_env.reset()
            done = False
            ep_reward = 0.0
            last_info: dict = {}
            while not done:
                action, _ = self.model.predict(obs, deterministic=True)
                obs, reward, done, last_info = self.eval_env.step(action)
                ep_reward += float(reward[0]) if hasattr(reward, "__len__") else float(reward)
            total_reward += ep_reward
            if last_info[0].get("won", False):
                wins += 1

        win_rate = float(wins) / float(self.n_eval_episodes)
        mean_reward = float(total_reward) / float(self.n_eval_episodes)

        # Wall-clock FPS anchored at first step (more reliable than SB3's
        # `time/fps` logger, which is updated per-rollout, not per-step).
        elapsed = max(time.time() - (self._start_time or time.time()), 1e-6)
        fps = int(self.num_timesteps / elapsed)

        msg = (
            f"[eval @ {self.num_timesteps:,} steps] "
            f"win_rate={win_rate:.2%} ({wins}/{self.n_eval_episodes}) "
            f"mean_reward={mean_reward:.4f}  "
            f"fps={fps}"
        )
        ts = self._ts(); print(f"[{ts}] {msg}")
        if self._log_fh is not None:
            self._log_fh.write(
                f"{self.num_timesteps},{win_rate:.6f},{mean_reward:.6f},{fps}\n"
            )

        if self.best_model_save_path and win_rate > self.best_win_rate:
            self.best_win_rate = win_rate
            save_path = os.path.join(self.best_model_save_path, "best_model.zip")
            self.model.save(save_path)
            print(f"  ✓ New best (win_rate={win_rate:.2%}) → {save_path}")

    def close(self) -> None:
        if self._log_fh is not None:
            self._log_fh.close()


# ----------------------------------------------------------------------
# Argument parsing
# ----------------------------------------------------------------------

def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Train Kaggriculture PPO agent")
    p.add_argument("--total_steps", type=int, default=2_500_000)
    p.add_argument("--model_path", type=str, default=None,
                   help="Path to save final model. Default: models/ppo_<timestamp>")
    p.add_argument("--log_dir", type=str, default="log",
                   help="Directory for the run's log files. Default: log/ "
                        "(matches project convention; e.g. log/train_5M.log)")
    p.add_argument("--log_name", type=str, default=None,
                   help="Base name for this run's files. Default: "
                        "train_<timestamp> inside --log_dir")
    p.add_argument("--device", type=str, default="cuda",
                   choices=["cuda", "cpu", "auto"])
    p.add_argument("--opponent", type=str, default="random",  # Phase 1: start easy
                   choices=["random", "trained"])
    p.add_argument("--opponent_model_path", type=str, default=None,
                   help="Path to opponent RF model (only if --opponent trained)")
    # PPO hyperparameters
    p.add_argument("--learning_rate", type=float, default=3e-4)
    p.add_argument("--n_steps", type=int, default=2048)
    p.add_argument("--batch_size", type=int, default=64)
    p.add_argument("--n_epochs", type=int, default=10)
    p.add_argument("--gamma", type=float, default=0.99)
    p.add_argument("--gae_lambda", type=float, default=0.95)
    p.add_argument("--clip_range", type=float, default=0.2)
    p.add_argument("--ent_coef", type=float, default=0.04)  # Phase 1: more exploration
    p.add_argument("--vf_coef", type=float, default=0.5)
    p.add_argument("--max_grad_norm", type=float, default=0.5)
    # Eval / checkpoint cadence
    p.add_argument("--eval_freq", type=int, default=10_000)
    p.add_argument("--eval_episodes", type=int, default=10)
    p.add_argument("--save_freq", type=int, default=100_000)
    # Misc
    p.add_argument("--seed", type=int, default=None)
    p.add_argument("--resume_from", type=str, default=None,
                   help="Resume from a saved .zip model")
    p.add_argument("--final_eval_episodes", type=int, default=50,
                   help="Episodes for the post-training evaluation")
    return p.parse_args()


# ----------------------------------------------------------------------
# Final evaluation
# ----------------------------------------------------------------------

def final_eval(model, env, n_episodes: int, logger: DualLogger) -> tuple[float, float]:
    """Run N episodes, return (win_rate, mean_reward)."""
    wins = 0
    total_reward = 0.0
    for ep in range(n_episodes):
        obs = env.reset()
        done = False
        ep_reward = 0.0
        last_info: dict = {}
        while not done:
            action, _ = model.predict(obs, deterministic=True)
            obs, reward, done, last_info = env.step(action)
            ep_reward += float(reward[0]) if hasattr(reward, "__len__") else float(reward)
        total_reward += ep_reward
        if last_info[0].get("won", False):
            wins += 1
        if (ep + 1) % 10 == 0:
            logger.log(f"  eval progress: {ep + 1}/{n_episodes}")
    return float(wins) / float(n_episodes), float(total_reward) / float(n_episodes)


# ----------------------------------------------------------------------
# Main
# ----------------------------------------------------------------------

def main() -> None:
    args = parse_args()

    # Default paths
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    if args.model_path is None:
        args.model_path = f"models/ppo_{timestamp}"
    if args.log_name is None:
        args.log_name = f"train_{timestamp}"

    os.makedirs(os.path.dirname(args.model_path) or "models", exist_ok=True)
    os.makedirs(args.log_dir, exist_ok=True)
    checkpoint_dir = os.path.join(args.log_dir, f"{args.log_name}_checkpoints")
    os.makedirs(checkpoint_dir, exist_ok=True)

    logger = DualLogger(os.path.join(args.log_dir, f"{args.log_name}.log"))
    try:
        _run(args, logger, checkpoint_dir)
    finally:
        logger.close()


def _run(args: argparse.Namespace, logger: DualLogger, checkpoint_dir: str) -> None:
    logger.log("=" * 64)
    logger.log("Kagriculture RL — PPO training")
    logger.log("=" * 64)
    logger.log(f"Started:           {datetime.now().isoformat()}")
    logger.log(f"Total steps:       {args.total_steps:,}")
    logger.log(f"Model path:        {args.model_path}")
    logger.log(f"Log dir:           {args.log_dir}")
    logger.log(f"Device:            {args.device}")
    logger.log(f"Opponent:          {args.opponent}"
               + (f" ({args.opponent_model_path})" if args.opponent_model_path else ""))
    logger.log(f"PPO:               lr={args.learning_rate}  n_steps={args.n_steps}"
               f"  batch={args.batch_size}  n_epochs={args.n_epochs}")
    logger.log(f"Eval:              every {args.eval_freq:,} steps, "
               f"{args.eval_episodes} eps/eval")
    logger.log(f"Resume from:       {args.resume_from or '(fresh)'}")
    logger.log("=" * 64)

    # Env — share one kaggle_env between train and eval so the trained-RF
    # opponent sees the same initial state in both. Without sharing, each
    # env's `make("kagriculture")` produces a different random initial farm
    # → opponent plays differently → eval is unreliable.
    logger.log(f"[setup] creating shared kaggle_env")
    from kaggle_environments import make as _kaggle_make
    shared_kaggle_env = _kaggle_make("kagriculture", debug=False)

    def _make_env(opponent, kaggle_env):
        def _init():
            env = KagricultureEnv(
                opponent=opponent,
                reward_type="dense",
                opponent_model_path=args.opponent_model_path,
                kaggle_env=kaggle_env,
            )
            env = ActionMasker(env, lambda e: e.action_masks())
            return env
        return _init

    logger.log(f"[setup] creating train env (opponent={args.opponent})")
    train_env = SubprocVecEnv([_make_env(args.opponent, shared_kaggle_env) for _ in range(16)])
    logger.log(f"[setup] creating eval env (sharing kaggle_env)")
    eval_env = SubprocVecEnv([_make_env(args.opponent, shared_kaggle_env)])

    # Model
    if args.resume_from:
        logger.log(f"[setup] resuming MaskablePPO from {args.resume_from}")
        model = MaskablePPO.load(args.resume_from, env=train_env, device=args.device)
    else:
        logger.log(f"[setup] creating fresh MaskablePPO (MaskableActorCriticPolicy)")
        model = MaskablePPO(
            policy=MaskableActorCriticPolicy,
            env=train_env,
            device=args.device,
            verbose=1,
            learning_rate=args.learning_rate,
            n_steps=args.n_steps,
            batch_size=args.batch_size,
            n_epochs=args.n_epochs,
            gamma=args.gamma,
            gae_lambda=args.gae_lambda,
            clip_range=args.clip_range,
            ent_coef=args.ent_coef,
            vf_coef=args.vf_coef,
            max_grad_norm=args.max_grad_norm,
            seed=args.seed,
        )

    # Sanity-check: actually confirm the policy lives on the requested device.
    try:
        import torch
        param_device = next(model.policy.parameters()).device
        n_params = sum(p.numel() for p in model.policy.parameters())
        logger.log(
            f"[setup] policy on device={param_device}  "
            f"({n_params:,} parameters)  "
            f"cuda_available={torch.cuda.is_available()}"
        )
        if args.device.startswith("cuda") and param_device.type != "cuda":
            logger.log(
                f"[setup] ⚠ requested {args.device} but policy is on {param_device} — "
                f"check CUDA_VISIBLE_DEVICES / driver"
            )
    except Exception as e:
        logger.log(f"[setup] device probe failed: {e}")

    # Callbacks
    win_rate_cb = WinRateEvalCallback(
        eval_env=eval_env,
        n_eval_episodes=args.eval_episodes,
        eval_freq=args.eval_freq,
        best_model_save_path=os.path.join(args.log_dir, f"{args.log_name}_best"),
        log_path=args.log_dir,
        eval_csv_name=f"{args.log_name}_eval.csv",
        verbose=1,
    )
    reward_cb = RewardMonitor(log_every=10, verbose=1)
    checkpoint_cb = CheckpointCallback(
        save_freq=args.save_freq,
        save_path=checkpoint_dir,
        name_prefix="ppo",
        verbose=1,
    )
    callbacks = [win_rate_cb, reward_cb, checkpoint_cb]

    # Train
    logger.log(f"[train] starting PPO.learn(total_timesteps={args.total_steps:,})")
    start = time.time()
    interrupted = False
    try:
        model.learn(
            total_timesteps=args.total_steps,
            callback=callbacks,
            tb_log_name="PPO",
            reset_num_timesteps=(args.resume_from is None),
            progress_bar=False,
        )
    except KeyboardInterrupt:
        interrupted = True
        logger.log("\n[train] KeyboardInterrupt — saving snapshot and exiting")
    finally:
        elapsed = time.time() - start
        fps = max(1, int(model.num_timesteps / max(elapsed, 1e-6)))

        logger.log("")
        logger.log("=" * 64)
        logger.log("Training summary")
        logger.log("=" * 64)
        logger.log(f"Steps completed:   {model.num_timesteps:,}")
        logger.log(f"Wall time:         {elapsed/3600:.2f}h")
        logger.log(f"Throughput:        {fps} steps/s")
        logger.log(f"Best win rate:     {win_rate_cb.best_win_rate:.2%}")

        # Save final (or interrupted) snapshot
        final_path = args.model_path + ("_interrupted" if interrupted else "")
        model.save(final_path)
        logger.log(f"Model saved:       {final_path}.zip")

        # Final evaluation
        if not interrupted and args.final_eval_episodes > 0:
            logger.log("")
            logger.log(f"[final-eval] running {args.final_eval_episodes} episodes…")
            win_rate, mean_reward = final_eval(
                model, eval_env, args.final_eval_episodes, logger,
            )
            logger.log(f"[final-eval] win_rate={win_rate:.2%}  "
                       f"mean_reward={mean_reward:.4f}")
            # Persist final eval alongside the model
            try:
                with open(args.model_path + ".eval.txt", "w") as f:
                    f.write(f"win_rate={win_rate:.6f}\n")
                    f.write(f"mean_reward={mean_reward:.6f}\n")
                    f.write(f"n_episodes={args.final_eval_episodes}\n")
                    f.write(f"total_timesteps={model.num_timesteps}\n")
            except OSError as e:
                logger.log(f"[final-eval] could not write eval file: {e}")

        eval_env.close()
        train_env.close()

        if interrupted:
            sys.exit(130)


if __name__ == "__main__":
    main()