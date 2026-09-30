#!/bin/bash
# One-command submission of a pre-packaged, smoke-tested build.
#   bash scripts/fire.sh final_v3_comp_straw "optional note"
cd /Users/nickyl/Developer/Sandbox/kaggle/kg-rl
NAME=${1:?usage: fire.sh <ready-name> [note]}
NOTE=${2:-}
PKG="data/submits/ready-${NAME}.tar.gz"
[ -f "$PKG" ] || { echo "no such package: $PKG"; ls data/submits/ready-*.tar.gz; exit 1; }
.venv/bin/python -u scripts/submit.py "$PKG" "PREPARED BUILD ${NAME}. Public composite base (the-metav4-farm-submission-v13) + our outermost market layers; base is NOT our work, the market layers are. ${NOTE}" 2>&1 | tail -3
