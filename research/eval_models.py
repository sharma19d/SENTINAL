"""
Score the reproducible LSTM autoencoder (5 seeds) and two baselines on the
identical N-BaIoT protocol defined in nbaiot.py.

Baselines, chosen to isolate what SENTINEL's design choices contribute:

  * IsolationForest  (Liu, Ting & Zhou, ICDM 2008) on the flattened (10,115)
    window. A standard unsupervised detector; tells us whether a neural model is
    needed at all.
  * DenseAE          the deep autoencoder N-BaIoT's authors used (Meidan et al.,
    IEEE Pervasive Computing 2018): hidden widths floor(115 x {0.75, 0.50,
    0.33, 0.25}) = 86-57-37-28, mirrored for the decoder, tanh, linear output,
    scoring each row independently. The
    window score is the mean of its rows' errors, so it sees the same data as
    the LSTM but WITHOUT temporal modelling — isolating the value of sequences.

Every model uses the same pre-registered threshold rule: the 99th percentile of
its own validation-benign window scores (a ~1% false-positive budget, set
without looking at attack traffic). Per-window scores are saved so ROC/AUC and
threshold sweeps can be computed later without re-running inference.
"""
import json, os, pickle, sys, time
import numpy as np
import torch
import torch.nn as nn
from sklearn.ensemble import IsolationForest
from sklearn.preprocessing import MinMaxScaler

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import nbaiot as nb
from train_anomaly import LSTMAutoencoder

DEV = "cuda" if torch.cuda.is_available() else "cpu"
RUNS = "/content/runs"
SEEDS = [0, 1, 2, 3, 4]


class DenseAE(nn.Module):
    def __init__(self, n=115):
        super().__init__()
        h = [int(n * r) for r in (0.75, 0.5, 0.33, 0.25)]           # 86, 57, 37, 28
        enc, dec, d = [], [], n
        for w in h:
            enc += [nn.Linear(d, w), nn.Tanh()]; d = w
        for w in reversed([n] + h[:-1]):
            dec += [nn.Linear(d, w), nn.Tanh()]; d = w
        dec[-1] = nn.Identity()                                     # linear output
        self.net = nn.Sequential(*enc, *dec)

    def forward(self, x):
        return self.net(x)


def lstm_scorer(seed):
    m = LSTMAutoencoder().to(DEV)
    m.load_state_dict(torch.load(f"{RUNS}/seed{seed}/model.pt", map_location=DEV)); m.eval()
    sc = pickle.load(open(f"{RUNS}/seed{seed}/scaler.pkl", "rb"))
    thr = json.load(open(f"{RUNS}/seed{seed}/meta.json"))["threshold"]

    def f(rows):
        W = nb.windows(sc.transform(rows).astype(np.float32), nb.WINDOW)
        out = []
        with torch.no_grad():
            for i in range(0, len(W), 8192):
                b = torch.from_numpy(W[i:i + 8192]).to(DEV)
                out.append(((b - m(b)) ** 2).mean(dim=(1, 2)).cpu().numpy())
        return np.concatenate(out) if out else np.empty(0)
    return f, thr


def train_dense(split, seed):
    torch.manual_seed(seed); np.random.seed(seed)
    sc = MinMaxScaler().fit(np.concatenate(split.train))
    tr = torch.from_numpy(sc.transform(np.concatenate(split.train)).astype(np.float32))
    m = DenseAE().to(DEV); opt = torch.optim.Adam(m.parameters(), lr=1e-3); lf = nn.MSELoss()

    def f(rows):
        X = torch.from_numpy(sc.transform(rows).astype(np.float32))
        with torch.no_grad():
            e = []
            for i in range(0, len(X), 65536):
                b = X[i:i + 65536].to(DEV); e.append(((b - m(b)) ** 2).mean(1).cpu().numpy())
        e = np.concatenate(e) if e else np.empty(0)
        n = (len(e) // nb.WINDOW) * nb.WINDOW                       # same windows as LSTM
        return e[:n].reshape(-1, nb.WINDOW).mean(1)

    best, state, bad = float("inf"), None, 0
    for ep in range(50):
        m.train(); perm = torch.randperm(len(tr))
        for i in range(0, len(tr), 256):
            b = tr[perm[i:i + 256]].to(DEV); loss = lf(m(b), b)
            opt.zero_grad(); loss.backward(); opt.step()
        m.eval(); vl = float(np.mean(np.concatenate([f(v) for v in split.val])))
        if vl < best - 1e-7: best, bad, state = vl, 0, {k: v.clone() for k, v in m.state_dict().items()}
        else:
            bad += 1
            if bad >= 5: break
    m.load_state_dict(state); m.eval()
    thr = float(np.percentile(np.concatenate([f(v) for v in split.val]), 99))
    return f, thr


def train_iforest(split, seed):
    sc = MinMaxScaler().fit(np.concatenate(split.train))
    flat = lambda rows: nb.windows(sc.transform(rows).astype(np.float32), nb.WINDOW).reshape(-1, nb.WINDOW * 115)
    Xtr = np.concatenate([flat(x) for x in split.train])
    clf = IsolationForest(n_estimators=100, random_state=seed, n_jobs=-1).fit(Xtr)
    f = lambda rows: -clf.score_samples(flat(rows)) if len(rows) >= nb.WINDOW else np.empty(0)
    thr = float(np.percentile(np.concatenate([f(v) for v in split.val]), 99))
    return f, thr


def evaluate(name, f, thr, split, cols):
    r = {"model": name, "threshold": thr, "benign": {}, "attack": {}}
    for group, dd in (("in_dist", split.test_benign_in), ("held_out", split.test_benign_out)):
        for d, rows in dd.items():
            s = f(rows); r["benign"][d] = {"group": group, "n": int(len(s)),
                                           "fpr": float((s > thr).mean()), "scores": s.astype(np.float32).tolist()}
    for d in nb.ALL_DEVICES:
        for botnet, atk, path in nb.attack_files(d):
            s = f(nb._read(path, cols))
            r["attack"][f"{d}|{botnet}|{atk}"] = {
                "device": d, "group": "in_dist" if d in nb.IN_DIST else "held_out",
                "botnet": botnet, "attack": atk, "n": int(len(s)),
                "tpr": float((s > thr).mean()), "scores": s.astype(np.float32).tolist()}
    return r


if __name__ == "__main__":
    cols = nb.feature_order("/content/orig/feature_order.csv")
    split = nb.benign_split(cols)
    os.makedirs("/content/res_models", exist_ok=True)
    jobs = [(f"lstm_seed{s}", (lambda s=s: lstm_scorer(s))) for s in SEEDS]
    jobs += [(f"dense_seed{s}", (lambda s=s: train_dense(split, s))) for s in SEEDS]
    jobs += [(f"iforest_seed{s}", (lambda s=s: train_iforest(split, s))) for s in SEEDS]
    only = [x for x in os.environ.get("ONLY", "").split(",") if x]
    if only:                                   # e.g. ONLY=dense,iforest after a VM reclaim
        jobs = [(n, b) for n, b in jobs if n.split("_")[0] in only]
    for name, build in jobs:
        out = f"/content/res_models/{name}.json"
        if os.path.exists(out):
            print(f"{name}: exists, skip", flush=True); continue
        t0 = time.time(); f, thr = build()
        r = evaluate(name, f, thr, split, cols)
        json.dump(r, open(out, "w"))
        os.makedirs("/content/out", exist_ok=True)
        json.dump(r, open(f"/content/out/{name}.json", "w"))      # synced off-VM as it lands
        fpr_in = np.mean([v["fpr"] for v in r["benign"].values() if v["group"] == "in_dist"])
        fpr_out = np.mean([v["fpr"] for v in r["benign"].values() if v["group"] == "held_out"])
        tpr = np.mean([v["tpr"] for v in r["attack"].values()])
        print(f"{name:<16} thr={thr:.4g}  FPR_in={fpr_in:.4f}  FPR_heldout={fpr_out:.4f}  "
              f"TPR_mean={tpr:.4f}  ({time.time()-t0:.0f}s)", flush=True)
