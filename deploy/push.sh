#!/bin/sh
# Push the aura source tree to the board and (re)install into its venv.
# usage: sh deploy/push.sh [user@host]     default: arduino@xfiles.local
# (the phone hotspot randomizes its subnet on config changes, so prefer the
#  mDNS name over a hard-coded IP; fall back to the current IP if mDNS fails)
set -e
DEST=${1:-arduino@xfiles.local}
ssh "$DEST" "mkdir -p ~/aura-src"
SRCS="aura training deploy pyproject.toml"
[ -d models ] && SRCS="$SRCS models"
[ -d board-app ] && SRCS="$SRCS board-app"
# tar (not scp -r): local __pycache__ must not ship, and root-owned .pyc files
# on the board (services run as root) make scp -r fail with Permission denied.
tar czf - --exclude='__pycache__' $SRCS | ssh "$DEST" "tar xzf - -C ~/aura-src"
# Debian 13 pip is externally-managed -> dedicated venv on the board
ssh "$DEST" "cd ~/aura-src && { [ -d .venv ] || python3 -m venv .venv; } && ./.venv/bin/pip install -q -e '.[board]'"
echo "pushed to $DEST:~/aura-src (venv ready)"
