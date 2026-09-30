#!/usr/bin/env bash
# Overnight panel sweep: every candidate vs the tracked champion on the same towns.
# Usage: bash scripts/night_panel.sh A|B
set -u
cd "$(dirname "$0")/.."
MODE="${1:-A}"
if [ "$MODE" = "A" ]; then SEEDS="9000-9199"; TAG="A"; else SEEDS="9200-9399"; TAG="B"; fi
for v in rgcs_te rgcs_de rgcs_bu rgcs_fr; do
  .venv/bin/python scripts/ab_duel.py \
      --cand "data/tapeopt/$v/main.py" --base data/tapeopt/rgcs/main.py \
      --seeds "$SEEDS" --procs 10 --label "$v" \
      --out "data/night-${TAG}-${v}.json" 2>&1 | sed -n '2p;4,10p'
done
echo "panel $TAG done"
