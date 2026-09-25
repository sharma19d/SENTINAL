"""
Reproducible training for SENTINEL's anomaly model.

The deployed model (sentinel/models/sentinel_lstm.onnx) was trained in a Colab
notebook that is not in this repository. Its architecture is recovered here
from the checkpoint's weight shapes, and the parameter count reproduces exactly
(153,651), so this script trains the same network — but on a leakage-free split
with a committed procedure, which is what a published result needs.

Architecture (sequence-to-sequence LSTM autoencoder):
    encoder   LSTM(115 -> 64, 2 layers)            46,336 + 33,280
    latent    final hidden state, repeated over the 10 timesteps
    decoder   LSTM(64 -> 64, 2 layers)             33,280 + 33,280
    output    Linear(64 -> 115)                     7,475
                                                  -------
                                                  153,651

Pre-registered choices (fixed before evaluation, recorded in the output):
    * scaler      MinMaxScaler(0,1) fit on the TRAIN split only (the deployed
                  scaler was fit on all benign rows of these devices, including
                  what a test set would hold)
    * threshold   99th percentile of the validation-benign window scores, i.e.
                  a ~1% false-positive budget chosen WITHOUT looking at attacks
    * optimiser   Adam, lr 1e-3, batch 256, <=50 epochs, early stop on val loss
                  (patience 5), best-val checkpoint restored
    * score       mean squared reconstruction error over the whole (10,115)
                  window — identical to sentinel/agents/anomaly/inference.py

Usage:  python3 train_anomaly.py --seed 0 --out /content/runs/seed0
"""
import argparse, json, os, pickle, sys, time
import numpy as np
import torch
import torch.nn as nn
from sklearn.preprocessing import MinMaxScaler

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import nbaiot as nb


class LSTMAutoencoder(nn.Module):
    def __init__(self, n_features=115, hidden=64, layers=2, seq_len=nb.WINDOW):
        super().__init__()
        self.seq_len = seq_len
        self.encoder = nn.LSTM(n_features, hidden, layers, batch_first=True)
        self.decoder = nn.LSTM(hidden, hidden, layers, batch_first=True)
        self.output_layer = nn.Linear(hidden, n_features)

    def forward(self, x):
        _, (h, _) = self.encoder(x)
        z = h[-1].unsqueeze(1).repeat(1, self.seq_len, 1)
        y, _ = self.decoder(z)
        return self.output_layer(y)


def window_scores(model, W, device, bs=4096):
    model.eval(); out = []
    with torch.no_grad():
        for i in range(0, len(W), bs):
            b = torch.from_numpy(W[i:i + bs]).to(device)
            out.append(((b - model(b)) ** 2).mean(dim=(1, 2)).cpu().numpy())
    return np.concatenate(out) if out else np.empty(0)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--seed", type=int, default=0)
    ap.add_argument("--out", required=True)
    ap.add_argument("--features", default="/content/orig/feature_order.csv")
    ap.add_argument("--epochs", type=int, default=50)
    ap.add_argument("--percentile", type=float, default=99.0)
    a = ap.parse_args()
    os.makedirs(a.out, exist_ok=True)

    torch.manual_seed(a.seed); np.random.seed(a.seed)
    torch.backends.cudnn.deterministic = True; torch.backends.cudnn.benchmark = False
    dev = "cuda" if torch.cuda.is_available() else "cpu"

    cols = nb.feature_order(a.features)
    s = nb.benign_split(cols)
    scaler = MinMaxScaler().fit(np.concatenate(s.train))           # train only
    tr = np.concatenate([nb.windows(scaler.transform(x).astype(np.float32), 1) for x in s.train])
    va = np.concatenate([nb.windows(scaler.transform(x).astype(np.float32), 1) for x in s.val])
    print(f"train windows {len(tr):,}  val windows {len(va):,}  device {dev}", flush=True)

    model = LSTMAutoencoder().to(dev)
    n_params = sum(p.numel() for p in model.parameters())
    assert n_params == 153_651, f"architecture drifted from deployed model: {n_params}"
    opt = torch.optim.Adam(model.parameters(), lr=1e-3)
    loss_fn = nn.MSELoss()
    trt = torch.from_numpy(tr)

    best, best_state, bad, hist = float("inf"), None, 0, []
    for ep in range(a.epochs):
        model.train(); t0 = time.time(); perm = torch.randperm(len(trt)); run = 0.0
        for i in range(0, len(trt), 256):
            b = trt[perm[i:i + 256]].to(dev)
            loss = loss_fn(model(b), b)
            opt.zero_grad(); loss.backward(); opt.step()
            run += loss.item() * len(b)
        vl = float(window_scores(model, va, dev).mean())
        hist.append({"epoch": ep + 1, "train": run / len(trt), "val": vl})
        print(f"ep {ep+1:2d} train {run/len(trt):.6f} val {vl:.6f} ({time.time()-t0:.1f}s)", flush=True)
        if vl < best - 1e-7:
            best, bad = vl, 0
            best_state = {k: v.detach().clone() for k, v in model.state_dict().items()}
        else:
            bad += 1
            if bad >= 5:
                print("early stop", flush=True); break
    model.load_state_dict(best_state)

    val_scores = window_scores(model, va, dev)
    thr = float(np.percentile(val_scores, a.percentile))
    torch.save(model.state_dict(), f"{a.out}/model.pt")
    pickle.dump(scaler, open(f"{a.out}/scaler.pkl", "wb"))
    # Metadata (incl. the threshold) is written BEFORE the ONNX export. An
    # earlier version wrote it after, so a failed export silently discarded
    # the threshold and the training history of an otherwise complete run.
    json.dump({"seed": a.seed, "threshold": thr, "percentile": a.percentile,
               "n_params": n_params, "best_val": best, "history": hist,
               "train_windows": int(len(tr)), "val_windows": int(len(va))},
              open(f"{a.out}/meta.json", "w"), indent=2)
    print(f"threshold (p{a.percentile:g} of val benign) = {thr:.6g}", flush=True)

    # ONNX is the deployment artefact, not an input to evaluation, so a failed
    # export is reported but does not fail the run. The legacy TorchScript
    # exporter (dynamo=False) emits native ONNX LSTM ops, matching the graph of
    # the deployed sentinel_lstm.onnx.
    model.cpu().eval()
    try:
        torch.onnx.export(model, torch.zeros(1, nb.WINDOW, 115), f"{a.out}/model.onnx",
                          input_names=["input"], output_names=["reconstruction"],
                          dynamic_axes={"input": {0: "batch_size"}, "reconstruction": {0: "batch_size"}},
                          opset_version=17, dynamo=False)
        print("onnx exported", flush=True)
    except Exception as e:                                    # pragma: no cover
        print(f"WARNING onnx export failed: {e}", flush=True)


if __name__ == "__main__":
    main()
