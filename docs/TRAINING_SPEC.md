# Training Code Specification — Kagriculture RL

> **Date**: 2026-08-11
> **Status**: Live spec — reflects the current `src/`, `scripts/train.py`, `scripts/eval_loop.py` (post P0-1/2/3/4 + P1-5 fixes)
> **Audience**: Future Claude instances picking up training, debugging, or extending the loop

This document describes how the current training pipeline works end-to-end. For a project-level orientation, see [`CLAUDE.md`](../CLAUDE.md). For bug-fix history, see [`log-session.md`](../log-session.md).

---

## 1. Overview — three scripts, one closed loop

```
┌────────────────────────────────────────────────────────────────────┐
│                  scripts/eval_loop.py  (master)                   │
│                                                                    │
│  for iter in 1..max_iters:                                        │
│    ┌─────────────────────────────────────────────────────────┐     │
│    │ 1. train PPO  (--steps_per_iter, default 280k = 30min) │     │
│    │    └─► subprocess: scripts/train.py                   │     │
│    │         produces model.zip + train_log/{train.log,    │     │
│    │         train_eval.csv, train_best/, train_checkpoints/}│    │
│    ├─────────────────────────────────────────────────────────┤     │
│    │ 2. convert model.zip → policy_np.npz (6 SB3 keys)    │     │
│    ├─────────────────────────────────────────────────────────┤     │
│    │ 3. local eval: 3 full episodes in kaggle env          │     │
│    │    └─► copy main.py + policy_np.npz into iter_dir,    │     │
│    │         import main, drive env.step(...)               │     │
│    │    records: actions[], money_traj[], won flag         │     │
│    ├─────────────────────────────────────────────────────────┤     │
│    │ 4. summarize: action_counts, trade_frac, win_rate     │     │
│    ├─────────────────────────────────────────────────────────┤     │
│    │ 5. render report.html (verdict, action table, money   │     │
│    │    sparkline, per-episode block, comparison card)      │     │
│    ├─────────────────────────────────────────────────────────┤     │
│    │ 6. early stop?                                       │     │
│    │    if trade_frac >= threshold → LEARNED → exit loop  │     │
│    │    else → next iter                                   │     │
│    └─────────────────────────────────────────────────────────┘     │
└────────────────────────────────────────────────────────────────────┘
```

`scripts/train.py` is **also usable standalone** for single long runs (`--total_steps 10M --device cuda`). But for verification of "did the agent learn to trade?" the closed loop is the canonical workflow.

---

## 2. Algorithm

### 2.1 PPO + Stable Baselines3

- **Algorithm**: Proximal Policy Optimization (clip surrogate)
- **Library**: `stable_baselines3==2.3.0` (`from stable_baselines3 import PPO`)
- **Policy**: `MlpPolicy` (ActorCriticPolicy with 2-layer MLP)
- **Network**: Linear(32, 64) → ReLU → Linear(64, 64) → ReLU → Linear(64, 5) (policy) + value head

### 2.2 PPO hyperparameters (default, mirror `configs/wheat_only.yaml`)

| Param | Value | Source |
|---|---|---|
| `learning_rate` | `3e-4` | stable |
| `n_steps` | `2048` | rollout buffer size |
| `batch_size` | `64` | minibatch size |
| `n_epochs` | `10` | PPO inner epochs per rollout |
| `gamma` | `0.99` | discount |
| `gae_lambda` | `0.95` | GAE |
| `clip_range` | `0.2` | PPO clipping |
| `ent_coef` | `0.01` | entropy bonus (encourages exploration) |
| `vf_coef` | `0.5` | value loss coefficient |
| `max_grad_norm` | `0.5` | gradient clipping |

### 2.3 Action space (Phase 1, 5 actions)

| Idx | Semantics | `main.py` output | Always legal? |
|---|---|---|---|
| 0 | HOLD | `[]` | ✅ |
| 1 | HIRE | `[{'market':[['HIRE']]}]` | ❌ needs `money ≥ 100` and `hires_today > 0` |
| 2 | SELL_WHEAT | `[{'market':[['SELL','WHEAT',1]]}]` | ❌ needs wheat in shed |
| 3 | BUY_PRODUCT_WHEAT | `[{'market':[['BUY_PRODUCT','WHEAT',1]]}]` | ❌ needs `money ≥ price` and market stock |
| 4 | PASS | `[{'farmer':['PASS']}]` | ✅ |

**Critical observation**: 2 of 5 actions are **always legal**. This means PPO can game `-0.05` invalid-action penalty by sticking to {0, 4} — this is the central failure mode that P1-5 (`action_masks()`) addresses when switching to MaskablePPO.

### 2.4 Observation space (32-dim)

Built by `ObsProcessor.process` from a flat `simple_obs` dict. Channels:

| Index | Field | Normalization |
|---|---|---|
| 0 | step | `step / 720` |
| 1 | day | `day / 30` |
| 2 | money | `min(money, 100000) / 100000` |
| 3-6 | WHEAT / FERTILIZER / MELON / STRAWBERRY prices | `/ 100` |
| 7-10 | market inventory | `/ 1000` |
| 11 | plantable_tiles | `/ 100` |
| 12 | plants_ready | `/ 100` |
| 13 | total_plants | `/ 100` |
| 14 | weed_density | raw |
| 15-17 | cows / sheep / unfed | `/ 10` |
| 18-20 | (reserved, currently 0) | — |
| 21-25 | hands / money / shed.wheat / shed.fertilizer / hires_left | various |
| 26-28 | opponent money / visible plants / animals | various |
| 29-31 | (reserved, currently 0) | — |

### 2.5 Reward function (post P0-1/3/4 + P1-5)

```python
def _compute_reward(self, raw_obs):
    money_delta = current_money - self._prev_money
    if self.reward_type == "sparse":
        reward = 0.0
    else:
        reward = money_delta / 10000.0          # P0-3: was /1000 (10× bigger)
    return reward, {"money_delta": money_delta}

def step(self, action):
    reward, _ = self._compute_reward(new_raw_obs)
    if not is_valid:
        reward += -0.05                          # invalid action
    if terminated:                                # P0-4: only true game-end
        if won:
            reward += 10.0
        else:
            reward += -5.0
    # truncated episodes get NO terminal bonus (P0-4)
```

**Reward magnitude per episode**:

| Component | Magnitude |
|---|---|
| Dense total (over 720 steps) | up to ±7.4 |
| Terminal win | `+10` (only on `terminated`) |
| Terminal loss | `-5` (only on `terminated`) |
| Invalid action | `-0.05` per occurrence |

**Terminal signal dominates**: dense is a small shaping signal; win/loss is the dominant gradient.

---

## 3. Environment contract

### 3.1 `src/envs/kagriculture_env.py:KagricultureEnv`

```python
KagricultureEnv(
    opponent: str = "random",                       # or "trained"
    reward_type: str = "dense",                     # or "sparse"
    opponent_model_path: str = None,                # default: models/opponent_model.joblib
    kaggle_env = None,                              # P0-2: shared kaggle_env
)
```

### 3.2 Train / eval share one kaggle_env (P0-2)

Created once in `scripts/train.py`:

```python
shared_kaggle_env = _kaggle_make("kagriculture", debug=False)
train_env = KagricultureEnv(opponent=..., kaggle_env=shared_kaggle_env)
eval_env  = KagricultureEnv(opponent=..., kaggle_env=shared_kaggle_env)
```

This ensures train and eval see the **same kaggle interpreter state** (and therefore the same RF opponent play sequence). Without this, the agent overfits to rollout's opponent play pattern and eval is unreliable.

### 3.3 `_owns_kaggle_env` flag (P1-4)

To safely call `close()` on either env without breaking the other, each env tracks whether it created its kaggle_env. Only the owner nullifies on close:

```python
self._owns_kaggle_env = (kaggle_env is None)
...
def close(self):
    if self._owns_kaggle_env:
        self._kaggle_env = None  # shared kaggle_env is NOT touched
```

### 3.4 `_won` reset on `reset()` (P0-1)

`reset()` MUST clear `self._won = False`. Otherwise stale state from a previous episode leaks.

### 3.5 Terminal bonus only on `terminated` (P0-4)

`done = terminated or truncated`. Terminal `+10/-5` fires ONLY when `terminated` (kaggle game actually ended). Truncated episodes (step=720) get no bonus — `_won` is explicitly set to False to prevent stale state.

### 3.6 kaggle_env done guard (Loop fix, 2026-08-11)

If `self._kaggle_env.done` is already True when `step()` is called, short-circuit to a done 5-tuple. SB3's VecEnv sometimes calls step() before reset() completes; without the guard it raises `FailedPrecondition: Environment done, reset required.`

### 3.7 `action_masks()` exposed (P1-5)

Gymnasium ActionMask API. Returns a `(5,)` int8 vector where 1 = legal, 0 = illegal. Also embedded in `info["action_mask"]` on every step. Used by sb3-contrib's `MaskablePPO` (future migration).

---

## 4. Logging — directory layout

### 4.1 What gets written, where

| Path | Writer | Contents |
|---|---|---|
| `log/eval_loop.log` | `eval_loop.py` | Master loop stdout (one line per iter start/end) |
| `eval_reports/iter_NN_<ts>/report.html` | `eval_loop.py` | Visual verdict + action distribution + money sparkline |
| `eval_reports/iter_NN_<ts>/replay.html` | `eval_loop.py` | Per-step replay timeline (action + money + day) |
| `eval_reports/iter_NN_<ts>/summary.json` | `eval_loop.py` | `action_counts`, `trade_frac`, `win_rate` |
| `eval_reports/iter_NN_<ts>/episodes.json` | `eval_loop.py` | Full per-step action log + money trajectory |
| `eval_reports/iter_NN_<ts>/replay.json` | `eval_loop.py` | Full Kaggle-format replay (compatible with kaggle-environments viewer) |
| `eval_reports/iter_NN_<ts>/model.zip` | `scripts/train.py` | Final SB3 model |
| `eval_reports/iter_NN_<ts>/policy_np.npz` | `eval_loop.py` | Numpy weights for `main.py` |
| `eval_reports/iter_NN_<ts>/main.py` | copied from project root | For local eval reproduction |
| `eval_reports/iter_NN_<ts>/train_log/train.log` | `train.py` DualLogger | Header + setup + train summary |
| `eval_reports/iter_NN_<ts>/train_log/train.stdout` | `eval_loop.py` (subprocess Popen) | **Continuous** train stdout — SB3 rollout tables, step counter, reward curves |
| `eval_reports/iter_NN_<ts>/train_log/train_eval.csv` | `WinRateEvalCallback` | Per-50k-step win rate / mean reward / fps |
| `eval_reports/iter_NN_<ts>/train_log/train_best/best_model.zip` | `WinRateEvalCallback` | Best-win-rate model (auto-saved) |
| `eval_reports/iter_NN_<ts>/train_log/train_checkpoints/ppo_*_steps.zip` | `CheckpointCallback` | Periodic checkpoints |

### 4.2 Why this layout?

- **Per-iteration isolation**: each iter is a self-contained artifact bundle — easy to diff, archive, or selectively submit
- **`report.html` is the canonical signal** — designed for quick visual triage (verdict badge + bar chart + sparkline)
- **CSV alongside HTML** — programmatic consumers can read CSV without parsing HTML
- **`episodes.json` retained** — full replay data for future forensics
- **No global `logs/` dir** — old `logs/` (plural) and `log/` (singular) dirs exist for legacy but `eval_reports/` is the new source of truth

### 4.3 What does NOT get logged

- ❌ TensorBoard event files — not used (we tried `tb_log_name='PPO'` but loop doesn't pass `tb_log_name` to `PPO` directly; SB3 default has TB disabled by default anyway)

### 4.4 Replay HTML — per-step episode visualization

After every eval (per iter), `eval_loop.py` generates a self-contained `replay.html` showing the per-step trajectory of each eval episode. This is the **canonical debug surface** when something looks wrong — was the agent close to winning? Did it ever pick a trade action? Where did it lose money?

**Layout (top to bottom):**

1. **Header** — iter number, episode index, won/lost badge, final money, total steps, action counts
2. **Money chart** — line/bar chart of money over the episode (full trajectory), with major events (first trade, last action) annotated
3. **Action timeline** — for each step (or every 5 steps if too long):
   - Step number, day/hour
   - Action pill (color-coded: HOLD=blue, HIRE=green, SELL_WHEAT=orange, BUY_WHEAT=red, PASS=purple, OTHER=gray)
   - Money at that step (with delta from previous step, color: green=up, red=down)
   - Cumulative reward (so far)
4. **Trade events** — highlighted section showing every step where action was HIRE/SELL/BUY
5. **Final summary** — total reward, won flag, action distribution mini-table

**Color palette** (matches `report.html`):

| Action | Color (hex) | Badge |
|---|---|---|
| HOLD (idx 0) | `#1f77b4` | blue |
| HIRE (idx 1) | `#2ca02c` | green |
| SELL_WHEAT (idx 2) | `#ff7f0e` | orange |
| BUY_WHEAT (idx 3) | `#d62728` | red |
| PASS (idx 4) | `#9467bd` | purple |
| OTHER (idx -1) | `#888888` | gray |

**Sample entry from the timeline table:**

```html
<tr>
  <td class="num">47</td>
  <td>day 1, h23</td>
  <td><span class="pill trade">HIRE</span></td>
  <td class="num money-up">$48 200  <span class="delta">−100</span></td>
  <td class="num">+0.10</td>
</tr>
```

If `num_eval_episodes > 1`, each episode gets its own tab/anchor in the same HTML file.

**Use cases**:

- *“Did the agent ever trade?”* → scroll to Trade events section, or `Ctrl-F` for "HIRE" / "SELL_WHEAT"
- *“Where did money drop sharply?”* → look at money column for red `delta` cells
- *“Was the agent's money tracking the opponent?”* → combine with opponent money if captured (future)

### 4.5 `replay.json` — Kaggle-compatible replay dump

`replay.json` is the **raw episode state in Kaggle's native format** (steps array with `obs` + `action` + `reward` per player per step). Compatible with:

- `kaggle-environments` HTML renderer (`html_renderer` from kaggriculture)
- `kaggle competitions episodes --download` (when uploaded as a dataset)
- Any third-party replay viewer

**Use case**: cross-check that our agent's behavior in `replay.html` matches the official Kaggle-format rendering (no mapping bugs).

---

## 5. Evaluation strategy

### 5.1 What counts as "the agent learned""

We define **learning** in two ways, both tracked simultaneously:

1. **trade_frac** — fraction of actions that are HIRE/SELL_WHEAT/BUY_PRODUCT_WHEAT (indices 1/2/3)
   - Threshold (default): `0.05` (5% of all actions)
   - Above threshold → agent has discovered that trade actions are useful
2. **win_rate** — fraction of eval episodes where `info["won"]` was True at episode end
   - Threshold (not auto-checked): `> 0.5` over many episodes
   - Above threshold → agent beats the opponent more than half the time

**The loop auto-stops on `trade_frac ≥ threshold`.** `win_rate` is reported but not gated.

### 5.2 Why trade_frac, not just win_rate

- Win rate needs many episodes to estimate (low N → high variance)
- Trade-action fraction is observable in just 3 episodes (~2000 actions)
- An agent that picks HIRE every step has trade_frac=1.0 even if it loses → at least it learned the action space

### 5.3 Per-iteration eval protocol

- 3 full episodes (configurable via `--num_eval_episodes`)
- vs `random` opponent (default) or `trained` opponent
- Action distribution, money trajectory, win flag per episode

### 5.4 Eval CSV (in-train)

`eval_reports/iter_NN/train_log/train_eval.csv` is written every `--eval_freq` (default 50 000) steps by the `WinRateEvalCallback`:

```csv
step,win_rate,mean_reward,fps
50000,0.000000,-11.250000,181
100000,0.000000,-9.100000,182
...
```

Use this to track whether win_rate is trending up within a single iter.

---

## 6. Best-model saving

### 6.1 When to save

`WinRateEvalCallback` saves `<log_dir>/<log_name>_best/best_model.zip` whenever the **eval `win_rate` strictly exceeds** the previous best:

```python
if win_rate > self.best_win_rate:
    self.best_win_rate = win_rate
    save_path = os.path.join(self.best_model_save_path, "best_model.zip")
    self.model.save(save_path)
```

### 6.2 Caveat: zero-win initialization

`self.best_win_rate` starts at `-1.0`, so the **first eval (even at 0% win rate) is always saved as "best"**. This is by design — we want a model artifact after every iter, even if the agent didn't win.

**Implication**: `train_best/best_model.zip` is often just the model from the first eval of the iter, not necessarily a good one. Don't submit blindly.

### 6.3 What to actually submit

Prefer, in order:

1. The model from the iter where `report.html` shows the highest `trade_frac` (proves it's actually trading)
2. The final model from the iter with highest `win_rate` in the in-train CSV
3. The model from the iter marked "✓ LEARNED" by the loop (if any)

---

## 7. Early stopping

### 7.1 Loop-level early stop (`scripts/eval_loop.py`)

The master loop stops on **either** condition:

| Condition | Behavior |
|---|---|
| `trade_frac ≥ --trade_threshold` (default 5%) | Print "✓ LEARNED" + exit |
| `iter == --max_iters` (default 5) | Print "✗ NOT LEARNED" + exit |
| KeyboardInterrupt / `pkill` | Mid-iter model saved as `_interrupted.zip` if PPO is alive; current iter's iter_dir is partial |

### 7.2 Within-iter early stop (`scripts/train.py`)

None currently. PPO runs to `total_steps`. Future: add SB3's `StopTrainingOnNoModelImprovement` callback if win_rate plateaus for N iters.

### 7.3 Logging early-stop signals

- "✓ LEARNED at iteration N!" printed to stdout AND written to `log/eval_loop.log`
- HTML `report.html` shows green "LEARNED" badge or red "NOT LEARNED"
- The loop's exit code is 0 either way — external monitor must parse `log/eval_loop.log`

---

## 8. Reproducing a single iter manually

```bash
# 1. Train (single iter, no loop)
python scripts/train.py \
    --total_steps 280000 \
    --model_path models/manual_test \
    --log_dir log \
    --log_name manual_test \
    --device cuda \
    --opponent trained \
    --final_eval_episodes 0

# 2. Convert .zip → .npz (keys: mlp_extractor.policy_net.{0,2}.{weight,bias}, action_net.{weight,bias})
python -c "
import zipfile, tempfile, os, numpy as np, torch
with tempfile.TemporaryDirectory() as td:
    with zipfile.ZipFile('models/manual_test.zip') as z: z.extractall(td)
    sd = torch.load(os.path.join(td,'policy.pth'), map_location='cpu', weights_only=True)
    np.savez('models/manual_test.npz', **{
        k: sd[k].numpy().astype(np.float32) for k in (
            'mlp_extractor.policy_net.0.weight', 'mlp_extractor.policy_net.0.bias',
            'mlp_extractor.policy_net.2.weight', 'mlp_extractor.policy_net.2.bias',
            'action_net.weight', 'action_net.bias')
    })
"

# 3. Local eval (3 episodes vs random opponent, log action distribution)
mkdir -p /tmp/eval_repro && cd /tmp/eval_repro
cp /data/app/sandbox/kaggle/kg-rl/main.py .
cp models/manual_test.npz ./policy_np.npz

python -c "
import sys, collections
sys.path.insert(0, '/data/app/sandbox/kaggle/kg-rl')   # registers kaggriculture
sys.path.insert(0, '/tmp/eval_repro')
import main
from kaggle_environments import make
main.load_actor(); main._step_count = 0
env = make('kagriculture', debug=False); env.reset(num_agents=2)
actions = []
while not env.done and len(actions) < 720:
    a = main.agent(env.state[0].observation, env.configuration)
    actions.append(a); env.step([a, {}])
print(collections.Counter(str(a) for a in actions).most_common(5))
"
```

---

## 9. Failure modes

| Symptom | Likely cause | Fix |
|---|---|---|
| Training crashes immediately | `_kaggle_env.done` guard missing | Ensure env has the done guard (see §3.6) |
| `ep_rew_mean ≈ +5` but win_rate = 0% | Dense reward too large (old `/1000`) | Verify P0-3 fix is in place |
| All actions are HOLD/PASS | PPO learned to avoid `-0.05` penalty | Switch to MaskablePPO using `action_masks()` |
| `trade_frac=0%` after 5M steps | Reward signal still wrong, or opponent too strong | Reduce `ent_coef` to 0, lower lr, or use `--opponent random` first |
| Iter 1 train crashes with "Environment done, reset required" | Done guard missing | Verify §3.6 is in `src/envs/kagriculture_env.py:step()` |
| Kaggle submission rejected ("main.py not at root") | Tarball layout wrong | Use `cp main.py policy_np.npz .` + `tar -czf` from repo root, per `CODEX.md` |

---

## 10. Pre-flight checklist before any training run

```
[ ] Confirm P0-1/2/3/4 + P1-5 are in src/envs/kagriculture_env.py
[ ] Confirm shared kaggle_env in scripts/train.py (P0-2)
[ ] Confirm _owns_kaggle_env flag and close() guard (P1-4)
[ ] Confirm eval_loop.py has --skip_train path tested
[ ] Confirm models/opponent_model.joblib exists (for --opponent trained)
[ ] Clear eval_reports/ for fresh run (or accept previous iters stay)
[ ] Allocate GPU (nvidia-smi shows 0% util before launch)
[ ] Pick --steps_per_iter based on budget: 280k = 30 min, 100k = 10 min
[ ] Pick --max_iters based on budget: 5 = 2.5h, 10 = 5h
[ ] Pick --trade_threshold: 0.05 = loose, 0.10 = strict
[ ] Pick --opponent: random first (easier to learn), then trained
[ ] Run with --num_eval_episodes 3 (cheap) or 10 (more confident)
```

---

## 11. References

- [`log-session.md`](../log-session.md) — chronological bug history
- [`docs/REPLAY_BUG_REPRODUCTION_20260810.md`](REPLAY_BUG_REPRODUCTION_20260810.md) — why models regress to PASS
- [`docs/CHANGE_SPEC-env-won-reset-20260810.md`](.) — P0-1 spec
- [`docs/CHANGE_SPEC-env-shared-kaggle-env-20260810.md`](.) — P0-2 spec
- [`docs/CHANGE_SPEC-env-dense-reward-scale-20260810.md`](.) — P0-3 spec
- [`docs/CHANGE_SPEC-env-terminal-bonus-20260810.md`](.) — P0-4 spec
- [`docs/CHANGE_SPEC-env-action-masks-20260810.md`](.) — P1-5 spec
- [`CODEX.md`](../CODEX.md) — submission tarball packaging rules
- [`.claude/WORKFLOW.md`](../.claude/WORKFLOW.md) — dev workflow (spec → review → fix → eval)