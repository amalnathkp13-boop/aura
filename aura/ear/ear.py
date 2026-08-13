import subprocess, threading, time
from pathlib import Path
from aura.frames import RFFrame, append_frame, read_frames, hash_mac
from aura.ear.parse import parse_scan, parse_station_signal, parse_bluetoothctl_line

class Ear:
    def __init__(self, cfg, wifi_poller, link_poller, ble_poller):
        self.cfg = cfg
        self.wifi, self.link, self.ble = wifi_poller, link_poller, ble_poller

    def run_forever(self, out_path: Path, stop_event: threading.Event):
        for p in (self.wifi, self.link, self.ble):
            p.start()
        period = 1.0 / self.cfg.frame_hz
        try:
            while not stop_event.is_set():
                t0 = time.time()
                f = RFFrame(
                    ts=t0,
                    wifi={hash_mac(m, self.cfg.salt): v for m, v in (self.wifi.latest() or {}).items()},
                    link=list(self.link.latest() or []),
                    ble={hash_mac(m, self.cfg.salt): v for m, v in (self.ble.latest() or {}).items()},
                )
                append_frame(out_path, f)
                _rotate(out_path)
                stop_event.wait(max(0.0, period - (time.time() - t0)))
        finally:
            for p in (self.wifi, self.link, self.ble):
                p.stop()

def _rotate(path: Path, max_bytes: int = 50_000_000):
    if path.exists() and path.stat().st_size > max_bytes:
        path.rename(path.with_suffix(".jsonl.old"))

def replay(session_path: Path, out_path: Path, speed: float = 1.0):
    frames = read_frames(session_path)
    if not frames:
        return
    base = frames[0].ts
    start = time.time()
    for f in frames:
        delay = (f.ts - base) / speed - (time.time() - start)
        if delay > 0:
            time.sleep(delay)
        append_frame(out_path, RFFrame(ts=time.time(), wifi=f.wifi, link=f.link, ble=f.ble))

# ---- real pollers (board-only; no unit tests — exercised by `aura record` on the board) ----

class _SubprocessPoller(threading.Thread):
    def __init__(self):
        super().__init__(daemon=True)
        self._latest, self._stop = None, threading.Event()
    def latest(self): return self._latest
    def stop(self): self._stop.set()

class ScanPoller(_SubprocessPoller):
    def __init__(self, cfg):
        super().__init__(); self.cfg = cfg
    def run(self):
        while not self._stop.is_set():
            try:
                out = subprocess.run(["sudo", "iw", "dev", "wlan0", "scan"],
                                     capture_output=True, text=True, timeout=15).stdout
                self._latest = parse_scan(out)
            except Exception:
                pass
            self._stop.wait(self.cfg.scan_interval)

class LinkPoller(_SubprocessPoller):
    def __init__(self, cfg):
        super().__init__(); self.cfg = cfg; self._buf = []
        self._ping = None
    def run(self):
        if self.cfg.gateway_ip:
            self._ping = subprocess.Popen(["ping", "-i", "0.2", self.cfg.gateway_ip],
                                          stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        while not self._stop.is_set():
            try:
                out = subprocess.run(["sudo", "iw", "dev", "wlan0", "station", "dump"],
                                     capture_output=True, text=True, timeout=5).stdout
                s = parse_station_signal(out)
                if s is not None:
                    self._buf = (self._buf + [s])[-8:]
                    self._latest = list(self._buf)
            except Exception:
                pass
            self._stop.wait(0.15)
    def stop(self):
        super().stop()
        if self._ping:
            self._ping.terminate()

class BlePoller(_SubprocessPoller):
    def run(self):
        try:
            proc = subprocess.Popen(["bluetoothctl", "scan", "on"], stdout=subprocess.PIPE, text=True)
        except FileNotFoundError:
            return
        devices = {}
        for line in proc.stdout:
            if self._stop.is_set():
                break
            hit = parse_bluetoothctl_line(line)
            if hit:
                devices[hit[0]] = hit[1]
                self._latest = dict(devices)
        proc.terminate()
