from collections import Counter
import numpy as np

def select_links(frames, k: int = 16):
    counts = Counter()
    for f in frames:
        counts.update(f.wifi.keys())
    return [bid for bid, _ in sorted(counts.items(), key=lambda x: (-x[1], x[0]))[:k]]

def _series(frames, bid):
    vals, last = [], np.nan
    for f in frames:
        last = f.wifi.get(bid, last)
        vals.append(last)
    return np.array(vals, dtype=np.float64)

def _link_series(frames):
    vals, last = [], np.nan
    for f in frames:
        if f.link:
            last = float(np.mean(f.link))
        vals.append(last)
    return np.array(vals, dtype=np.float64)

def _norm(x, out_len):
    if np.all(np.isnan(x)):
        return np.zeros(out_len, dtype=np.float32)
    idx = np.arange(len(x), dtype=np.float64)
    good = ~np.isnan(x)
    x = np.interp(idx, idx[good], x[good])
    x = np.interp(np.linspace(0, len(x) - 1, out_len), idx, x)
    x = (x - np.median(x)) / 5.0
    return np.clip(x, -4, 4).astype(np.float32)

def build_matrix(frames, link_ids, out_len: int = 60):
    rows = [_norm(_series(frames, bid), out_len) for bid in link_ids]
    rows.append(_norm(_link_series(frames), out_len))
    return np.stack(rows)

def summary(matrix, window_seconds: float = 15.0):
    diffs = np.diff(matrix, axis=1)
    motion_energy = float(np.mean(np.std(diffs, axis=1)))
    fs = matrix.shape[1] / window_seconds
    freqs = np.fft.rfftfreq(matrix.shape[1], d=1.0 / fs)
    power = np.abs(np.fft.rfft(matrix, axis=1)) ** 2
    band = (freqs >= 0.5) & (freqs <= 3.0)
    total = power[:, 1:].sum(axis=1)
    with np.errstate(invalid="ignore", divide="ignore"):
        frac = np.where(total > 0, power[:, band].sum(axis=1) / total, 0.0)
    band_energy = float(np.mean(frac))
    var = np.var(diffs, axis=1)
    top = diffs[np.argsort(var)[-5:]]
    if top.shape[0] >= 2 and np.all(np.std(top, axis=1) > 0):
        c = np.corrcoef(top)
        xcorr = float(np.mean(np.abs(c[np.triu_indices_from(c, 1)])))
    else:
        xcorr = 0.0
    return {"motion_energy": motion_energy, "band_energy": band_energy, "xcorr": xcorr}
