import json, subprocess, sys
from pathlib import Path
from flask import Flask, jsonify, request, send_from_directory

STATIC = Path(__file__).parent / "static"

def _tail_jsonl(path: Path, n: int):
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
        if not p.exists():
            return jsonify({"src": "none"})
        return jsonify(json.loads(p.read_text()))

    @app.get("/api/waterfall")
    def waterfall():
        n = int(request.args.get("n", 120))
        return jsonify(_tail_jsonl(cfg.aura_home / "features.jsonl", n))

    @app.get("/api/alerts")
    def alerts():
        n = int(request.args.get("n", 20))
        return jsonify(_tail_jsonl(cfg.aura_home / "alerts.jsonl", n))

    @app.post("/api/mode")
    def mode():
        body = request.get_json(force=True)
        if body.get("mode") not in ("home", "away", "wellness"):
            return jsonify({"error": "bad mode"}), 400
        (cfg.aura_home / "mode.json").write_text(json.dumps(
            {"mode": body["mode"], "wellness_hours": int(body.get("wellness_hours", 8))}))
        return jsonify({"ok": True})

    @app.post("/api/calibrate")
    def calibrate():
        body = request.get_json(force=True)
        phase = body.get("phase")
        if phase not in ("empty", "walk"):
            return jsonify({"error": "bad phase"}), 400
        subprocess.Popen([sys.executable, "-m", "aura.cli", "calibrate", phase,
                          "--minutes", str(int(body.get("minutes", 10)))])
        return jsonify({"started": True})

    return app

def run_face(cfg):
    create_app(cfg).run(host="0.0.0.0", port=8080)
