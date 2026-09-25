"""Time ONE IntelBus.enrich_ip call, split into its OTX and AbuseIPDB parts.

The OTX SDK call used by IntelBus is synchronous and has no timeout, so it is
timed on its own, in a worker thread with a hard wall-clock cap, rather than
inside the event loop where a stall would block everything else.
"""
import asyncio, concurrent.futures as cf, json, os, sys, time
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__))); sys.path.insert(0, ROOT)
from intel.bus import IntelBus
from OTXv2 import IndicatorTypes
CAP = float(sys.argv[1]) if len(sys.argv) > 1 else 180.0
bus, ip, res = IntelBus(), "198.51.100.123", {}
ex = cf.ThreadPoolExecutor(1)
t0 = time.perf_counter()
fut = ex.submit(bus.otx.get_indicator_details_full, IndicatorTypes.IPv4, ip) if bus.otx else None
try:
    if fut: fut.result(timeout=CAP)
    res["otx_s"] = time.perf_counter() - t0; res["otx_status"] = "ok" if fut else "no OTX key"
except cf.TimeoutError:
    res["otx_s"] = CAP; res["otx_status"] = f"NO RESPONSE within {CAP:.0f}s (the call has no timeout)"
except Exception as e:
    res["otx_s"] = time.perf_counter() - t0; res["otx_status"] = f"error: {e}"
bus.otx = None                                   # now time AbuseIPDB alone
t0 = time.perf_counter(); asyncio.run(bus.enrich_ip(ip)); res["abuseipdb_s"] = time.perf_counter() - t0
print(json.dumps(res, indent=1), flush=True)
json.dump(res, open(os.path.join(ROOT, "research/results/intel_probe.json"), "w"), indent=1)
os._exit(0)                                      # never wait on a possibly-hung OTX thread
