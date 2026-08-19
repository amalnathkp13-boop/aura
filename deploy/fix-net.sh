#!/bin/sh
# One-shot (run as root on the board): point aura at the hotspot's current
# gateway and restart the sensing pipeline after the subnet change.
# The hotspot moved 192.168.63.0/24 -> 192.168.248.0/24 on 2026-08-20; the old
# gateway_ip left the link-RSSI ping stream dead and the pipeline stalled.
set -e
cat > /home/arduino/.aura/config.json <<'JSON'
{"scan_interval": 8.0, "gateway_ip": "192.168.248.104", "frame_hz": 4.0}
JSON
systemctl restart aura-ear aura-brain
echo "restarted at (UTC): $(date -u '+%Y-%m-%d %H:%M:%S')"
