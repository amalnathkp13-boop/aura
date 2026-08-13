import argparse
import numpy as np
import torch, torch.nn as nn
from pathlib import Path

class AuraNet(nn.Module):
    def __init__(self, channels: int):
        super().__init__()
        self.body = nn.Sequential(
            nn.Conv1d(channels, 32, 5, stride=2, padding=2), nn.BatchNorm1d(32), nn.ReLU(),
            nn.Conv1d(32, 64, 5, stride=2, padding=2), nn.BatchNorm1d(64), nn.ReLU(),
            nn.Conv1d(64, 64, 3, padding=1), nn.ReLU(),
            nn.AdaptiveAvgPool1d(1), nn.Flatten())
        self.presence = nn.Linear(64, 1)
        self.motion = nn.Linear(64, 1)
        self.activity = nn.Linear(64, 1)

    def forward(self, x):
        h = self.body(x)
        return self.presence(h).squeeze(1), self.motion(h).squeeze(1), self.activity(h).squeeze(1)

def train(npz: Path, val_sessions, out: Path, epochs: int = 30, lr: float = 1e-3):
    d = np.load(npz, allow_pickle=True)
    val_mask = np.isin(d["session"], list(val_sessions))
    def tensors(mask):
        return (torch.tensor(d["x"][mask]), torch.tensor(d["y_presence"][mask], dtype=torch.float32),
                torch.tensor(d["y_motion"][mask], dtype=torch.float32),
                torch.tensor(d["y_activity"][mask], dtype=torch.float32))
    xtr, ptr, mtr, atr = tensors(~val_mask)
    xva, pva, mva, ava = tensors(val_mask)
    model = AuraNet(channels=d["x"].shape[1])
    opt = torch.optim.Adam(model.parameters(), lr=lr)
    bce, mse = nn.BCEWithLogitsLoss(), nn.MSELoss()
    for ep in range(epochs):
        model.train()
        perm = torch.randperm(len(xtr))
        for i in range(0, len(perm), 64):
            idx = perm[i:i + 64]
            opt.zero_grad()
            lp, lm, la = model(xtr[idx])
            loss = bce(lp, ptr[idx]) + bce(lm, mtr[idx]) + mse(la, atr[idx]) / 1000.0
            loss.backward(); opt.step()
    model.eval()
    with torch.no_grad():
        lp, lm, la = model(xva) if len(xva) else model(xtr)
        ref_p = pva if len(xva) else ptr
        acc = float(((torch.sigmoid(lp) > 0.5).float() == ref_p).float().mean())
    out.parent.mkdir(parents=True, exist_ok=True)
    torch.onnx.export(model, torch.zeros(1, d["x"].shape[1], 60), str(out),
                      input_names=["rf"], output_names=["presence", "motion", "activity"],
                      dynamic_axes={"rf": {0: "batch"}}, opset_version=18)
    metrics = {"val_presence_acc": acc, "n_train": int((~val_mask).sum()), "n_val": int(val_mask.sum())}
    print(metrics)
    return metrics

if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--npz", required=True, type=Path)
    ap.add_argument("--val-sessions", default="", type=str)
    ap.add_argument("--out", required=True, type=Path)
    ap.add_argument("--epochs", type=int, default=30)
    a = ap.parse_args()
    train(a.npz, [s for s in a.val_sessions.split(",") if s], a.out, a.epochs)
