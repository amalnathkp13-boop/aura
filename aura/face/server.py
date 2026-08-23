import json, re, subprocess, sys
from pathlib import Path
from flask import Flask, jsonify, request, send_from_directory

STATIC = Path(__file__).parent / "static"

def _int_arg(name, default):
    try:
        return max(0, int(request.args.get(name, default)))
    except (TypeError, ValueError):
        return default

def _tail_jsonl(path: Path, n: int):
    if n <= 0:
        return []
    if not path.exists():
        return []
    lines = path.read_text(encoding="utf-8").strip().splitlines()[-n:]
    out = []
    for l in lines:
        try:
            out.append(json.loads(l))
        except json.JSONDecodeError:
            pass
    return out

def create_app(cfg):
    app = Flask(__name__)

    @app.get("/")
    def index():
        return send_from_directory(STATIC, "index.html")

    @app.get("/static/<path:p>")
    def static_files(p):
        return send_from_directory(STATIC, p)

    @app.get("/api/state")
    def state():
        p = cfg.aura_home / "state.json"
        try:
            d = json.loads(p.read_text())
        except Exception:
            return jsonify({"src": "none"})
        return jsonify(d if isinstance(d, dict) else {"src": "none"})

    @app.get("/api/sense")
    def sense():
        p = cfg.aura_home / "sense.json"
        try:
            d = json.loads(p.read_text())
        except Exception:
            return jsonify({})
        return jsonify(d if isinstance(d, dict) else {})

    @app.get("/api/waterfall")
    def waterfall():
        n = _int_arg("n", 120)
        return jsonify(_tail_jsonl(cfg.aura_home / "features.jsonl", n))

    @app.get("/api/alerts")
    def alerts():
        n = _int_arg("n", 20)
        return jsonify(_tail_jsonl(cfg.aura_home / "alerts.jsonl", n))

    @app.get("/api/mode")
    def get_mode():
        p = cfg.aura_home / "mode.json"
        if p.exists():
            return jsonify(json.loads(p.read_text()))
        return jsonify({"mode": "home", "wellness_hours": 8})

    @app.post("/api/mode")
    def mode():
        body = request.get_json(silent=True)
        if not isinstance(body, dict):
            return jsonify({"error": "bad body"}), 400
        if body.get("mode") not in ("home", "away", "wellness"):
            return jsonify({"error": "bad mode"}), 400
        try:
            hours = int(body.get("wellness_hours", 8))
        except (TypeError, ValueError):
            return jsonify({"error": "bad wellness_hours"}), 400
        (cfg.aura_home / "mode.json").write_text(json.dumps(
            {"mode": body["mode"], "wellness_hours": hours}))
        return jsonify({"ok": True})

    @app.post("/api/calibrate")
    def calibrate():
        body = request.get_json(silent=True)
        if not isinstance(body, dict):
            return jsonify({"error": "bad body"}), 400
        phase = body.get("phase")
        if phase not in ("empty", "walk", "zone"):
            return jsonify({"error": "bad phase"}), 400
        try:
            minutes = int(body.get("minutes", 10))
        except (TypeError, ValueError):
            return jsonify({"error": "bad minutes"}), 400
        argv = [sys.executable, "-m", "aura.cli", "calibrate", phase,
                "--minutes", str(minutes)]
        if phase == "zone":
            name = body.get("name")
            if not (isinstance(name, str) and re.fullmatch(r"[a-z0-9_-]{1,16}", name)):
                return jsonify({"error": "bad zone name (a-z 0-9 _ -, max 16)"}), 400
            argv += ["--name", name]
        subprocess.Popen(argv)
        return jsonify({"started": True})

    return app

def run_face(cfg):
    create_app(cfg).run(host="0.0.0.0", port=8080)
