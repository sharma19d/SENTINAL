"""
Does SENTINEL's live Kitsune extractor produce N-BaIoT-like features?

Runs the NEW extractor (sentinel/agents/anomaly/kitsune.py, reference engine)
and the OLD hand-written one (research/results/kitsune_OLD_for_comparison.py)
over the same real packets — the Mirai capture shipped with Kitsune-py
(Mirsky et al., NDSS 2018) — and checks two things:

 1. STRUCTURAL: the invariants measured directly on N-BaIoT's rows must hold.
      MI_dir == H (one IP per MAC), HH weight <= H weight (channel is a
      sub-stream of the host), radius >= std^2, magnitude >= |mean|, and pcc
      must be a continuous correlation, not only {0, 1}.
 2. DISTRIBUTIONAL: after the deployed scaler, what fraction of values lands
      inside N-BaIoT's training range [0, 1]? The capture is from a different
      network than N-BaIoT, so neither extractor need be fully in range — the
      comparison is between extractors on identical packets.

Usage:  ./venv/bin/python research/test_kitsune_parity.py PATH/mirai.pcap [N]
"""
import importlib.util, os, pickle, sys
import numpy as np
import pandas as pd

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
from sentinel.agents.anomaly.kitsune import KitsuneExtractor as New

spec = importlib.util.spec_from_file_location(
    "old_kitsune", os.path.join(ROOT, "research/results/kitsune_OLD_for_comparison.py"))
old_mod = importlib.util.module_from_spec(spec); spec.loader.exec_module(old_mod)
Old = old_mod.KitsuneExtractor

cols = pd.read_csv(os.path.join(ROOT, "sentinel/models/feature_order.csv"))["value"].tolist()
scaler = pickle.load(open(os.path.join(ROOT, "sentinel/models/sentinel_scaler.pkl"), "rb"))


def packets(path, n):
    from scapy.all import PcapReader, Ether, IP, TCP, UDP
    with PcapReader(path) as r:
        for i, p in enumerate(r):
            if i >= n: break
            if not p.haslayer(IP): continue
            ip = p[IP]; l4 = p[TCP] if p.haslayer(TCP) else (p[UDP] if p.haslayer(UDP) else None)
            yield (ip.src, p[Ether].src if p.haslayer(Ether) else "", l4.sport if l4 else 0,
                   ip.dst, p[Ether].dst if p.haslayer(Ether) else "", l4.dport if l4 else 0,
                   len(p), float(p.time))


def run(cls, pkts):
    ex = cls(); return pd.DataFrame(np.array([ex.extract(*k) for k in pkts]), columns=cols)


def check(name, F):
    L = "L0.1"
    tests = {
        "MI_dir == H":        np.isclose(F[f"MI_dir_{L}_mean"], F[f"H_{L}_mean"]).mean(),
        "HH_weight <= H_wt":  (F[f"HH_{L}_weight"] <= F[f"H_{L}_weight"] + 1e-6).mean(),
        "radius >= std^2":    (F[f"HH_{L}_radius"] >= F[f"HH_{L}_std"] ** 2 * (1 - 1e-5) - 1e-6).mean(),
        "magnitude >= |mean|": (F[f"HH_{L}_magnitude"] >= F[f"HH_{L}_mean"].abs() - 1e-6).mean(),
        "|pcc| <= 1 (all)":   (F[[c for c in cols if c.endswith("_pcc")]].abs() <= 1 + 1e-6).to_numpy().mean(),
    }
    pcc = F[[c for c in cols if c.endswith("_pcc")]].to_numpy().ravel()
    S = scaler.transform(F[cols].to_numpy())
    inr = ((S >= -1e-6) & (S <= 1 + 1e-6)).mean()
    print(f"\n{name}")
    for k, v in tests.items(): print(f"  {k:<20} {v*100:6.1f}% of packets")
    print(f"  pcc distinct values  {len(np.unique(np.round(pcc, 6))):>6}   range [{pcc.min():.3f}, {pcc.max():.3f}]")
    print(f"  scaled values in N-BaIoT training range [0,1]: {inr*100:.1f}%")
    return tests, inr


if __name__ == "__main__":
    path = sys.argv[1]; n = int(sys.argv[2]) if len(sys.argv) > 2 else 60000
    P = list(packets(path, n)); print(f"{len(P):,} IP packets from {os.path.basename(path)}")
    Fn, Fo = run(New, P), run(Old, P)
    new_t, new_in = check("NEW extractor (reference engine)", Fn)
    old_t, old_in = check("OLD extractor (hand-written)", Fo)
    import json
    pcc_n = lambda F: int(len(np.unique(np.round(F[[c for c in cols if c.endswith('_pcc')]].to_numpy().ravel(), 6))))
    json.dump({"packets": len(P),
               "new": {**{k: float(v) for k, v in new_t.items()}, "pcc_distinct": pcc_n(Fn), "in_range": float(new_in)},
               "old": {**{k: float(v) for k, v in old_t.items()}, "pcc_distinct": pcc_n(Fo), "in_range": float(old_in)}},
              open(os.path.join(ROOT, "research/results/parity.json"), "w"), indent=1)
    ok = all(v > 0.99 for v in new_t.values())
    print(f"\nSTRUCTURAL PARITY {'PASS' if ok else 'FAIL'} (new extractor: all invariants > 99%)")
    sys.exit(0 if ok else 1)
