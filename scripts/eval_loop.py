#!/usr/bin/env python3
"""
Train → Eval → HTML loop for Kagriculture RL.

Each iteration:
  1. Train PPO for ~30 min (configurable steps)
  2. Convert SB3 model → numpy weights
  3. Run local eval: N full episodes with the agent in the Kaggle env
  4. Record action distribution, money trajectory, win/loss
  5. Render an HTML report into `eval_reports/iter_NN_<ts>/report.html`
  6. Decide: if "trade actions" (HIRE+SELL+BUY) fraction > threshold → STOP (learned)
     else → next iteration

Usage:
  python scripts/eval_loop.py                        # default 5 iters, 30 min each
  python scripts/eval_loop.py --max_iters 3         # 3 iters only
  python scripts/eval_loop.py --steps_per_iter 100000  # ~10 min each
"""

import argparse
import json
import os
import shutil
import subprocess
import sys
import tempfile
import time
import zipfile
from datetime import datetime, timedelta

import numpy as np

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


# ============================================================
# Training
# ============================================================

def train_one_iter(args, iter_dir, iter_idx):
    """Train PPO for steps_per_iter; return model.zip path."""
    log_dir = os.path.join(iter_dir, "train_log")
    os.makedirs(log_dir, exist_ok=True)

    model_prefix = os.path.join(iter_dir, "model")
    stdout_path = os.path.join(log_dir, "train.stdout")
    cmd = [
        "python", "-u", "scripts/train.py",
        "--total_steps", str(args.steps_per_iter),
        "--model_path", model_prefix,
        "--log_dir", log_dir,
        "--log_name", "train",
        "--device", args.device,
        "--opponent", args.opponent,
        "--final_eval_episodes", "0",
        "--save_freq", "999999999",
        "--n_steps", "2048",
        "--batch_size", "64",
        "--eval_freq", "50000",
        "--eval_episodes", "5",
        "--ent_coef", str(args.ent_coef),
    ]

    print(f"[iter {iter_idx}] training cmd: {' '.join(cmd)}")
    print(f"[iter {iter_idx}] stdout → {stdout_path}  (tail -f to watch live)")
    t0 = time.time()
    # Stream subprocess stdout/stderr to a file continuously so the user
    # can tail -f the per-iter training progress.
    with open(stdout_path, "w", buffering=1) as logf:
        proc = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                                text=True, bufsize=1)
        try:
            for line in proc.stdout:
                logf.write(line)
        except Exception:
            pass
        proc.wait()
        elapsed = time.time() - t0
        if proc.returncode != 0:
            print(f"[iter {iter_idx}] ✗ training failed (rc={proc.returncode})")
            print(f"--- last 30 lines of {stdout_path} ---")
            with open(stdout_path) as f:
                for line in f.readlines()[-30:]:
                    print(line, end="")
            raise RuntimeError("training failed")

    print(f"[iter {iter_idx}] ✓ training done in {elapsed:.1f}s")
    model_zip = model_prefix + ".zip"
    if not os.path.exists(model_zip):
        raise FileNotFoundError(f"expected {model_zip}, not found")
    return model_zip, elapsed


# ============================================================
# SB3 .zip → policy_np.npz
# ============================================================

def convert_to_npz(model_zip, npz_path):
    """Extract policy.pth from SB3 zip, convert torch tensors → numpy."""
    with tempfile.TemporaryDirectory() as td:
        with zipfile.ZipFile(model_zip) as z:
            z.extractall(td)
        pth = os.path.join(td, "policy.pth")
        if not os.path.exists(pth):
            raise FileNotFoundError(f"policy.pth missing inside {model_zip}")
        import torch
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


# ============================================================
# Local eval
# ============================================================

# Force-register kagriculture by importing our env first
from src.envs.kagriculture_env import KagricultureEnv  # noqa


def eval_local(npz_path, num_episodes, opponent, max_steps=720):
    """Run num_episodes episodes locally; return per-episode action log + summary.

    Sets up a 'submission-style' dir in iter_dir with main.py + npz, imports main,
    runs the kaggle env.
    """
    # Set up a temp submission dir next to npz_path with main.py + policy_np.npz
    sub_dir = os.path.dirname(os.path.abspath(npz_path))
    # Use the project's main.py (the one shipped in submission tarball)
    project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    main_src = os.path.join(project_root, "main.py")
    if not os.path.exists(main_src):
        raise FileNotFoundError(f"main.py not found at {main_src}")

    # Copy main.py and policy_np.npz into iter_dir (matches submission layout)
    dst_main = os.path.join(sub_dir, "main.py")
    if os.path.abspath(main_src) != os.path.abspath(dst_main):
        shutil.copy(main_src, dst_main)
    dst_npz = os.path.join(sub_dir, "policy_np.npz")
    if os.path.abspath(npz_path) != os.path.abspath(dst_npz):
        shutil.copy(npz_path, dst_npz)

    # Reset sys.path and import
    saved_path = sys.path.copy()
    sys.path.insert(0, sub_dir)
    for mod_name in ["main"]:
        if mod_name in sys.modules:
            del sys.modules[mod_name]
    import main  # noqa: E402

    try:
        main.load_actor()

        from kaggle_environments import make
        env = make("kagriculture", debug=False)

        episodes = []
        for ep_i in range(num_episodes):
            env.reset(num_agents=2)
            main._step_count = 0

            action_log = []
            money_log = []
            won_flag = False
            terminated_flag = False
            try:
                while len(action_log) < max_steps:
                    if env.done:
                        break
                    obs = env.state[0].observation
                    action = main.agent(obs, env.configuration)
                    action_log.append(action)

                    if opponent == "random":
                        import random
                        opp_options = [{}, {"market": [["HIRE"]]},
                                       {"market": [["SELL", "WHEAT", 1]]},
                                       {"farmer": ["PASS"]}]
                        opp_action = random.choice(opp_options)
                    else:
                        opp_action = {}

                    env.step([action, opp_action])
                    money_log.append(env.state[0].observation.farms[0].get("money", 0))
            except Exception as e:
                print(f"[eval] episode {ep_i} exception: {e}")
                break

            if env.done:
                try:
                    p0_money = env.state[0].observation.farms[0].get("money", 0)
                    p1_money = env.state[0].observation.farms[1].get("money", 0)
                    won_flag = p0_money > p1_money
                    terminated_flag = True
                except Exception:
                    pass
            episodes.append({
                "index": ep_i,
                "steps": len(action_log),
                "actions": action_log,
                "money_traj": money_log,
                "final_money_p0": money_log[-1] if money_log else 0,
                "won": won_flag,
                "terminated": terminated_flag,
                "truncated": not terminated_flag,
            })
        return episodes
    finally:
        sys.path[:] = saved_path
        for mod_name in ["main"]:
            if mod_name in sys.modules:
                del sys.modules[mod_name]


def action_class(action):
    """Map a Kaggle action dict back to its training index (0-4).

    Supports both Format A (single dict, current main.py) and Format B
    (list of dicts, old main.py) for backward compatibility.
    """
    # Normalize to list-of-dicts for uniform matching
    actions = action if isinstance(action, list) else [action]

    # Empty list/dict = HOLD
    if not actions or all(a == {} for a in actions):
        return 0

    for a in actions:
        if not isinstance(a, dict):
            continue
        market = a.get("market", [])
        farmer = a.get("farmer", [])
        # Each op in market is a list like ["BUY_PRODUCT", "WHEAT", 1]
        # Check op[0] (first element) for the op name
        for op in market:
            if not isinstance(op, list) or not op:
                continue
            op_name = op[0]
            args = op[1:]  # remaining elements are args
            if op_name == "HIRE":
                return 1
            if op_name == "SELL" and "WHEAT" in args:
                return 2
            if op_name == "BUY_PRODUCT" and "WHEAT" in args:
                return 3
        # PASS / other farmer actions
        for op in farmer:
            op_name = op if isinstance(op, str) else (op[0] if op else None)
            if op_name == "PASS":
                return 4

    # Unknown / hands actions → bucket as "other"
    return -1


ACTION_NAMES = {0: "HOLD", 1: "HIRE", 2: "SELL_WHEAT", 3: "BUY_WHEAT", 4: "PASS"}
ACTION_COLORS = {0: "#1f77b4", 1: "#2ca02c", 2: "#ff7f0e", 3: "#d62728", 4: "#9467bd", -1: "#888888"}
TRADE_ACTIONS = {1, 2, 3}  # HIRE, SELL_WHEAT, BUY_WHEAT


def summarize_episodes(episodes):
    """Compute aggregate stats across episodes."""
    total_actions = sum(len(e["actions"]) for e in episodes)
    action_counts = {i: 0 for i in range(-1, 5)}
    for e in episodes:
        for a in e["actions"]:
            action_counts[action_class(a)] += 1

    trade_count = sum(action_counts[a] for a in TRADE_ACTIONS)
    trade_frac = trade_count / total_actions if total_actions > 0 else 0.0

    wins = sum(1 for e in episodes if e["won"])
    win_rate = wins / len(episodes) if episodes else 0.0
    return {
        "total_actions": total_actions,
        "action_counts": action_counts,
        "trade_count": trade_count,
        "trade_frac": trade_frac,
        "wins": wins,
        "episodes": len(episodes),
        "win_rate": win_rate,
    }


# ============================================================
# HTML report
# ============================================================

HTML_TEMPLATE = """<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<title>Eval Report — Iter {iter_idx}</title>
<style>
  body {{ font-family: -apple-system, "Segoe UI", Roboto, sans-serif;
         max-width: 1100px; margin: 24px auto; padding: 0 16px;
         color: #222; background: #fafafa; }}
  h1 {{ margin-bottom: 4px; }}
  .meta {{ color: #666; font-size: 14px; margin-bottom: 24px; }}
  .card {{ background: white; border: 1px solid #ddd; border-radius: 6px;
          padding: 18px 22px; margin-bottom: 16px; box-shadow: 0 1px 3px rgba(0,0,0,0.04); }}
  .card h2 {{ margin-top: 0; font-size: 18px; color: #333; }}
  .verdict {{ font-size: 22px; font-weight: 600; padding: 12px 18px;
              border-radius: 4px; display: inline-block; }}
  .learned {{ background: #d4edda; color: #155724; border: 1px solid #c3e6cb; }}
  .not-learned {{ background: #f8d7da; color: #721c24; border: 1px solid #f5c6cb; }}
  table {{ border-collapse: collapse; width: 100%; font-size: 14px; }}
  th, td {{ padding: 6px 10px; text-align: left; border-bottom: 1px solid #eee; }}
  th {{ background: #f5f5f5; font-weight: 600; }}
  td.num {{ text-align: right; font-family: monospace; }}
  .bar {{ display: inline-block; padding: 3px 8px; color: white;
          font-family: monospace; font-size: 12px; min-width: 40px; }}
  .money-chart {{ font-family: monospace; font-size: 11px; line-height: 1.4;
                  white-space: pre; background: #fafafa; padding: 12px;
                  border: 1px solid #eee; overflow-x: auto; }}
  .episode-block {{ border-left: 3px solid #ddd; padding-left: 12px;
                    margin: 12px 0; }}
  .episode-block.won {{ border-left-color: #28a745; }}
  .episode-block.lost {{ border-left-color: #dc3545; }}
  .actions-table th {{ background: #e8e8e8; }}
  .badge {{ display: inline-block; padding: 2px 8px; border-radius: 10px;
            font-size: 12px; font-weight: 600; margin-left: 8px; }}
  .badge-ok {{ background: #28a745; color: white; }}
  .badge-fail {{ background: #dc3545; color: white; }}
  .legend {{ font-size: 13px; color: #555; }}
  .footer {{ color: #888; font-size: 12px; margin-top: 32px;
             border-top: 1px solid #ddd; padding-top: 12px; }}
</style>
</head>
<body>

<h1>Eval Report — Iteration {iter_idx}</h1>
<div class="meta">
  Generated: {timestamp} &middot;
  Training: {training_duration:.1f}s &middot;
  Episodes: {episodes_run} &middot;
  Total steps: {total_steps} &middot;
  Model: <code>{model_name}</code>
</div>

<div class="card">
  <h2>Verdict</h2>
  <div class="verdict {verdict_class}">
    {verdict_text}
  </div>
  <p style="margin-top: 12px;">
    Trade-action fraction: <b>{trade_frac:.2%}</b>
    (HIRE + SELL_WHEAT + BUY_WHEAT, threshold {trade_threshold:.0%})<br>
    Win rate: <b>{win_rate:.2%}</b> ({wins}/{episodes_run} episodes won)
  </p>
</div>

<div class="card">
  <h2>Action distribution <span style="font-weight: normal; font-size: 13px; color: #666;">(across all {total_steps} actions)</span></h2>
  <table class="actions-table">
    <thead>
      <tr><th>Action</th><th>Idx</th><th>Count</th><th>%</th><th>Visual</th></tr>
    </thead>
    <tbody>
      {action_rows}
    </tbody>
  </table>
  <p class="legend">
    HOLD (idx 0, <code>[]</code>) and PASS (idx 4, <code>farmer:PASS</code>) are
    <i>always legal</i>. HIRE / SELL_WHEAT / BUY_WHEAT need valid game state.
    <b>If HOLD+PASS &gt; 90%, the agent has not learned to trade.</b>
  </p>
</div>

<div class="card">
  <h2>Money trajectory</h2>
  {money_charts}
</div>

<div class="card">
  <h2>Per-episode detail</h2>
  {episode_blocks}
</div>

{comparison_block}

<div class="footer">
  Auto-generated by scripts/eval_loop.py &middot;
  iter_dir: <code>{iter_dir_name}</code>
</div>

</body>
</html>
"""


def render_action_row(i, count, total):
    pct = count / total * 100 if total > 0 else 0
    color = ACTION_COLORS.get(i, "#888")
    name = ACTION_NAMES.get(i, "OTHER")
    is_trade = " <span class='badge badge-ok'>TRADE</span>" if i in TRADE_ACTIONS else ""
    bar_width = max(pct, 1.5)
    return (
        f"<tr>"
        f"<td>{name}{is_trade}</td>"
        f"<td class='num'>{i if i >= 0 else '-'}</td>"
        f"<td class='num'>{count}</td>"
        f"<td class='num'>{pct:.1f}%</td>"
        f"<td><div class='bar' style='background:{color}; width: {bar_width*4}px;'>&nbsp;</div></td>"
        f"</tr>"
    )


def render_money_chart(ep):
    """ASCII-ish sparkline of money over time."""
    money = ep["money_traj"]
    if not money:
        return "<p>(no data)</p>"

    n_samples = 60
    if len(money) <= n_samples:
        samples = money
    else:
        idx = np.linspace(0, len(money) - 1, n_samples).astype(int)
        samples = [money[i] for i in idx]

    lo, hi = min(samples), max(samples)
    span = max(hi - lo, 1)
    bars = "▁▂▃▄▅▆▇█"
    out = []
    for v in samples:
        idx = int((v - lo) / span * (len(bars) - 1))
        out.append(bars[idx])
    line = "".join(out)
    return (
        f"<p><b>Episode {ep['index']}</b> ({'WON' if ep['won'] else 'LOST'}, "
        f"{'terminated' if ep['terminated'] else 'truncated'}, {ep['steps']} steps)</p>"
        f"<div class='money-chart'>min={lo:>6}  max={hi:>6}  final={money[-1]:>6}\n"
        f"{line}</div>"
    )


def render_episode_block(ep):
    """Per-episode summary."""
    action_counts = {i: 0 for i in range(-1, 5)}
    for a in ep["actions"]:
        action_counts[action_class(a)] += 1
    rows = []
    for i in range(-1, 5):
        if action_counts[i] > 0:
            rows.append(f"<tr><td>{ACTION_NAMES.get(i, 'OTHER')}</td>"
                        f"<td class='num'>{action_counts[i]}</td></tr>")
    won_class = "won" if ep["won"] else "lost"
    won_badge = '<span class="badge badge-ok">WON</span>' if ep["won"] else '<span class="badge badge-fail">LOST</span>'
    return (
        f"<div class='episode-block {won_class}'>"
        f"<b>Episode {ep['index']}</b> {won_badge} &middot; "
        f"{ep['steps']} steps &middot; "
        f"{'terminated' if ep['terminated'] else 'truncated'}<br>"
        f"<table style='width:auto; margin-top:8px;'>{''.join(rows)}</table>"
        f"</div>"
    )


def render_comparison_block(prev_iter_dir):
    if not prev_iter_dir or not os.path.exists(prev_iter_dir):
        return ""
    prev_summary_path = os.path.join(prev_iter_dir, "summary.json")
    if not os.path.exists(prev_summary_path):
        return ""
    with open(prev_summary_path) as f:
        prev = json.load(f)
    return (
        "<div class='card'>"
        "<h2>Comparison with previous iteration</h2>"
        f"<table>"
        f"<tr><th>Metric</th><th>This iter</th><th>Prev iter</th><th>Δ</th></tr>"
        f"<tr><td>Trade-action %</td>"
        f"<td class='num'>{prev.get('_current_trade_frac', 0)*100:.1f}%</td>"
        f"<td class='num'>{prev.get('trade_frac', 0)*100:.1f}%</td>"
        f"<td class='num'>{prev.get('_current_trade_frac', 0)*100 - prev.get('trade_frac', 0)*100:+.1f}pp</td></tr>"
        f"<tr><td>Win rate</td>"
        f"<td class='num'>{prev.get('_current_win_rate', 0)*100:.1f}%</td>"
        f"<td class='num'>{prev.get('win_rate', 0)*100:.1f}%</td>"
        f"<td class='num'>{(prev.get('_current_win_rate', 0) - prev.get('win_rate', 0))*100:+.1f}pp</td></tr>"
        f"</table></div>"
    )


def render_html(iter_dir, iter_idx, summary, episodes, training_duration,
                trade_threshold, model_path, prev_iter_dir=None):
    action_rows = "".join(
        render_action_row(i, summary["action_counts"][i], summary["total_actions"])
        for i in [-1, 0, 1, 2, 3, 4]
    )
    money_charts = "".join(render_money_chart(ep) for ep in episodes)
    episode_blocks = "".join(render_episode_block(ep) for ep in episodes)
    comparison_block = render_comparison_block(prev_iter_dir)

    learned = summary["trade_frac"] >= trade_threshold
    verdict_class = "learned" if learned else "not-learned"
    verdict_text = (
        f"✓ LEARNED — Trade-action fraction {summary['trade_frac']:.1%} ≥ threshold {trade_threshold:.0%}"
        if learned else
        f"✗ NOT LEARNED — Trade-action fraction {summary['trade_frac']:.1%} < threshold {trade_threshold:.0%}"
    )

    html = HTML_TEMPLATE.format(
        iter_idx=iter_idx,
        timestamp=datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        training_duration=training_duration,
        episodes_run=summary["episodes"],
        total_steps=summary["total_actions"],
        model_name=os.path.basename(model_path),
        verdict_class=verdict_class,
        verdict_text=verdict_text,
        trade_frac=summary["trade_frac"],
        trade_threshold=trade_threshold,
        win_rate=summary["win_rate"],
        wins=summary["wins"],
        action_rows=action_rows,
        money_charts=money_charts,
        episode_blocks=episode_blocks,
        comparison_block=comparison_block,
        iter_dir_name=os.path.basename(iter_dir),
    )
    html_path = os.path.join(iter_dir, "report.html")
    with open(html_path, "w") as f:
        f.write(html)

    # Also save summary.json (with current iter values baked in for next iter's comparison)
    summary_save = dict(summary)
    summary_save["_current_trade_frac"] = summary["trade_frac"]
    summary_save["_current_win_rate"] = summary["win_rate"]
    with open(os.path.join(iter_dir, "summary.json"), "w") as f:
        json.dump(summary_save, f, indent=2)

    return html_path


# ============================================================
# Main loop
# ============================================================

# ============================================================
# Kaggle-format replay dump
# ============================================================

def save_kaggle_replay(iter_dir, episodes):
    """Save a Kaggle-format replay JSON for each eval episode.

    Format matches what `kaggle competitions episodes --download` returns:
    - steps: list of [player0_step, player1_step]
    - each step has `observation`, `action`, `reward`, `status`, `info`

    For our purposes we save simplified steps (just actions) since we don't
    capture full obs history. Compatible with kaggriculture html_renderer.
    """
    replays_dir = os.path.join(iter_dir, "replays")
    os.makedirs(replays_dir, exist_ok=True)
    for ep in episodes:
        replay = {
            "id": f"iter-{os.path.basename(iter_dir)}-ep-{ep['index']}",
            "rewards": [
                ep.get("final_money_p0", 0),
                ep.get("final_money_p1", 0),
            ],
            "steps": [
                [
                    {
                        "action": a,
                        "reward": 0,
                        "info": {},
                        "observation": {},
                    }
                    for a in ep["actions"]
                ],
                [],  # opponent actions not captured
            ],
        }
        path = os.path.join(replays_dir, f"episode_{ep['index']:02d}_replay.json")
        with open(path, "w") as f:
            json.dump(replay, f, indent=2)


# ============================================================
# Replay HTML — per-step timeline
# ============================================================

REPLAY_HTML_TEMPLATE = """<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<title>Replay — Iter {iter_idx} Episode {ep_idx}</title>
<style>
  body {{ font-family: -apple-system, "Segoe UI", Roboto, sans-serif;
         max-width: 1200px; margin: 24px auto; padding: 0 16px;
         color: #222; background: #fafafa; }}
  h1, h2 {{ margin-bottom: 4px; }}
  .meta {{ color: #666; font-size: 14px; margin-bottom: 24px; }}
  .card {{ background: white; border: 1px solid #ddd; border-radius: 6px;
          padding: 18px 22px; margin-bottom: 16px;
          box-shadow: 0 1px 3px rgba(0,0,0,0.04); }}
  .verdict {{ font-size: 22px; font-weight: 600; padding: 12px 18px;
              border-radius: 4px; display: inline-block; }}
  .won {{ background: #d4edda; color: #155724; border: 1px solid #c3e6cb; }}
  .lost {{ background: #f8d7da; color: #721c24; border: 1px solid #f5c6cb; }}
  table {{ border-collapse: collapse; width: 100%; font-size: 13px; }}
  th, td {{ padding: 4px 8px; text-align: left;
            border-bottom: 1px solid #f0f0f0; }}
  th {{ background: #f5f5f5; font-weight: 600;
        position: sticky; top: 0; }}
  td.num {{ text-align: right; font-family: monospace; }}
  .pill {{ display: inline-block; padding: 2px 8px; border-radius: 10px;
           color: white; font-weight: 600; font-size: 11px;
           font-family: monospace; min-width: 50px; text-align: center; }}
  .pill.trade {{ box-shadow: 0 0 0 2px gold; }}
  .money-up {{ color: #28a745; }}
  .money-down {{ color: #dc3545; }}
  .delta {{ font-size: 10px; font-family: monospace;
            padding: 1px 4px; border-radius: 3px; margin-left: 4px; }}
  .delta.up {{ background: #d4edda; color: #155724; }}
  .delta.down {{ background: #f8d7da; color: #721c24; }}
  .delta.zero {{ background: #f0f0f0; color: #666; }}
  .row-trade {{ background: #fffbe6; }}
  .money-chart {{ font-family: monospace; font-size: 11px; line-height: 1.4;
                  white-space: pre; background: #fafafa; padding: 12px;
                  border: 1px solid #eee; overflow-x: auto;
                  font-size: 14px; }}
  .badge {{ display: inline-block; padding: 2px 8px; border-radius: 10px;
            font-size: 12px; font-weight: 600; margin-left: 8px; }}
  .badge-ok {{ background: #28a745; color: white; }}
  .badge-fail {{ background: #dc3545; color: white; }}
  .footer {{ color: #888; font-size: 12px; margin-top: 32px;
             border-top: 1px solid #ddd; padding-top: 12px; }}
  .legend {{ display: flex; gap: 12px; flex-wrap: wrap;
            font-size: 12px; color: #555; }}
</style>
</head>
<body>

<h1>Episode Replay — Iter {iter_idx}</h1>
<div class="meta">
  Generated: {timestamp} &middot;
  Iter dir: <code>{iter_dir_name}</code> &middot;
  <a href="report.html">View summary report</a>
</div>

<div class="card">
  <h2>Episode {ep_idx} {won_badge}</h2>
  <div class="verdict {won_class}">
    {verdict_text}
  </div>
  <p style="margin-top: 12px;">
    <b>{steps}</b> steps &middot;
    Final money: <b>${final_money:,}</b> &middot;
    Trade actions: <b>{trade_count}</b> &middot;
    HOLD+PASS: <b>{safe_count}</b>
  </p>
</div>

<div class="card">
  <h2>Money trajectory</h2>
  <div class="money-chart">{money_chart}</div>
</div>

<div class="card">
  <h2>Per-step timeline {step_filter_note}</h2>
  <table>
    <thead>
      <tr>
        <th>Step</th>
        <th>Action</th>
        <th>Money</th>
        <th>Δ</th>
        <th>Cumul. reward</th>
      </tr>
    </thead>
    <tbody>
      {timeline_rows}
    </tbody>
  </table>
</div>

<div class="card">
  <h2>Trade events <span style="font-weight:normal; font-size:13px; color:#666;">(HIRE / SELL_WHEAT / BUY_WHEAT)</span></h2>
  {trade_events}
</div>

<div class="card">
  <h2>Legend</h2>
  <div class="legend">
    <span><span class="pill" style="background:#1f77b4;">HOLD</span> idx 0, empty action</span>
    <span><span class="pill" style="background:#2ca02c;">HIRE</span> idx 1, trade action</span>
    <span><span class="pill" style="background:#ff7f0e;">SELL</span> idx 2, trade action</span>
    <span><span class="pill" style="background:#d62728;">BUY</span> idx 3, trade action</span>
    <span><span class="pill" style="background:#9467bd;">PASS</span> idx 4, farmer skip</span>
    <span><span class="pill" style="background:#888888;">OTHER</span> unknown</span>
  </div>
</div>

<div class="footer">
  Auto-generated by scripts/eval_loop.py &middot;
  Iter dir: <code>{iter_dir_name}</code>
</div>

</body>
</html>
"""


def _action_pill_html(action_class):
    """Return color-coded pill HTML for an action class index."""
    color = ACTION_COLORS.get(action_class, "#888")
    name = ACTION_NAMES.get(action_class, "OTHER")
    is_trade = " trade" if action_class in TRADE_ACTIONS else ""
    return f'<span class="pill{is_trade}" style="background:{color};">{name}</span>'


def _action_str_repr(action):
    """Return a short repr of the action for the money-trajectory column."""
    if not action:
        return "—"
    if isinstance(action, list):
        # Truncate for display
        s = str(action)
        return s[:60] + ("…" if len(s) > 60 else "")
    return str(action)[:60]


def render_replay_html(iter_dir, iter_idx, episodes):
    """Render one replay.html per iter containing all episodes as sections.

    Valid single-page HTML with shared <head>/<style>. Each episode is a
    <section id="episode-N"> with header, money sparkline, per-step timeline
    table, and trade events table.
    """
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    # Extract shared style block from template (between <style> and </style>)
    # The template uses {{ }} to escape { } for .format() — unescape them here
    # since we'll use .replace() for body and don't want double braces in CSS.
    style_start = REPLAY_HTML_TEMPLATE.index("<style>") + len("<style>")
    style_end = REPLAY_HTML_TEMPLATE.index("</style>")
    shared_style = REPLAY_HTML_TEMPLATE[style_start:style_end].replace("{{", "{").replace("}}", "}")

    # Extract body content template (after </style>, between <body> and </body>)
    body_marker = "<body>"
    body_end_marker = "</body>"
    body_start = REPLAY_HTML_TEMPLATE.index(body_marker) + len(body_marker)
    body_end = REPLAY_HTML_TEMPLATE.index(body_end_marker)
    body_template = REPLAY_HTML_TEMPLATE[body_start:body_end].strip()

    # Episode navigation
    tab_nav = " | ".join(
        f'<a href="#episode-{ep["index"]}">Episode {ep["index"]}</a>'
        f'{" (WON)" if ep["won"] else " (LOST)"}'
        for ep in episodes
    )

    sections = []
    for ep in episodes:
        ep_idx = ep["index"]
        won = ep["won"]
        won_class = "won" if won else "lost"
        won_badge = '<span class="badge badge-ok">WON</span>' if won else '<span class="badge badge-fail">LOST</span>'
        verdict_text = f"{'Won' if won else 'Lost'} ({ep['steps']} steps, final ${ep.get('final_money_p0', 0):,})"

        # Money chart (sparkline)
        money = ep.get("money_traj", [])
        if money:
            n_samples = 60
            if len(money) <= n_samples:
                samples = money
            else:
                idx = np.linspace(0, len(money) - 1, n_samples).astype(int)
                samples = [money[i] for i in idx]
            lo, hi = min(samples), max(samples)
            span = max(hi - lo, 1)
            bars = "▁▂▃▄▅▆▇█"
            sparkline = "".join(bars[int((v - lo) / span * (len(bars) - 1))] for v in samples)
            money_chart = f"min=${lo:,}  max=${hi:,}  final=${money[-1]:,}\n{sparkline}"
        else:
            money_chart = "(no money data)"

        # Per-step timeline (subsample if too long)
        actions = ep["actions"]
        money = ep.get("money_traj", [])
        step_filter_note = ""
        if len(actions) > 200:
            stride = max(1, len(actions) // 200)
            step_filter_note = f"<span style='color:#888;'>(showing every {stride}th of {len(actions)} steps)</span>"
        else:
            stride = 1

        rows = []
        cumul_reward = 0.0
        last_money = money[0] if money else 0
        for i in range(0, len(actions), stride):
            cls = action_class(actions[i])
            money_now = money[i] if i < len(money) else last_money
            delta = money_now - last_money
            cumul_reward += delta / 10000.0
            if delta > 0:
                delta_class = "up"
                delta_text = f"+{delta:,}"
                money_class = "money-up"
            elif delta < 0:
                delta_class = "down"
                delta_text = f"{delta:,}"
                money_class = "money-down"
            else:
                delta_class = "zero"
                delta_text = "0"
                money_class = ""
            row_class = "row-trade" if cls in TRADE_ACTIONS else ""
            rows.append(
                f"<tr class='{row_class}'>"
                f"<td class='num'>{i}</td>"
                f"<td>{_action_pill_html(cls)} "
                f"<span style='color:#888; font-size:10px; margin-left:4px;'>"
                f"{_action_str_repr(actions[i])}</span></td>"
                f"<td class='num {money_class}'>${money_now:,}</td>"
                f"<td class='num'><span class='delta {delta_class}'>{delta_text}</span></td>"
                f"<td class='num'>{cumul_reward:+.2f}</td>"
                f"</tr>"
            )
            last_money = money_now

        # Trade events section
        trade_events_rows = []
        for i, a in enumerate(actions):
            if action_class(a) in TRADE_ACTIONS:
                money_now = money[i] if i < len(money) else 0
                trade_events_rows.append(
                    f"<tr><td class='num'>{i}</td>"
                    f"<td>{_action_pill_html(action_class(a))}</td>"
                    f"<td>{_action_str_repr(a)}</td>"
                    f"<td class='num'>${money_now:,}</td></tr>"
                )
        if trade_events_rows:
            trade_events_html = (
                "<table><thead><tr><th>Step</th><th>Action</th><th>Raw</th>"
                "<th>Money</th></tr></thead><tbody>"
                + "".join(trade_events_rows)
                + "</tbody></table>"
            )
        else:
            trade_events_html = '<p style="color:#888;">No trade actions in this episode — agent only emitted HOLD/PASS.</p>'

        # Count actions for this episode
        cls_counts = {i: 0 for i in range(-1, 5)}
        for a in actions:
            cls_counts[action_class(a)] += 1
        trade_count = sum(cls_counts[a] for a in TRADE_ACTIONS)
        safe_count = cls_counts[0] + cls_counts[4]

        # Build the section by filling body template (use .replace() not .format()
        # because the body template contains CSS { } that we don't want escaped)
        section_html = (
            body_template
            .replace("{iter_idx}", str(iter_idx))
            .replace("{ep_idx}", str(ep_idx))
            .replace("{won_badge}", won_badge)
            .replace("{won_class}", won_class)
            .replace("{verdict_text}", verdict_text)
            .replace("{steps}", str(ep["steps"]))
            .replace("{final_money:,}", f"{ep.get('final_money_p0', 0):,}")
            .replace("{trade_count}", str(trade_count))
            .replace("{safe_count}", str(safe_count))
            .replace("{money_chart}", money_chart)
            .replace("{step_filter_note}", step_filter_note)
            .replace("{timeline_rows}", "".join(rows))
            .replace("{trade_events}", trade_events_html)
            .replace("{timestamp}", timestamp)
            .replace("{iter_dir_name}", os.path.basename(iter_dir))
        )
        sections.append(f'<section id="episode-{ep_idx}">\n{section_html}\n</section>')

    # Assemble full document with shared head/style
    full_html = (
        "<!DOCTYPE html>\n"
        "<html lang=\"en\">\n"
        "<head>\n"
        "<meta charset=\"utf-8\">\n"
        f"<title>Replay — Iter {iter_idx}</title>\n"
        f"<style>\n{shared_style}\n</style>\n"
        "</head>\n"
        "<body style=\"font-family:-apple-system,sans-serif; max-width:1200px; "
        "margin:24px auto; padding:0 16px;\">\n"
        f"<h1>Episode Replays — Iter {iter_idx}</h1>\n"
        f"<div style=\"color:#666; font-size:14px; margin-bottom:24px;\">"
        f"Generated: {timestamp} &middot; "
        f"<a href=\"report.html\">View summary report</a></div>\n"
        "<div style=\"background:white; border:1px solid #ddd; border-radius:6px; "
        "padding:18px 22px; margin-bottom:16px;\">\n"
        f"<h2 style=\"margin-top:0;\">Episode navigation</h2>\n{tab_nav}\n"
        "</div>\n"
        + "\n<hr style=\"margin: 32px 0;\">\n".join(sections)
        + "\n</body>\n</html>\n"
    )

    out_path = os.path.join(iter_dir, "replay.html")
    with open(out_path, "w") as f:
        f.write(full_html)
    return out_path


# ============================================================
# Main loop
# ============================================================

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--max_iters", type=int, default=10)
    parser.add_argument("--steps_per_iter", type=int, default=280_000,
                        help="~30 min at 155 fps on V100")
    parser.add_argument("--device", type=str, default="cuda",
                        help="Device name; pass to train.py. Use CUDA_VISIBLE_DEVICES env var to pin GPU.")
    parser.add_argument("--opponent", type=str, default="random",
                        choices=["random", "trained"])
    parser.add_argument("--ent_coef", type=float, default=0.04,
                        help="PPO entropy coefficient (Phase 1: 0.04; was 0.01)")
    parser.add_argument("--reward_type", type=str, default="dense",
                        choices=["dense", "sparse"])
    parser.add_argument("--trade_threshold", type=float, default=0.05,
                        help="Stop when HIRE+SELL+BUY fraction ≥ this")
    parser.add_argument("--num_eval_episodes", type=int, default=3)
    parser.add_argument("--reports_dir", type=str, default="eval_reports")
    parser.add_argument("--skip_train", action="store_true",
                        help="Skip training, use existing model (.zip in models/ or --existing_model)")
    parser.add_argument("--existing_model", type=str, default=None,
                        help="Path to specific model .zip to use when --skip_train")
    args = parser.parse_args()

    os.makedirs(args.reports_dir, exist_ok=True)
    # Always start fresh for this run
    # (Don't wipe — leave old iters for comparison)

    learned = False
    prev_iter_dir = None

    print(f"\n{'='*60}")
    print(f"Kagriculture RL — Train/Eval/HTML Loop")
    print(f"{'='*60}")
    print(f"  max_iters:        {args.max_iters}")
    print(f"  steps_per_iter:   {args.steps_per_iter:,}")
    print(f"  device:           {args.device}")
    print(f"  opponent:         {args.opponent}")
    print(f"  reward_type:      {args.reward_type}")
    print(f"  trade_threshold:  {args.trade_threshold:.0%}")
    print(f"  num_eval_episodes:{args.num_eval_episodes}")
    print(f"  reports_dir:      {args.reports_dir}")
    print(f"{'='*60}\n")

    for i in range(1, args.max_iters + 1):
        iter_start = time.time()
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        iter_dir = os.path.join(args.reports_dir, f"iter_{i:02d}_{timestamp}")
        os.makedirs(iter_dir, exist_ok=True)

        print(f"\n{'='*60}")
        print(f"[{datetime.now().isoformat()}] ITERATION {i}/{args.max_iters}")
        print(f"  iter_dir: {iter_dir}")
        print(f"{'='*60}")

        # 1. Train (unless skipped)
        if args.skip_train:
            # Use the most recently modified .zip in models/ unless --existing_model given
            if args.existing_model:
                model_zip = args.existing_model
            else:
                candidates = sorted(
                    [os.path.join("models", f) for f in os.listdir("models") if f.endswith(".zip")],
                    key=lambda p: os.path.getmtime(p),
                    reverse=True,
                )
                if not candidates:
                    raise FileNotFoundError("--skip_train set but no .zip found in models/")
                model_zip = candidates[0]
            # Copy into iter_dir so all artifacts are co-located
            import shutil
            shutil.copy(model_zip, os.path.join(iter_dir, "model.zip"))
            model_zip = os.path.join(iter_dir, "model.zip")
            training_duration = 0.0
        else:
            model_zip, training_duration = train_one_iter(args, iter_dir, i)

        # 2. Convert to npz
        npz_path = os.path.join(iter_dir, "policy_np.npz")
        convert_to_npz(model_zip, npz_path)

        # 3. Local eval
        episodes = eval_local(npz_path, args.num_eval_episodes, args.opponent)
        summary = summarize_episodes(episodes)

        # Save raw eval data
        with open(os.path.join(iter_dir, "episodes.json"), "w") as f:
            json.dump(episodes, f, indent=2)

        # Save Kaggle-format replay (raw episode state) — useful for cross-check
        # with kaggle-environments' official HTML renderer
        save_kaggle_replay(iter_dir, episodes)

        # 4. Render HTML reports
        html_path = render_html(
            iter_dir=iter_dir,
            iter_idx=i,
            summary=summary,
            episodes=episodes,
            training_duration=training_duration,
            trade_threshold=args.trade_threshold,
            model_path=model_zip,
            prev_iter_dir=prev_iter_dir,
        )

        # 5. Render per-step replay timeline HTML (debug surface)
        replay_html_path = render_replay_html(iter_dir, i, episodes)
        print(f"  HTML report:   {html_path}")
        print(f"  HTML replay:   {replay_html_path}")
        print(f"  Kaggle replay: {os.path.join(iter_dir, 'replays')}")

        elapsed = time.time() - iter_start
        print(f"\n[{datetime.now().isoformat()}] iter {i:>2} done in {elapsed:.1f}s")
        print(f"  trade_frac={summary['trade_frac']:.2%}  "
              f"win_rate={summary['win_rate']:.2%}  "
              f"action_dist={dict((k, v) for k, v in summary['action_counts'].items() if v > 0)}")
        print(f"  HTML: {html_path}")

        # 5. Stop condition
        if summary["trade_frac"] >= args.trade_threshold:
            print(f"\n✓ LEARNED at iteration {i}!")
            print(f"  trade_frac = {summary['trade_frac']:.2%} >= threshold {args.trade_threshold:.0%}")
            print(f"  open: {html_path}")
            learned = True
            break
        else:
            print(f"  not learned yet (trade_frac={summary['trade_frac']:.2%} < {args.trade_threshold:.0%}), continuing...")

        prev_iter_dir = iter_dir

    print(f"\n{'='*60}")
    if learned:
        print(f"✓ Loop complete — model learned in {i} iteration(s)")
    else:
        print(f"✗ Loop complete — max iters ({args.max_iters}) reached without learning")
    print(f"{'='*60}\n")


if __name__ == "__main__":
    main()