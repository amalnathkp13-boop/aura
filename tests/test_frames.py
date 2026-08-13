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
