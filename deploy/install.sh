#!/bin/sh
# run ON THE BOARD from ~/aura-src: sh deploy/install.sh
set -e
cp deploy/systemd/*.service /etc/systemd/system/
systemctl daemon-reload
for s in aura-ear aura-brain aura-guardian aura-face aura-bridge; do
  systemctl enable --now "$s"
done
systemctl --no-pager status aura-ear aura-brain | grep -E "aura-|Active:"
