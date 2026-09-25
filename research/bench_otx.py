"""OTX latency: the call SENTINEL makes (all sections) vs the one it needs.

IntelBus reads only reputation['general']['pulse_info'], but fetches every
section via get_indicator_details_full. Time both on documentation addresses.
Each call runs in a thread with a hard cap, since the SDK call has no timeout.
"""
import concurrent.futures as cf, json, os, sys, time
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__))); sys.path.insert(0, ROOT)
from intel.bus import IntelBus
from OTXv2 import IndicatorTypes
otx = IntelBus().otx; CAP = 300.0; ex = cf.ThreadPoolExecutor(4); res = {"full": [], "general": []}
def timed(fn, *a):
    t0 = time.perf_counter(); f = ex.submit(fn, *a)
    try: f.result(timeout=CAP); return time.perf_counter() - t0
    except cf.TimeoutError: return None
for i in range(10):
    ip = f"198.51.100.{140 + i}"
    res["general"].append(timed(otx.get_indicator_details_by_section, IndicatorTypes.IPv4, ip, "general"))
    print("general", ip, res["general"][-1], flush=True)
for i in range(4):
    ip = f"198.51.100.{160 + i}"
    res["full"].append(timed(otx.get_indicator_details_full, IndicatorTypes.IPv4, ip))
    print("full", ip, res["full"][-1], flush=True)
    json.dump(res, open(os.path.join(ROOT, "research/results/otx_latency.json"), "w"), indent=1)
print("done", flush=True); os._exit(0)
