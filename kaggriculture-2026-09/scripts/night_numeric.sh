#!/usr/bin/env bash
set -u
cd "$(dirname "$0")/.."
for v in rgcs_msp1 rgcs_msp20 rgcs_msp60 rgcs_bt24 rgcs_bt168; do
  .venv/bin/python scripts/ab_duel.py \
      --cand "data/tapeopt/$v/main.py" --base data/tapeopt/rgcs/main.py \
      --seeds 9000-9199 --procs 10 --label "$v" \
      --out "data/night-A-${v}.json" 2>&1 | sed -n '2p'
done
echo "numeric panel done"
