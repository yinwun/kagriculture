# Saved Model Evaluation

Generated: 2026-08-11 09:46:26  
Opponent: `trained`  ·  Episodes per model: 10  ·  Action space: 5

## Trade-action summary (HIRE + SELL_WHEAT + BUY_WHEAT)

| Model | Trade % | Safe % | Win rate | Wins / Total |
|---|---|---|---|---|
| `roi_reward_val.zip` | **97.50%** | 2.50% | 0.00% | 0/10 |

## Detailed action counts

| Model | HOLD | HIRE | SELL | BUY | PASS | OTHER | Total |
|---|---|---|---|---|---|---|---|
| `roi_reward_val.zip` | 0 | 0 | 0 | 7010 | 180 | 0 | 7190 |

## How to read this

- **Trade %** > 5% means the model triggered HIRE/SELL/BUY actions at least sometimes
- **Safe %** > 95% means the model collapsed to HOLD/PASS only (PASS-every-step bug)
- **Win rate** = fraction of episodes won (info['won'] at episode end)