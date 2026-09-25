"""
Per-stage latency of SENTINEL's detection-to-response path, measured in-process
on this machine with the real components (not mocks).

Stages timed here (no root needed):
  1. feature extraction   KitsuneExtractor.extract, per packet (real packets:
                          Kitsune's Mirai capture)
  2. anomaly inference    AnomalyDetector.predict on a (10,115) window — the
                          deployed ONNX model, exactly as the worker calls it
  3. intel enrichment     IntelBus.enrich_ip (AlienVault OTX + AbuseIPDB) on
                          RFC 5737 documentation addresses — real network calls
  4. response policy      ResponseGraph.run (LangGraph policy + security gate)
  5. bus hop              Redis publish -> subscriber receive, one message
Not timed here:
  * LLM classification — measured over the 400 calls of the pre-registered
    classification experiment (run_llm_experiment.py), on realistic prompts.
  * nftables enforcement — needs root; see bench_enforce.py.

Usage: ./venv/bin/python research/bench_latency.py PATH/mirai.pcap
"""
import asyncio, json, os, statistics, sys, threading, time, uuid
import numpy as np

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT); sys.path.insert(0, os.path.join(ROOT, "research"))


def summ(xs):
    xs = np.asarray(xs) * 1000.0
    return {"n": int(len(xs)), "median_ms": float(np.median(xs)), "mean_ms": float(xs.mean()),
            "std_ms": float(xs.std(ddof=1)) if len(xs) > 1 else 0.0,
            "p95_ms": float(np.percentile(xs, 95)), "p99_ms": float(np.percentile(xs, 99))}


def show(name, s):
    print(f"  {name:<22} n={s['n']:>6}  median {s['median_ms']:9.3f} ms  p95 {s['p95_ms']:9.3f} ms"
          f"  mean {s['mean_ms']:9.3f} ± {s['std_ms']:.3f}", flush=True)


def bench_extract(pcap, n=50000):
    from test_kitsune_parity import packets
    from sentinel.agents.anomaly.kitsune import KitsuneExtractor
    P = list(packets(pcap, n)); ex = KitsuneExtractor(); ts = []
    for k in P:
        t0 = time.perf_counter(); ex.extract(*k); ts.append(time.perf_counter() - t0)
    return summ(ts), P


def bench_infer(P, n=3000):
    from sentinel.agents.anomaly.inference import AnomalyDetector
    from sentinel.agents.anomaly.kitsune import KitsuneExtractor
    det = AnomalyDetector(); ex = KitsuneExtractor()
    F = np.array([ex.extract(*k) for k in P[: n + 10]], dtype=np.float32)
    for i in range(20): det.predict(F[i:i + 10])                       # warm-up
    ts = []
    for i in range(n):
        t0 = time.perf_counter(); det.predict(F[i:i + 10]); ts.append(time.perf_counter() - t0)
    return summ(ts)


async def bench_intel(n=10):
    from intel.bus import IntelBus
    bus = IntelBus(); ts = []
    for i in range(n):
        t0 = time.perf_counter(); await bus.enrich_ip(f"198.51.100.{100 + i}"); ts.append(time.perf_counter() - t0)
    return summ(ts)


async def bench_policy(n=500):
    from sentinel.agents.responder.graph import ResponseGraph
    g = ResponseGraph(); ts = []
    for i in range(n):
        ev = {"event_id": str(uuid.uuid4()), "device_id": "bench", "severity": (i % 10) + 1,
              "tactic": "Impact", "summary": "bench", "indicators": ["198.51.100.7"]}
        t0 = time.perf_counter(); await g.run(ev); ts.append(time.perf_counter() - t0)
    return summ(ts)


def bench_bus(n=1000):
    import redis
    r = redis.Redis(); ch = f"sentinel:bench:{uuid.uuid4().hex[:8]}"
    ps = r.pubsub(); ps.subscribe(ch)
    while ps.get_message(timeout=1.0) is None: pass                      # consume subscribe ack
    ts = []
    for i in range(n):
        t0 = time.perf_counter(); r.publish(ch, json.dumps({"i": i, "pad": "x" * 512}))
        while ps.get_message(timeout=5.0) is None: pass
        ts.append(time.perf_counter() - t0)
    ps.close(); return summ(ts)


if __name__ == "__main__":
    pcap = sys.argv[1]; out = {}
    print("stage latency on this host", flush=True)
    out["1_feature_extraction_per_packet"], P = bench_extract(pcap); show("1 feature extraction", out["1_feature_extraction_per_packet"])
    out["2_anomaly_inference_per_window"] = bench_infer(P);          show("2 anomaly inference", out["2_anomaly_inference_per_window"])
    out["5_redis_bus_hop"] = bench_bus();                            show("5 redis bus hop", out["5_redis_bus_hop"])
    out["4_response_policy"] = asyncio.run(bench_policy());          show("4 response policy", out["4_response_policy"])
    try:
        out["3_intel_enrichment"] = asyncio.run(bench_intel());      show("3 intel enrichment", out["3_intel_enrichment"])
    except Exception as e:
        out["3_intel_enrichment"] = {"error": str(e)}; print("  3 intel enrichment    ERROR", e)
    import platform
    out["host"] = {"machine": platform.machine(), "cpus": os.cpu_count(), "python": platform.python_version()}
    json.dump(out, open(os.path.join(ROOT, "research/results/latency_stages.json"), "w"), indent=2)
    print("wrote research/results/latency_stages.json")
