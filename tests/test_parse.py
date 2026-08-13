from pathlib import Path
from aura.ear.parse import parse_scan, parse_station_signal, parse_bluetoothctl_line

FIX = Path(__file__).parent / "fixtures"

def test_parse_scan():
    out = parse_scan((FIX / "iw_scan.txt").read_text())
    assert out == {"aa:bb:cc:dd:ee:01": -58.0, "aa:bb:cc:dd:ee:02": -71.5}

def test_parse_scan_empty():
    assert parse_scan("") == {}

def test_parse_station_signal():
    assert parse_station_signal((FIX / "station_dump.txt").read_text()) == -54.0
    assert parse_station_signal("no stations") is None

def test_parse_ble_line():
    assert parse_bluetoothctl_line("[CHG] Device 4C:87:5D:11:22:33 RSSI: -67") == ("4c:87:5d:11:22:33", -67.0)
    assert parse_bluetoothctl_line("[NEW] Device 4C:87:5D:11:22:33 SomeName") is None
    assert parse_bluetoothctl_line("") is None
