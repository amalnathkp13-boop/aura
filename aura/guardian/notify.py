import json

def _http_sender(url, payload):
    import requests
    requests.post(url, json=payload, timeout=10)

def _http_fetch(url):
    import requests
    return requests.get(url, timeout=10).json()

def telegram_connect(token: str, fetch=None):
    """Resolve the alert chat for a bot token: the user creates a bot with
    @BotFather, sends it any message, and we read the chat id back from
    getUpdates. Returns (chat_id, display_name); raises with instructions when
    the bot has not been messaged yet."""
    fetch = fetch or _http_fetch
    upd = fetch(f"https://api.telegram.org/bot{token}/getUpdates")
    chats = [u["message"]["chat"] for u in (upd.get("result") or [])
             if u.get("message", {}).get("chat")]
    if not chats:
        raise RuntimeError(
            "no messages found for this bot - open Telegram, send your bot any "
            "message (e.g. /start), then rerun telegram-connect")
    chat = chats[-1]
    return str(chat["id"]), chat.get("first_name") or chat.get("title") or ""

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
