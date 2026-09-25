"""
N-BaIoT loading, splitting and windowing for the SENTINEL evaluation.

Dataset: Meidan et al., "N-BaIoT: Network-based Detection of IoT Botnet Attacks
Using Deep Autoencoders", IEEE Pervasive Computing 17(3), 2018. Features are the
115 Kitsune AfterImage statistics (Mirsky et al., NDSS 2018) — the same feature
set SENTINEL's deployed anomaly model consumes (sentinel/models/feature_order.csv).

PROTOCOL — fixed before any model was scored, and not tuned afterwards:

  * IN-DISTRIBUTION devices are the six whose benign traffic the deployed model's
    scaler was fit on. This was established empirically, not assumed: the saved
    MinMaxScaler's 115 minima and 115 maxima match the benign traffic of exactly
    these six devices with zero deviation, and its n_samples_seen (322,064) equals
    their combined benign row count.
  * HELD-OUT devices are the remaining three. Neither the deployed model nor any
    model trained here sees a single row from them, so they measure
    generalisation to IoT devices the detector has never observed — the realistic
    case for a home appliance, where new devices join the network.
  * Benign traffic of in-distribution devices is split TEMPORALLY per device.
    As in Meidan et al., the chronologically final third is the test set. They
    divided the first two-thirds into equal training and optimisation thirds;
    we use 90% of it for training and hold out the last 10% for early stopping
    and for choosing the detection threshold. Temporal, not random, because
    adjacent rows share damped-window statistics, so a random split would leak
    near-duplicate rows between training and test.
  * All attack traffic (Mirai and BASHLITE/Gafgyt, 10 attack types) is test-only.
    An autoencoder anomaly detector never trains on attacks.
  * Windows are 10 consecutive rows from ONE file (never spanning a file or
    device boundary), matching the deployed model's (10, 115) input. Test
    windows are non-overlapping (stride 10) so they are closer to independent
    samples; training windows use stride 1.
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field

import numpy as np
import pandas as pd

ROOT = os.environ.get("NBAIOT_ROOT", "/content/nbaiot")
WINDOW = 10

IN_DIST = [
    "Danmini_Doorbell",
    "Ecobee_Thermostat",
    "Provision_PT_737E_Security_Camera",
    "Provision_PT_838_Security_Camera",
    "Samsung_SNH_1011_N_Webcam",
    "SimpleHome_XCS7_1002_WHT_Security_Camera",
]
HELD_OUT = [
    "Ennio_Doorbell",
    "Philips_B120N10_Baby_Monitor",
    "SimpleHome_XCS7_1003_WHT_Security_Camera",
]
ALL_DEVICES = IN_DIST + HELD_OUT

TRAIN_FRAC = 2 / 3
VAL_FRAC_OF_TRAIN = 0.10


def feature_order(path: str) -> list[str]:
    """The 115 feature names, in the exact order the deployed model expects."""
    return pd.read_csv(path)["value"].tolist()


def _read(path: str, cols: list[str]) -> np.ndarray:
    return pd.read_csv(path, usecols=cols)[cols].to_numpy(np.float32)


def attack_files(device: str) -> list[tuple[str, str, str]]:
    """(botnet, attack, path) for every attack CSV of a device.

    Two devices (Ennio, Samsung) have no Mirai captures in N-BaIoT; that is a
    property of the dataset, not a filtering choice.
    """
    out = []
    for botnet in ("mirai", "gafgyt"):
        d = os.path.join(ROOT, device, f"{botnet}_attacks")
        if not os.path.isdir(d):
            continue
        for f in sorted(os.listdir(d)):
            if f.endswith(".csv"):
                out.append((botnet, f[:-4], os.path.join(d, f)))
    return out


def windows(X: np.ndarray, stride: int) -> np.ndarray:
    """[N, F] -> [M, WINDOW, F] of consecutive rows. Never pads across a boundary."""
    if len(X) < WINDOW:
        return np.empty((0, WINDOW, X.shape[1]), np.float32)
    v = np.lib.stride_tricks.sliding_window_view(X, WINDOW, axis=0)  # [N-W+1, F, W]
    return np.ascontiguousarray(v[::stride].transpose(0, 2, 1))


@dataclass
class Split:
    train: list[np.ndarray] = field(default_factory=list)   # raw rows, per device
    val: list[np.ndarray] = field(default_factory=list)
    test_benign_in: dict = field(default_factory=dict)      # device -> rows
    test_benign_out: dict = field(default_factory=dict)     # held-out device -> rows


def benign_split(cols: list[str]) -> Split:
    s = Split()
    for d in IN_DIST:
        X = _read(os.path.join(ROOT, d, "benign_traffic.csv"), cols)
        n_tr = int(len(X) * TRAIN_FRAC)
        n_va = int(n_tr * VAL_FRAC_OF_TRAIN)
        s.train.append(X[: n_tr - n_va])
        s.val.append(X[n_tr - n_va : n_tr])
        s.test_benign_in[d] = X[n_tr:]
    for d in HELD_OUT:
        s.test_benign_out[d] = _read(os.path.join(ROOT, d, "benign_traffic.csv"), cols)
    return s
