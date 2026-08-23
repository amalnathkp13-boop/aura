import json, os, secrets
from dataclasses import dataclass, fields
from pathlib import Path
from typing import Optional

@dataclass
class Config:
    aura_home: Path
    salt: str
    frame_hz: float = 4.0
    scan_interval: float = 3.0
    top_k: int = 16
    window_seconds: float = 15.0
    detector: str = "rfsense"          # rfsense | baseline | cnn ("ruview" = legacy alias)
    telegram_token: str = ""
    telegram_chat_id: str = ""
    serial_port: str = ""
    gateway_ip: str = ""

    @classmethod
    def load(cls, path: Optional[Path] = None) -> "Config":
        home = Path(os.environ.get("AURA_HOME", Path.home() / ".aura"))
        home.mkdir(parents=True, exist_ok=True)
        salt_file = home / "salt"
        if not salt_file.exists():
            salt_file.write_text(secrets.token_hex(16))
        overrides = {}
        cfg_file = path or (home / "config.json")
        if cfg_file.exists():
            overrides = json.loads(cfg_file.read_text())
        known = {f.name for f in fields(cls)} - {"aura_home", "salt"}
        overrides = {k: v for k, v in overrides.items() if k in known}
        if overrides.get("detector") == "ruview":   # pre-rename config files
            overrides["detector"] = "rfsense"
        return cls(aura_home=home, salt=salt_file.read_text().strip(), **overrides)
