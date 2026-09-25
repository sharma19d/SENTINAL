"""
SENTINEL Layer 3 — Kitsune feature extraction (115 features, N-BaIoT layout).

Produces the exact 115-feature vector the anomaly model was trained on. The
model is trained on N-BaIoT (Meidan et al., IEEE Pervasive Computing 2018),
whose features come from Kitsune's extractor (Mirsky et al., NDSS 2018), so
this module must reproduce THAT feature definition — any deviation hands the
model inputs from a different distribution than it was trained on.

The statistics engine is the reference Kitsune code, vendored unmodified in
afterimage.py. The stream layout below is pinned to what the N-BaIoT data
itself shows, established empirically on the dataset rather than assumed
(research/ in the repository reproduces each check):

  group   key (stream)                  per-lambda stats (in this order)
  ------  ----------------------------  ------------------------------------
  MI_dir  src MAC + src IP              weight, mean, variance
  H       src IP                        weight, mean, variance
  HH      channel  srcIP -> dstIP       weight, mean, std, magnitude, radius,
          (2D partner: dstIP -> srcIP)  covariance, pcc
  HH_jit  channel  srcIP -> dstIP       weight, mean, variance  (of inter-
                                        arrival times)
  HpHp    socket  src:port -> dst:port  weight, mean, std, magnitude, radius,
          (2D partner: reverse socket)  covariance, pcc
  lambdas 5, 3, 1, 0.1, 0.01

Evidence for the non-obvious choices, from N-BaIoT's own rows:
  * MI_dir == H on 100% of rows  -> both single-updated, one IP per MAC.
  * HH weight < H weight         -> HH is keyed by the CHANNEL, not by the
                                    source host (the public Kitsune-py keys it
                                    by source IP; N-BaIoT's generator did not).
  * radius >= std^2 on ~100% of rows -> 2D groups report a true std (not the
                                    variance the reference's 1D getter returns)
                                    and radius = sqrt(var_a^2 + var_b^2).
  * the column labelled radius satisfies the radius bound and the column
    labelled magnitude satisfies magnitude >= |mean| -> the data is ordered
    magnitude, radius (the public reference returns radius first).

The previous hand-written extractor (preserved for comparison in
research/results/kitsune_OLD_for_comparison.py) fed one stream to both sides
of every 2D statistic, so covariance equalled variance and pcc was only ever
0 or 1 — 40 of the 115 features were degenerate — and it keyed MI by IP and H
by MAC, the reverse of the definition.
"""

from __future__ import annotations

import math

import numpy as np

from sentinel.agents.anomaly import afterimage as af

LAMBDAS = (5, 3, 1, 0.1, 0.01)

# Streams whose decayed weight has fallen below this are dead: at lambda=0.01
# an idle stream reaches it after ~1000 s. Evicting them bounds memory on an
# always-on appliance; the reference's own cleanOutOldRecords() is broken (it
# indexes [0] into an incStat), so eviction is done here.
_DEAD_WEIGHT = 1e-3
_EVICT_EVERY = 20_000          # packets between eviction sweeps
_MIN_STD = 1e-3               # bytes; below this a stream is constant-size (see _two_d)


class _Table:
    """An incStatDB plus eviction that also unlinks covariance partners."""

    def __init__(self):
        self.db = af.incStatDB()

    def evict(self, now: float) -> int:
        dead = []
        for key, s in self.db.HT.items():
            dt = now - s.lastTimestamp
            w = s.w * (math.pow(2, -s.Lambda * dt) if dt > 0 else 1.0)
            if w < _DEAD_WEIGHT:
                dead.append(key)
        for key in dead:
            s = self.db.HT.pop(key)
            for cov in s.covs:                       # break links both ways
                other = cov.incStats[1] if cov.incStats[0] is s else cov.incStats[0]
                if cov in other.covs:
                    other.covs.remove(cov)
            s.covs.clear()
        return len(dead)


class KitsuneExtractor:
    """Per-packet incremental extractor. Call extract() once per packet, in
    timestamp order; returns the 115-feature vector for that packet."""

    N_FEATURES = 115

    def __init__(self, lambdas=LAMBDAS):
        self.lambdas = tuple(lambdas)
        self.MI, self.H, self.HH = _Table(), _Table(), _Table()
        self.JIT, self.HpHp = _Table(), _Table()
        self._n = 0

    def _one_d(self, table, key, t, v, lam, diff=False):
        return table.db.update_get_1D_Stats(key, t, v, lam, isTypeDiff=diff)   # w, mean, var

    def _two_d(self, table, k1, k2, t, v, lam):
        w, mean, var, radius, magnitude, cov, _ = table.db.update_get_1D2D_Stats(k1, k2, t, v, lam)
        # pcc is recomputed with a numerical guard. The reference returns
        # cov/(std_a*std_b) whenever that product is not EXACTLY zero; for a
        # stream of constant-size packets the true variance is 0, but the
        # reference's |CF2/w - mean^2| leaves ~1e-10 of cancellation noise, so
        # the ratio can explode (values of +-6e5 were observed on real traffic,
        # for a statistic bounded by +-1). A correlation is undefined for a
        # zero-variance stream; 0 is the reference's own convention when the
        # product is exactly zero, so any std below a thousandth of a byte is
        # treated as zero, and the rest is bounded to [-1, 1] (Cauchy-Schwarz).
        # This matches N-BaIoT, whose pcc lies within [-0.68, 0.82].
        link = table.db.register_cov(k1, k2, lam, t)          # existing link; no update
        sa, sb = link.incStats[0].std(), link.incStats[1].std()
        pcc = 0.0 if min(sa, sb) < _MIN_STD else max(-1.0, min(1.0, cov / (sa * sb)))
        return [w, mean, math.sqrt(var), magnitude, radius, cov, pcc]           # N-BaIoT order

    def extract(self,
                src_ip: str, src_mac: str, src_port: int,
                dst_ip: str, dst_mac: str, dst_port: int,
                pkt_len: int, timestamp: float) -> np.ndarray:
        t, v = float(timestamp), float(pkt_len)
        chan, rchan = f"{src_ip}>{dst_ip}", f"{dst_ip}>{src_ip}"
        sock, rsock = f"{src_ip}:{src_port}>{dst_ip}:{dst_port}", f"{dst_ip}:{dst_port}>{src_ip}:{src_port}"

        f = []
        for lam in self.lambdas:
            f += self._one_d(self.MI, f"{src_mac}{src_ip}", t, v, lam)
        for lam in self.lambdas:
            f += self._one_d(self.H, src_ip, t, v, lam)
        for lam in self.lambdas:
            f += self._two_d(self.HH, chan, rchan, t, v, lam)
        for lam in self.lambdas:
            f += self._one_d(self.JIT, chan, t, 0.0, lam, diff=True)
        for lam in self.lambdas:
            f += self._two_d(self.HpHp, sock, rsock, t, v, lam)

        self._n += 1
        if self._n % _EVICT_EVERY == 0:
            for tbl in (self.MI, self.H, self.HH, self.JIT, self.HpHp):
                tbl.evict(t)

        out = np.asarray(f, dtype=np.float32)
        # pcc is 0/0 until a stream has variance; the reference returns nan in
        # some such paths. The model has never seen nan, so map it to 0.
        return np.nan_to_num(out, nan=0.0, posinf=0.0, neginf=0.0)
