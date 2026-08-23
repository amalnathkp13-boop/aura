import argparse, json, threading, time
from pathlib import Path
from aura.config import Config

def main():
    ap = argparse.ArgumentParser(prog="aura")
    sub = ap.add_subparsers(dest="cmd", required=True)
    p = sub.add_parser("record"); p.add_argument("--session", required=True); p.add_argument("--minutes", type=float, default=0)
    for c in ("run-ear", "run-brain", "run-guardian", "run-face", "run-bridge", "status"):
        sub.add_parser(c)
    p = sub.add_parser("replay"); p.add_argument("--session", required=True); p.add_argument("--speed", type=float, default=1.0)
    p = sub.add_parser("calibrate"); p.add_argument("phase", choices=["empty", "walk", "zone"]); p.add_argument("--minutes", type=int, default=10); p.add_argument("--name", default=None, help="zone name (phase 'zone' only)")
    p = sub.add_parser("telegram-connect", help="wire Telegram alerts: create a bot with @BotFather, message it once, then run this with the token"); p.add_argument("--token", required=True)
    a = ap.parse_args()
    cfg = Config.load()

    if a.cmd == "status":
        for name in ("state.json",):
            f = cfg.aura_home / name
            print(f.read_text() if f.exists() else "{}")
        alerts = cfg.aura_home / "alerts.jsonl"
        if alerts.exists():
            lines = alerts.read_text().strip().splitlines()
            print("last alert:", lines[-1] if lines else "none")

    elif a.cmd == "replay":
        from aura.ear.ear import replay
        replay(Path(a.session), cfg.aura_home / "frames.jsonl", speed=a.speed)

    elif a.cmd in ("record", "run-ear"):
        from aura.ear.ear import Ear, ScanPoller, LinkPoller, BlePoller
        out = (Path("data/sessions") / a.session / "frames.jsonl") if a.cmd == "record" \
            else cfg.aura_home / "frames.jsonl"
        out.parent.mkdir(parents=True, exist_ok=True)
        stop = threading.Event()
        ear = Ear(cfg, ScanPoller(cfg), LinkPoller(cfg), BlePoller())
        t = threading.Thread(target=ear.run_forever, args=(out, stop)); t.start()
        try:
            if a.cmd == "record" and a.minutes:
                time.sleep(a.minutes * 60)
            else:
                while True:
                    time.sleep(60)
        except KeyboardInterrupt:
            pass
        stop.set(); t.join()

    elif a.cmd == "run-brain":
        from aura.brain.brain import run_brain
        model = Path(__file__).parent.parent / "models" / "aura.onnx"
        run_brain(cfg, cfg.aura_home / "frames.jsonl", threading.Event(),
                  model_path=model if model.exists() else None)

    elif a.cmd == "run-guardian":
        from aura.guardian.guardian import run_guardian
        run_guardian(cfg, threading.Event())

    elif a.cmd == "run-face":
        from aura.face.server import run_face
        run_face(cfg)

    elif a.cmd == "run-bridge":
        from aura.face.bridge import run_bridge
        run_bridge(cfg, threading.Event())

    elif a.cmd == "telegram-connect":
        from aura.guardian.notify import telegram_connect, _http_sender
        chat_id, name = telegram_connect(a.token)
        cfg_path = cfg.aura_home / "config.json"
        merged = json.loads(cfg_path.read_text()) if cfg_path.exists() else {}
        merged.update({"telegram_token": a.token, "telegram_chat_id": chat_id})
        cfg_path.write_text(json.dumps(merged))
        _http_sender(f"https://api.telegram.org/bot{a.token}/sendMessage",
                     {"chat_id": chat_id, "text": "✅ Aura connected — alerts will arrive here."})
        print(f"connected to chat {chat_id} ({name or 'unnamed'}); config written: {cfg_path}")
        print("restart the guardian to pick it up: sudo systemctl restart aura-guardian")

    elif a.cmd == "calibrate":
        from aura.frames import read_frames
        from aura.brain.calibrate import calibrate_empty, calibrate_walk, calibrate_zone
        if a.phase == "zone" and not a.name:
            raise SystemExit("calibrate zone needs --name")
        print(f"Capturing {a.minutes} min of live frames for phase '{a.phase}'...")
        t0 = time.time()
        time.sleep(a.minutes * 60)
        frames = [f for f in read_frames(cfg.aura_home / "frames.jsonl") if f.ts >= t0]
        cal_path = cfg.aura_home / "calibration.json"
        if a.phase == "empty":
            cal = calibrate_empty(frames, cfg.top_k)
        elif a.phase == "zone":
            cal = calibrate_zone(frames, json.loads(cal_path.read_text()), a.name)
        else:
            cal = calibrate_walk(frames, json.loads(cal_path.read_text()))
        cal_path.write_text(json.dumps(cal))
        print("calibration written:", cal_path)

if __name__ == "__main__":
    main()
