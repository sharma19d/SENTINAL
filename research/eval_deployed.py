"""
Score the DEPLOYED anomaly model (sentinel/models/sentinel_lstm.onnx) exactly as
SENTINEL runs it: MinMax-scale with the shipped scaler, run the ONNX graph on a
(10, 115) window, score = mean squared reconstruction error over the whole
window, alert if score > shipped threshold (0.004004517).

The deployed scaler was fit on ALL benign traffic of the six in-distribution
devices, so in-distribution benign windows are not a clean test for this model
(some or all of them informed its scaling and, possibly, its training). They are
reported but flagged `contaminated`. The held-out devices and all attack traffic
are clean for this model.
"""
import json, os, pickle, sys, time
import numpy as np
import onnxruntime as ort

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import nbaiot as nb

ORIG = os.environ.get("ORIG_DIR", "/content/orig")
cols = nb.feature_order(f"{ORIG}/feature_order.csv")
scaler = pickle.load(open(f"{ORIG}/sentinel_scaler.pkl", "rb"))
thr = float(open(f"{ORIG}/sentinel_threshold.txt").read().strip())
sess = ort.InferenceSession(f"{ORIG}/sentinel_lstm.onnx", providers=["CPUExecutionProvider"])
iname = sess.get_inputs()[0].name


def scores(rows: np.ndarray) -> np.ndarray:
    W = nb.windows(scaler.transform(rows).astype(np.float32), stride=nb.WINDOW)
    out = []
    for i in range(0, len(W), 4096):
        b = W[i:i + 4096]
        r = sess.run(None, {iname: b})[0]
        out.append(((b - r) ** 2).mean(axis=(1, 2)))
    return np.concatenate(out) if out else np.empty(0)


res = {"threshold": thr, "benign": {}, "attack": {}}
t0 = time.time()
split = nb.benign_split(cols)
for group, dd in (("in_dist", split.test_benign_in), ("held_out", split.test_benign_out)):
    for d, rows in dd.items():
        s = scores(rows)
        res["benign"][d] = {"group": group, "n": int(len(s)),
                            "fpr": float((s > thr).mean()),
                            "contaminated": group == "in_dist",
                            "scores": s.astype(np.float32).tolist()}
        print(f"benign  {group:<8} {d:<44} n={len(s):>6} FPR={(s>thr).mean():.4f}", flush=True)

for d in nb.ALL_DEVICES:
    for botnet, atk, path in nb.attack_files(d):
        s = scores(nb._read(path, cols))
        res["attack"][f"{d}|{botnet}|{atk}"] = {
            "device": d, "group": "in_dist" if d in nb.IN_DIST else "held_out",
            "botnet": botnet, "attack": atk, "n": int(len(s)),
            "tpr": float((s > thr).mean()), "scores": s.astype(np.float32).tolist()}
        print(f"attack  {d[:24]:<24} {botnet:<6} {atk:<10} n={len(s):>6} TPR={(s>thr).mean():.4f}", flush=True)

res["elapsed_s"] = time.time() - t0
json.dump(res, open("/content/res_deployed.json", "w"))
print(f"done in {res['elapsed_s']:.0f}s")
