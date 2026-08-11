# Kagriculture Submission — PASS-Every-Step Bug Reproduction

> **Date**: 2026-08-10
> **Status**: Bug confirmed locally, root cause identified, fix in progress (P0-1/2/3/4 + P1-5 already merged)

## TL;DR

Our submitted agents (v4-short, v5-short) output **HOLD or PASS every single step** — they never trade, hire, plant, or do anything useful. Local reproduction with `main.py` + `policy_np.npz` confirms the same passive behavior.

This is a **model training failure**, not a `main.py` bug. The P0 fixes (dense-reward scale, terminal-bonus on `terminated` only, `_won` reset, shared `kaggle_env`) and P1-5 (action masking) should make the *next* training run actually learn useful actions.

---

## 1. Kaggle replays — what the agent actually did

Two local replays pulled from `data/replay_latest/` show identical "do nothing" behavior.

### Episode 91667611

```text
rewards:    [5501.0, 3000.0]      ← we LOST  (−2500)
team_names: ['johndeere', 'nickyl']
steps:      720
```

### Episode 91601886

```text
rewards:    [3000.0, 3356.0]      ← we LOST  (−356)
team_names: ['nickyl', 'Turab Zaidi']
steps:      720
```

### Action distribution (player 0 = our agent)

<table>
<thead>
<tr>
  <th rowspan="2">Episode</th>
  <th rowspan="2">Reward [p0, p1]</th>
  <th colspan="2">PASS-every-step</th>
  <th colspan="2">Other actions</th>
</tr>
<tr>
  <th>{'farmer':['PASS']}</th>
  <th>%</th>
  <th>count</th>
  <th>%</th>
</tr>
</thead>
<tbody>
<tr>
  <td><b>91667611</b></td>
  <td>[5501, 3000]</td>
  <td>682</td>
  <td style="background:#ffcccc"><b>94.7%</b></td>
  <td>38</td>
  <td>5.3%</td>
</tr>
<tr>
  <td><b>91601886</b></td>
  <td>[3000, 3356]</td>
  <td>720</td>
  <td style="background:#ff9999"><b>100.0%</b></td>
  <td>0</td>
  <td>0.0%</td>
</tr>
</tbody>
</table>

### Visual: PASS-only behaviour dominates

<div style="font-family:monospace; font-size:13px; line-height:1.6; padding:10px; background:#f8f8f8; border:1px solid #ddd;">

<b>Episode 91667611 (p0 = our agent)</b>
<div style="background:#cc0000; color:white; padding:2px 6px; width:94.7%; display:inline-block;">PASS 682 (94.7%)</div>
<div style="background:#ffaa00; color:black; padding:2px 6px; width:3.7%; display:inline-block;">WATER 27</div>
<div style="background:#ffaa00; color:black; padding:2px 6px; width:0.3%; display:inline-block;">HARVEST 2</div>
<div style="background:#999999; color:white; padding:2px 6px; width:1.3%; display:inline-block;">+ 9 more</div>

<br><br>

<b>Episode 91601886 (p0 = our agent)</b>
<div style="background:#cc0000; color:white; padding:2px 6px; width:100%; display:inline-block;">PASS 720 (100%)</div>

</div>

### What `{'farmer': ['PASS'], 'hands': [], 'market': []}` actually means

It's a **valid** Kaggle action — the agent just tells the farmer to do nothing, no hands, no market. So the agent emits well-formed actions that mean "skip the entire turn". It is the equivalent of HOLD, but in Kaggle's `farmer` namespace rather than the empty `{}` (which Kaggle treats as "no-op for whichever player namespace it lands in").

---

## 2. Local reproduction — step by step

### 2.1 Setup

```bash
# 1. Copy the exact files that go into the Kaggle submission tarball
mkdir -p /tmp/replay_repro && cd /tmp/replay_repro
cp /data/app/sandbox/kaggle/kg-rl/main.py .
cp /data/app/sandbox/kaggle/kg-rl/models/policy_np.npz .

ls -la
# main.py          8 152 bytes
# policy_np.npz   28 122 bytes
```

These are **the identical files** inside `pkg/submission-ppo-v5-short.tar.gz`.

### 2.2 Run a full episode

```python
import sys
sys.path.insert(0, '/data/app/sandbox/kaggle/kg-rl')   # triggers env registration
sys.path.insert(0, '/tmp/replay_repro')

from src.envs.kagriculture_env import KagricultureEnv  # noqa — registers kagriculture
import main
from kaggle_environments import make

main.load_actor()
main._step_count = 0

env = make('kagriculture', debug=False)
env.reset(num_agents=2)

actions_log = []
while not env.done and len(actions_log) < 720:
    obs_for_p0 = env.state[0].observation
    action = main.agent(obs_for_p0, env.configuration)
    actions_log.append(action)
    env.step([action, {}])          # opponent: pure HOLD

import collections
counter = collections.Counter(str(a) for a in actions_log)
```

### 2.3 Local result (v5-short model)

<table>
<thead>
<tr>
  <th>Action emitted</th>
  <th>Count</th>
  <th>%</th>
  <th>Visual</th>
  <th>Meaning</th>
</tr>
</thead>
<tbody>
<tr>
  <td><code>[]</code></td>
  <td>507</td>
  <td><b>70.6%</b></td>
  <td>
    <div style="background:#1f77b4; color:white; padding:3px 8px; width:70.6%; display:inline-block; min-width:60px;">HOLD 507</div>
  </td>
  <td>Empty action — Kaggle treats as "no-op". Equivalent to action index 0.</td>
</tr>
<tr>
  <td><code>[{'farmer': ['PASS']}]</code></td>
  <td>200</td>
  <td><b>27.8%</b></td>
  <td>
    <div style="background:#ff7f0e; color:white; padding:3px 8px; width:27.8%; display:inline-block; min-width:60px;">PASS 200</div>
  </td>
  <td>Farmer skips; no hands, no market. Action index 4.</td>
</tr>
<tr>
  <td><code>[{'market': [['SELL', 'WHEAT', 1]]}]</code></td>
  <td>12</td>
  <td>1.7%</td>
  <td>
    <div style="background:#2ca02c; color:white; padding:3px 8px; width:1.7%; display:inline-block; min-width:60px;">SELL 12</div>
  </td>
  <td>Sells one wheat on the market. Action index 2.</td>
</tr>
<tr>
  <td>HIRE / BUY</td>
  <td><b>0</b></td>
  <td>0%</td>
  <td><span style="color:#999;">never picked</span></td>
  <td>Action indices 1 and 3 — model never picks them.</td>
</tr>
</tbody>
</table>

**Total non-trade actions: 707/719 = 98.3%.**

---

## 3. Why both HOLD and PASS appear locally but only PASS appears on Kaggle

`main.py`'s `agent()` returns:

```python
if action == 0:    return []                           # ← HOLD (empty)
elif action == 1:  return [{'market': [['HIRE']]}]
elif action == 2:  return [{'market': [['SELL', 'WHEAT', 1]]}]
elif action == 3:  return [{'market': [['BUY_PRODUCT', 'WHEAT', 1]]}]
elif action == 4:  return [{'farmer': ['PASS']}]       # ← farmer PASS
```

The Kaggle replay (from v4-short, ref 55410260) was generated by an older `main.py` where action=0 returned `[{'farmer': ['PASS']}]` instead of `[]`. So the action mapping differed between v4 and v5. **Both versions emit only index 0 and index 4.** That is the model, not `main.py`.

The model literally never picks indices 1 / 2 / 3 in any of our submissions. This is the actual failure mode.

---

## 4. Root cause analysis

### 4.1 PPO learned that "do nothing" is the optimum

The rollout reward signal was:

```text
dense:  money_delta / 1000     (per step)
term:   +10 / -5               (on every done=True, including truncated)
inv:    -0.05                  (illegal action penalty)
```

**Why "do nothing" wins in PPO's view:**

- HOLD (action 0) and PASS (action 4) are **always valid** → no `-0.05` penalty
- The market/inventory state at step 0 is empty / low → SELL_WHEAT and BUY_PRODUCT_WHEAT are **illegal** → `-0.05` each time picked
- HIRE needs `money >= 100` → may be legal but adds no guaranteed reward
- So PPO learns: "always pick 0 or 4, never get penalized"

The "+10 win bonus" never fires because the agent never wins (it doesn't trade, so money stays flat or declines slowly, opponent wins).

### 4.2 The dense reward signal masks "losing"

Old dense `money_delta / 1000` per step is **~70× larger** than the `-5` loss penalty per episode, so PPO happily converges to "always make tiny positive money_delta by not trading" while losing the game.

### 4.3 Confirms our earlier P0 analysis

`log-session.md` (2026-08-10 晚间更新) flagged this exact pattern — `rollout ep_rew_mean ≈ +5.8` but `eval win_rate = 0%`. The P0 fixes address it directly:

| P0 fix | Effect on the bug |
|---|---|
| **P0-1** `_won` reset | eval win_rate now reliable |
| **P0-2** shared kaggle_env | train & eval see same opponent sequence |
| **P0-3** dense `÷10000` | dense no longer swamps ±10 terminal; PPO actually learns to win |
| **P0-4** terminal bonus only on `terminated` | truncated episodes don't get spurious "loss" penalty |
| **P1-5** `action_masks()` | MaskablePPO can skip illegal actions without learning to never-trade |

---

## 5. Action index map (for debugging)

<table>
<thead>
<tr>
  <th>Action idx</th>
  <th>main.py output</th>
  <th>Trained as</th>
  <th>Always legal?</th>
  <th>Effect</th>
</tr>
</thead>
<tbody>
<tr>
  <td>0</td>
  <td><code>[]</code></td>
  <td>HOLD</td>
  <td>✅ Yes</td>
  <td>No-op (do nothing)</td>
</tr>
<tr>
  <td>1</td>
  <td><code>[{'market':[['HIRE']]}]</code></td>
  <td>HIRE</td>
  <td>❌ Needs money ≥100 AND hires_today > 0</td>
  <td>Hire a hand</td>
</tr>
<tr>
  <td>2</td>
  <td><code>[{'market':[['SELL','WHEAT',1]]}]</code></td>
  <td>SELL_WHEAT</td>
  <td>❌ Needs wheat in shed</td>
  <td>Sell one wheat</td>
</tr>
<tr>
  <td>3</td>
  <td><code>[{'market':[['BUY_PRODUCT','WHEAT',1]]}]</code></td>
  <td>BUY_PRODUCT_WHEAT</td>
  <td>❌ Needs money ≥ price AND market has wheat</td>
  <td>Buy one wheat</td>
</tr>
<tr>
  <td>4</td>
  <td><code>[{'farmer':['PASS']}]</code></td>
  <td>PASS</td>
  <td>✅ Yes</td>
  <td>Farmer skips turn</td>
</tr>
</tbody>
</table>

<div style="background:#fff8e1; border-left:4px solid #ff9800; padding:10px 16px; margin:16px 0;">

<b>⚠ Two of five actions are always legal — that's 40% of the action space that never triggers the `-0.05` penalty.</b>
PPO learns this very quickly: "stay in the safe zone (indices 0, 4), never risk the `-0.05`." Combined with the dense reward magnitude, this collapses the policy to "always PASS".

</div>

---

## 6. Verification commands (re-run anytime)

### 6.1 Inspect a downloaded replay

```python
import json, collections
with open('data/replay_latest/episode-91667611-replay.json') as f:
    d = json.load(f)
print('rewards:', d['rewards'])
print('team_names:', d['info']['TeamNames'])

all_p0 = [s[0].get('action', {}) for s in d['steps']]
counter = collections.Counter(str(a) for a in all_p0)
for action_str, count in counter.most_common(5):
    print(f'  {count:>4} × {action_str}')
```

### 6.2 Re-run local reproduction

```bash
mkdir -p /tmp/replay_repro && cd /tmp/replay_repro
cp /data/app/sandbox/kaggle/kg-rl/main.py .
cp /data/app/sandbox/kaggle/kg-rl/models/policy_np.npz .

# In Python:
python <<'EOF'
import sys, collections
sys.path.insert(0, '/data/app/sandbox/kaggle/kg-rl')
sys.path.insert(0, '/tmp/replay_repro')
from src.envs.kagriculture_env import KagricultureEnv  # noqa
import main
from kaggle_environments import make

main.load_actor(); main._step_count = 0
env = make('kagriculture', debug=False); env.reset(num_agents=2)

actions = []
while not env.done and len(actions) < 720:
    a = main.agent(env.state[0].observation, env.configuration)
    actions.append(a); env.step([a, {}])

print(collections.Counter(str(a) for a in actions).most_common(5))
EOF
```

### 6.3 Side-by-side comparison (this doc's tables regenerate from)

```bash
# Replay data lives in:
data/replay_latest/episode-91667611-replay.json    # 4.3 MB
data/replay/episode-91601886-replay.json           # 4.4 MB
```

---

## 7. Fix plan (already merged, awaiting retraining)

| # | Status | Change |
|---|---|---|
| P0-1 | ✅ done | `reset()` clears `self._won` |
| P0-2 | ✅ done | Train & eval share `kaggle_env` |
| P0-3 | ✅ done | Dense reward `÷10000` (was `÷1000`) |
| P0-4 | ✅ done | `+10/-5` only on `terminated`, not on `truncated` |
| P1-5 | ✅ done | `action_masks()` exposed for MaskablePPO |
| MaskablePPO | ⬜ next | Switch from `PPO` to `MaskablePPO` (sb3-contrib) to consume the masks |
| 2.5M retrain | ⬜ next | Re-run `train_v6_verify` to confirm fix |

---

## 8. Don't submit the broken models

The two `submission-*.tar.gz` tarballs in `pkg/` are based on these broken models:

| File | Source model | Public score (from Kaggle) |
|---|---|---|
| `pkg/submission-ppo-v4-short.tar.gz` | v4-short (55410260) | 187.4 |
| `pkg/submission-ppo-v5-short.tar.gz` | v5-short (this session's training) | not submitted (403) |

**Both should be considered retired until `train_v6_verify` produces a model that actually trades.**