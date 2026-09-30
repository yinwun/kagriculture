#!/bin/bash
# Paired duels (30 seeds x 2 seats) of built race variants against the champion.
# usage: scripts/race_sweep.sh variant1 [variant2 ...]
cd "$(dirname "$0")/.." || exit 1
for v in "$@"; do
  .venv/bin/python scripts/ab_duel.py --cand "data/race/$v/main.py" \
      --base data/tapeopt/rgcs/main.py --seeds 9000-9029 --procs 10 \
      --label "$v" --out "data/race/duel-$v.json" > "data/race/duel-$v.log" 2>&1
  grep -h "vs rgcs" "data/race/duel-$v.log"
done
