"""
Time real nftables enforcement: HostFirewall.block() and .unblock().

NEEDS ROOT (nftables requires CAP_NET_ADMIN). Run:
    sudo ./venv/bin/python research/bench_enforce.py

Uses RFC 5737 documentation addresses (198.51.100.0/24), which carry no real
traffic, and removes every rule it adds. The first block also creates the
`inet sentinel` table; that one-time setup is timed separately.
"""
import json, os, sys, time
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__))); sys.path.insert(0, ROOT)
import numpy as np
from sentinel.core.firewall.host_firewall import HostFirewall

if os.geteuid() != 0:
    sys.exit("needs root:  sudo ./venv/bin/python research/bench_enforce.py")
fw = HostFirewall(); blk, unb = [], []
t0 = time.perf_counter(); first = fw.block("198.51.100.200"); setup = time.perf_counter() - t0
fw.unblock("198.51.100.200")
if not getattr(first, "enforced", False):
    sys.exit(f"block was not enforced: {getattr(first, 'note', first)}")
for i in range(30):
    ip = f"198.51.100.{201 + i}"
    t0 = time.perf_counter(); r = fw.block(ip); blk.append(time.perf_counter() - t0)
    assert r.enforced, r.note
for i in range(30):
    ip = f"198.51.100.{201 + i}"
    t0 = time.perf_counter(); fw.unblock(ip); unb.append(time.perf_counter() - t0)
leftover = [ip for ip in fw.blocked_ips() if ip.startswith("198.51.100.")]
s = lambda x: {"n": len(x), "median_ms": float(np.median(x) * 1e3), "p95_ms": float(np.percentile(x, 95) * 1e3)}
out = {"first_block_incl_setup_ms": setup * 1e3, "block": s(blk), "unblock": s(unb), "leftover_rules": leftover}
print(json.dumps(out, indent=1))
json.dump(out, open(os.path.join(ROOT, "research/results/enforce_latency.json"), "w"), indent=1)
