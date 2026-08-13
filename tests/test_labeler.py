from aura.labeler.labeler import write_label, read_labels

def test_label_roundtrip(tmp_path):
    p = tmp_path / "labels.jsonl"
    write_label(p, 100.0, 1, 0.25)
    write_label(p, 101.0, 0, 0.0)
    out = read_labels(p)
    assert out == [{"ts": 100.0, "person": 1, "motion": 0.25},
                   {"ts": 101.0, "person": 0, "motion": 0.0}]
