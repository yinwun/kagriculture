#!/bin/bash
# Paired duel of each sell_spread variant against the champion (data/tapeopt/rgcs).
cd /Users/nickyl/Developer/Sandbox/kaggle/kg-rl
PY=.venv/bin/python
for v in k3 k1 k8 k3frac50 k3h4 k3h48 k3nogate k3cash2000 k3shed70; do
  echo "=== $v ==="
  $PY -u scripts/ab_duel.py --cand data/spread/$v/main.py --base data/tapeopt/rgcs/main.py \
     --seeds 9000-9029 --procs 10 --label spread_$v --out data/spread/duel-$v.json 2>/dev/null \
     | grep -E "delta|idle share|MKT_SELL"
done
