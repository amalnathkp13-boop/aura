import re

_BSS = re.compile(r"^BSS ([0-9a-f:]{17})", re.M | re.I)
_SIG = re.compile(r"signal: (-?\d+(?:\.\d+)?) dBm")
_STA_SIG = re.compile(r"signal:\s+(-?\d+)")
_BLE = re.compile(r"Device ([0-9A-Fa-f:]{17}) RSSI: (-?\d+)")

def parse_scan(text: str) -> dict:
    out = {}
    blocks = _BSS.split(text)
    for i in range(1, len(blocks), 2):
        m = _SIG.search(blocks[i + 1])
        if m:
            out[blocks[i].lower()] = float(m.group(1))
    return out

def parse_station_signal(text: str):
    m = _STA_SIG.search(text)
    return float(m.group(1)) if m else None

def parse_bluetoothctl_line(line: str):
    m = _BLE.search(line)
    return (m.group(1).lower(), float(m.group(2))) if m else None
