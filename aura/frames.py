import hashlib, json, time
from dataclasses import dataclass, asdict, field
from pathlib import Path

@dataclass
class RFFrame:
    ts: float
    wifi: dict = field(default_factory=dict)
    link: list = field(default_factory=list)
    ble: dict = field(default_factory=dict)

def hash_mac(mac: str, salt: str) -> str:
    return hashlib.sha1((mac.lower() + salt).encode()).hexdigest()[:8]

def append_frame(path: Path, f: RFFrame) -> None:
    with open(path, "a", encoding="utf-8") as fh:
        fh.write(json.dumps(asdict(f)) + "\n")

def _parse(line: str):
    try:
        d = json.loads(line)
        if not isinstance(d, dict):
            return None
        return RFFrame(ts=float(d["ts"]), wifi=d.get("wifi") or {},
                       link=d.get("link") or [], ble=d.get("ble") or {})
    except (json.JSONDecodeError, KeyError, TypeError, ValueError):
        return None

def read_frames(path: Path):
    if not Path(path).exists():
        return []
    out = []
    for line in Path(path).read_text(encoding="utf-8").splitlines():
        f = _parse(line)
        if f:
            out.append(f)
    return out

def tail_frames(path: Path, poll_s: float = 0.25):
    pos = 0
    while True:
        p = Path(path)
        if p.exists():
            with open(p, "r", encoding="utf-8") as fh:
                fh.seek(pos)
                while True:
                    line = fh.readline()
                    if not line:
                        break
                    if not line.endswith("\n"):
                        break
                    pos = fh.tell()
                    f = _parse(line)
                    if f:
                        yield f
        time.sleep(poll_s)
