import json

def _http_sender(url, payload):
    import requests
    requests.post(url, json=payload, timeout=10)

class Notifier:
    MSG = {"intrusion": "🚨 Aura: motion detected while armed!",
           "inactivity": "🩺 Aura: no movement detected for the configured period."}

    def __init__(self, cfg, sender=None):
        self.cfg = cfg
        self.sender = sender or _http_sender

    def send(self, alert: dict):
        with open(self.cfg.aura_home / "alerts.jsonl", "a", encoding="utf-8") as fh:
            fh.write(json.dumps(alert) + "\n")
        if self.cfg.telegram_token and self.cfg.telegram_chat_id:
            url = f"https://api.telegram.org/bot{self.cfg.telegram_token}/sendMessage"
            try:
                self.sender(url, {"chat_id": self.cfg.telegram_chat_id,
                                  "text": self.MSG.get(alert["type"], str(alert))})
            except Exception:
                pass
