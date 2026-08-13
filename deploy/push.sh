#!/bin/sh
# Push the aura source tree to the board and (re)install into its venv.
# usage: sh deploy/push.sh [user@host]     default: arduino@192.168.63.60
set -e
DEST=${1:-arduino@192.168.63.60}
ssh "$DEST" "mkdir -p ~/aura-src"
SRCS="aura training deploy pyproject.toml"
[ -d models ] && SRCS="$SRCS models"
[ -d board-app ] && SRCS="$SRCS board-app"
scp -q -r $SRCS "$DEST":~/aura-src/
# Debian 13 pip is externally-managed -> dedicated venv on the board
ssh "$DEST" "cd ~/aura-src && { [ -d .venv ] || python3 -m venv .venv; } && ./.venv/bin/pip install -q -e '.[board]'"
echo "pushed to $DEST:~/aura-src (venv ready)"
