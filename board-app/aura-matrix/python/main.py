# Aura Matrix — Arduino App python side.
#
# IMPORTANT platform discovery: an Arduino App's python side runs inside its
# own Docker container (ghcr.io/arduino/app-bricks/python-apps-base), which
# only bind-mounts this app's own directory (/app), LED sysfs paths, and the
# RouterBridge socket -- there is no supported app.yaml mechanism to bind-
# mount an arbitrary host path like ~/.aura into it. So this app does NOT
# read ~/.aura/state.json + alerts.jsonl directly (that approach was tried
# first and silently produced all-zero state, since the file "doesn't
# exist" from inside the container -- confirmed via `docker inspect
# aura-matrix-main-1` showing only /app + LED + router-socket bind mounts).
#
# Instead it fetches the SAME data over HTTP from the aura-face systemd
# service's already-running, already-live, read-only API
# (aura/face/server.py: GET /api/state, GET /api/alerts) -- untouched,
# read-only, no new host-side infrastructure needed. The container reaches
# it via the HOST_IP env var the framework injects into every app container
# for exactly this purpose, with the docker host-gateway hostname alias
# ("msgpack-rpc-router", present in every app's compose file) as a
# network-topology-independent fallback if HOST_IP ever goes stale.
#
# Every 0.2s: GET /api/state -> presence/motion/activity, and (every ~2s,
# cached in between -- no need to hit it at 0.2s resolution for a 60s
# freshness window) GET /api/alerts?n=1 -> alert=1 iff its ts is < 60s old.
# This mirrors aura/face/bridge.py's field defaults and freshness window,
# the PC-testable reference implementation for the Linux <-> M33 channel.
#
# Self-contained: does NOT import the aura package, only stdlib +
# arduino.app_utils.
import json
import os
import time
import urllib.request

from arduino.app_utils import App, Bridge, Logger

FACE_PORT = 8080
CANDIDATE_HOSTS = [h for h in [os.environ.get("HOST_IP"), "msgpack-rpc-router"] if h]

POLL_INTERVAL_S = 0.2
HTTP_TIMEOUT_S = 0.3
ALERT_CHECK_INTERVAL_S = 2.0
ALERT_FRESH_S = 60.0
HEARTBEAT_EVERY_S = 30.0
BACKOFF_S = 5.0

logger = Logger("aura-matrix")

_working_host = None
_backoff_until = 0.0


def _get_json(path):
    """GET a JSON path from the aura-face API, trying candidate hosts (the
    last host that worked first) until one succeeds. Returns None on any
    failure (service down, timeout, bad JSON, ...) so callers can fall back
    to a safe default -- never raises.

    Negative-cache: if every host failed on a previous call, skip HTTP
    entirely until BACKOFF_S has passed -- an aura-face outage must not
    stack up to ~4s of worst-case per-tick timeout (2 hosts x 2 endpoints
    x HTTP_TIMEOUT_S), it should degrade to the zero-state fallback fast
    and stay there until the service is plausibly back.
    """
    global _working_host, _backoff_until
    if time.time() < _backoff_until:
        return None

    hosts = CANDIDATE_HOSTS
    if _working_host in hosts:
        hosts = [_working_host] + [h for h in hosts if h != _working_host]

    for host in hosts:
        url = "http://%s:%d%s" % (host, FACE_PORT, path)
        try:
            with urllib.request.urlopen(url, timeout=HTTP_TIMEOUT_S) as resp:
                data = json.load(resp)
            _working_host = host
            return data
        except Exception:
            continue

    _backoff_until = time.time() + BACKOFF_S
    return None


def _read_state():
    """presence/motion/activity via GET /api/state. Tolerates the face API
    being unreachable/returning something unexpected by falling back to
    all-zero state, same as aura/face/bridge.py's _read() helper.
    """
    s = _get_json("/api/state") or {}
    try:
        presence = int(s.get("presence", 0) or 0)
    except Exception:
        presence = 0
    try:
        motion = int(s.get("motion", 0) or 0)
    except Exception:
        motion = 0
    try:
        activity = int(round(float(s.get("activity", 0) or 0)))
    except Exception:
        activity = 0

    presence = 1 if presence else 0
    motion = 1 if motion else 0
    activity = max(0, min(255, activity))
    return presence, motion, activity


_cached_alert = 0
_last_alert_check = 0.0


def _alert_active(now):
    """1 iff the most recent alert (GET /api/alerts?n=1) has a ts within the
    last 60s. Only re-checked every ALERT_CHECK_INTERVAL_S (a 60s freshness
    window doesn't need 0.2s resolution); the cached value is reused
    in between. Tolerates a missing/corrupt response, same as
    aura/face/bridge.py's _alert_active() helper.
    """
    global _cached_alert, _last_alert_check
    if now - _last_alert_check < ALERT_CHECK_INTERVAL_S:
        return _cached_alert

    _last_alert_check = now
    alerts = _get_json("/api/alerts?n=1")
    if not alerts:
        _cached_alert = 0
        return _cached_alert
    try:
        last = alerts[-1]
        _cached_alert = 1 if (now - float(last["ts"])) < ALERT_FRESH_S else 0
    except Exception:
        _cached_alert = 0
    return _cached_alert


_tick_count = 0
_last_heartbeat = 0.0


def loop():
    """Called repeatedly by the App framework (see App.run below)."""
    global _tick_count, _last_heartbeat

    now = time.time()
    presence, motion, activity = _read_state()
    alert = _alert_active(now)

    try:
        Bridge.call("state", bytes([presence, motion, activity, alert]))
    except Exception:
        pass  # transient bridge hiccup must never kill the loop

    _tick_count += 1
    if now - _last_heartbeat >= HEARTBEAT_EVERY_S:
        _last_heartbeat = now
        logger.info(
            "heartbeat: ticks=%d presence=%d motion=%d activity=%d alert=%d face_host=%s"
            % (_tick_count, presence, motion, activity, alert, _working_host)
        )

    time.sleep(POLL_INTERVAL_S)


logger.info(
    "Aura Matrix starting: polling aura-face API (candidates=%s) every %.1fs"
    % (CANDIDATE_HOSTS, POLL_INTERVAL_S)
)

App.run(user_loop=loop)
