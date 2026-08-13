from aura.frames import RFFrame, hash_mac, append_frame, read_frames

def test_hash_mac_stable_and_case_insensitive():
    a = hash_mac("AA:BB:CC:DD:EE:FF", "salt1")
    b = hash_mac("aa:bb:cc:dd:ee:ff", "salt1")
    assert a == b and len(a) == 8
    assert hash_mac("AA:BB:CC:DD:EE:FF", "salt2") != a

def test_roundtrip(tmp_path):
    p = tmp_path / "frames.jsonl"
    f1 = RFFrame(ts=100.0, wifi={"ab12cd34": -60.0}, link=[-55.0, -56.0], ble={})
    f2 = RFFrame(ts=100.25, wifi={"ab12cd34": -61.0}, link=[-55.5], ble={"ffee0011": -70.0})
    append_frame(p, f1); append_frame(p, f2)
    out = read_frames(p)
    assert out == [f1, f2]

def test_read_skips_corrupt_lines(tmp_path):
    p = tmp_path / "frames.jsonl"
    append_frame(p, RFFrame(ts=1.0, wifi={}, link=[], ble={}))
    with open(p, "a") as fh:
        fh.write("{corrupt\n")
    append_frame(p, RFFrame(ts=2.0, wifi={}, link=[], ble={}))
    assert [f.ts for f in read_frames(p)] == [1.0, 2.0]

def test_read_skips_valid_json_non_dict_lines(tmp_path):
    p = tmp_path / "frames.jsonl"
    append_frame(p, RFFrame(ts=1.0, wifi={}, link=[], ble={}))
    with open(p, "a") as fh:
        fh.write("42\n"); fh.write("null\n"); fh.write("[]\n"); fh.write('"hello"\n'); fh.write("true\n")
    append_frame(p, RFFrame(ts=2.0, wifi={}, link=[], ble={}))
    assert [f.ts for f in read_frames(p)] == [1.0, 2.0]

def test_read_normalizes_null_fields(tmp_path):
    p = tmp_path / "frames.jsonl"
    with open(p, "w") as fh:
        fh.write('{"ts": 5.0, "wifi": null, "link": null, "ble": null}\n')
    out = read_frames(p)
    assert out[0].wifi == {} and out[0].link == [] and out[0].ble == {}

def test_tail_frames_defers_partial_line_and_stops(tmp_path):
    import threading, time
    from aura.frames import tail_frames
    p = tmp_path / "f.jsonl"
    append_frame(p, RFFrame(ts=1.0, wifi={}, link=[], ble={}))
    with open(p, "a", encoding="utf-8") as fh:
        fh.write('{"ts": 2.0')  # partial write, no newline
    stop, got = threading.Event(), []
    t = threading.Thread(target=lambda: [got.append(f.ts) for f in tail_frames(p, poll_s=0.05, stop_event=stop)])
    t.start(); time.sleep(0.3)
    assert got == [1.0]
    with open(p, "a", encoding="utf-8") as fh:
        fh.write(', "wifi": {}, "link": [], "ble": {}}\n')
    time.sleep(0.3)
    assert got == [1.0, 2.0]
    stop.set(); t.join(timeout=2)
    assert not t.is_alive()

def test_tail_frames_from_end_skips_history(tmp_path):
    import threading, time
    from aura.frames import tail_frames
    p = tmp_path / "f.jsonl"
    for i in range(3):
        append_frame(p, RFFrame(ts=float(i), wifi={}, link=[], ble={}))
    stop, got = threading.Event(), []
    t = threading.Thread(target=lambda: [got.append(f.ts) for f in tail_frames(p, poll_s=0.05, from_end=True, stop_event=stop)])
    t.start(); time.sleep(0.2)
    append_frame(p, RFFrame(ts=99.0, wifi={}, link=[], ble={}))
    time.sleep(0.3)
    assert got == [99.0]
    stop.set(); t.join(timeout=2)

def test_tail_frames_survives_rotation(tmp_path):
    import threading, time
    from aura.frames import tail_frames
    p = tmp_path / "f.jsonl"
    for i in range(5):
        append_frame(p, RFFrame(ts=float(i), wifi={}, link=[], ble={}))
    stop, got = threading.Event(), []
    t = threading.Thread(target=lambda: [got.append(f.ts) for f in tail_frames(p, poll_s=0.05, stop_event=stop)])
    t.start(); time.sleep(0.3)
    assert got == [0.0, 1.0, 2.0, 3.0, 4.0]
    p.rename(p.with_suffix(".jsonl.old"))          # Ear rotation
    append_frame(p, RFFrame(ts=100.0, wifi={}, link=[], ble={}))  # fresh, smaller file
    time.sleep(0.4)
    assert 100.0 in got
    stop.set(); t.join(timeout=2)
