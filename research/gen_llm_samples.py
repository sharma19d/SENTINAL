"""
Draw the 200 evaluation windows for the pre-registered LLM experiment
(research/PREREGISTRATION.md): 20 per attack class x 10 classes, seed 0,
uniformly over every device that has that class (in-distribution and held-out).

For each window it records the anomaly score from the reproducible LSTM
autoencoder (seed 0) and the five pre-registered "evidence" statistics, taken
from the LAST row of the window. No label-bearing field (protocol, attack name)
is ever written into anything the LLM will see.
"""
import json, os, pickle, sys
import numpy as np
import torch

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import nbaiot as nb
from train_anomaly import LSTMAutoencoder

CATEGORY = {"scan": "DISCOVERY"}          # every other class is a flood -> DOS
PER_CLASS, SEED, RUN = 20, 0, "/content/runs/seed0"


def evidence(raw_last_row, cols):
    """The five pre-registered statistics, from UNscaled Kitsune features."""
    v = dict(zip(cols, raw_last_row.tolist()))
    h, hh, hphp = v["H_L0.1_weight"], v["HH_L0.1_weight"], v["HpHp_L0.1_weight"]
    return {
        "recent_packet_count": round(v["MI_dir_L0.1_weight"], 2),
        "mean_packet_size_bytes": round(v["MI_dir_L0.1_mean"], 1),
        "approx_active_destination_hosts": round(h / hh, 2) if hh > 0 else None,
        "approx_active_sockets": round(h / hphp, 2) if hphp > 0 else None,
        "channel_jitter_mean_s": float(f"{v['HH_jit_L0.1_mean']:.4g}"),
    }


if __name__ == "__main__":
    rng = np.random.default_rng(SEED)
    cols = nb.feature_order("/content/orig/feature_order.csv")
    dev = "cuda" if torch.cuda.is_available() else "cpu"
    m = LSTMAutoencoder().to(dev)
    m.load_state_dict(torch.load(f"{RUN}/model.pt", map_location=dev)); m.eval()
    sc = pickle.load(open(f"{RUN}/scaler.pkl", "rb"))
    thr = json.load(open(f"{RUN}/meta.json"))["threshold"]

    by_class = {}
    for d in nb.ALL_DEVICES:
        for botnet, atk, path in nb.attack_files(d):
            by_class.setdefault((botnet, atk), []).append((d, path))

    samples = []
    for (botnet, atk), sources in sorted(by_class.items()):
        # Uniform over devices first, then over windows within the device, so
        # no single device dominates a class.
        picks = rng.integers(0, len(sources), size=PER_CLASS)
        cache = {}
        for k, pi in enumerate(picks):
            d, path = sources[pi]
            if path not in cache:
                cache[path] = nb._read(path, cols)
            raw = cache[path]
            W = nb.windows(raw, nb.WINDOW)                            # stride 10
            wi = int(rng.integers(0, len(W)))
            win_raw = W[wi]
            x = torch.from_numpy(sc.transform(win_raw).astype(np.float32)).unsqueeze(0).to(dev)
            with torch.no_grad():
                score = float(((x - m(x)) ** 2).mean().item())
            samples.append({
                "id": f"{botnet}-{atk}-{k:02d}", "botnet": botnet, "attack": atk,
                "category": CATEGORY.get(atk, "DOS"), "device": d,
                "group": "in_dist" if d in nb.IN_DIST else "held_out",
                "anomaly_score": round(score, 6),
                "alert_level": "critical" if score > thr * 2 else "warning",
                "flagged": bool(score > thr),
                "evidence": evidence(win_raw[-1], cols),
            })
        print(f"{botnet}/{atk}: {PER_CLASS} samples from {len(sources)} devices", flush=True)

    json.dump({"seed": SEED, "lstm_threshold": thr, "samples": samples},
              open("/content/llm_samples.json", "w"), indent=2)
    print(f"wrote {len(samples)} samples")
