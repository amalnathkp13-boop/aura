import numpy as np
from pathlib import Path
from aura.frames import RFFrame, append_frame
from aura.labeler.labeler import write_label

def _make_session(root, name, jitter, person, n=300, seed=0):
    d = root / name; d.mkdir(parents=True)
    rng = np.random.default_rng(seed)
    for i in range(n):
        append_frame(d / "frames.jsonl", RFFrame(
            ts=i * 0.25, wifi={"aaaaaaaa": -60 + jitter * np.sin(i / 3) + rng.normal(0, jitter / 2)},
            link=[-50.0], ble={}))
        if i % 4 == 0:
            write_label(d / "labels.jsonl", i * 0.25, person, 0.05 if person else 0.0)
    return d

def test_build_dataset(tmp_path):
    from training.dataset import build_dataset
    s1 = _make_session(tmp_path, "empty1", 0.3, 0)
    s2 = _make_session(tmp_path, "move1", 4.0, 1, seed=1)
    out = tmp_path / "ds.npz"
    build_dataset([s1, s2], ["aaaaaaaa"], out)
    d = np.load(out, allow_pickle=True)
    assert d["x"].shape[1:] == (2, 60)      # 1 link + link-stream
    assert set(d["y_presence"]) == {0, 1}
    assert len(d["x"]) == len(d["session"])
    assert d["x"].dtype == np.float32
    assert d["y_presence"].dtype == np.float32 and d["y_motion"].dtype == np.float32

def test_train_and_export_onnx(tmp_path):
    from training.dataset import build_dataset
    from training.train import train
    s1 = _make_session(tmp_path, "empty1", 0.3, 0)
    s2 = _make_session(tmp_path, "move1", 4.0, 1, seed=1)
    npz = tmp_path / "ds.npz"
    build_dataset([s1, s2], ["aaaaaaaa"], npz)
    onnx_path = tmp_path / "m.onnx"
    metrics = train(npz, val_sessions=["move1"], out=onnx_path, epochs=2)
    assert onnx_path.exists()
    assert 0.0 <= metrics["val_presence_acc"] <= 1.0
    import onnxruntime as ort
    sess = ort.InferenceSession(str(onnx_path))
    x = np.zeros((1, 2, 60), dtype=np.float32)
    outs = sess.run(None, {"rf": x})
    assert len(outs) == 3
