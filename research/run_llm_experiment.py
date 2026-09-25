"""
Run the pre-registered LLM ATT&CK experiment (research/PREREGISTRATION.md)
against the local Ollama model, on this machine.

The AS-BUILT prompt is produced by SENTINEL's own GemmaClassifier._build_prompt
and system_prompt — imported, not copied — so what is measured is exactly what
the deployed classifier sends. The Ollama payload mirrors GemmaClassifier.classify
(model, prompt, system, stream=False, format="json", default sampling).

Usage: ../venv/bin/python run_llm_experiment.py results/llm_samples.json
"""
import json, os, random, re, sys, time
import urllib.request

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from sentinel.agents.classifier.gemma_client import GemmaClassifier

SCHEMA = {"tactic", "technique_id", "confidence", "severity", "summary", "recommended_action"}
ACCEPT_TECH = {
    "DISCOVERY": {"T1046", "T1595", "T1018", "T0846", "T0840", "T0888"},
    "DOS": {"T1498", "T1499", "T0814"},
}
ACCEPT_TACTIC = {"DISCOVERY": ("discovery", "reconnaissance"),
                 "DOS": ("impact", "inhibit response function")}
TECH_RE = re.compile(r"T\d{4}(?:\.\d{3})?")
HOST = os.environ.get("LLM_HOST", "local")        # see PREREGISTRATION.md Deviations


def context(s):
    """What the classifier worker would assemble — minus the label-bearing fields."""
    n = int(s["id"].rsplit("-", 1)[1])
    return {
        "device_id": f"nbaiot:{s['device']}",
        "vendor": s["device"],
        "src_ip": f"192.0.2.{10 + n}",          # RFC 5737 TEST-NET-1
        "dst_ip": f"198.51.100.{10 + n}",       # RFC 5737 TEST-NET-2
        "protocol": "unknown",                  # pre-registered: avoid label leakage
        "anomaly_score": s["anomaly_score"],
        "alert_level": s["alert_level"],
        "cves": "None",
        "intel": {},                            # -> "Global Reputation: Not checked"
    }


def evidence_block(e):
    f = lambda v: "n/a" if v is None else v
    return ("\nTRAFFIC EVIDENCE (damped-window statistics of the most recent packet):\n"
            f"- Recent packet count from this host: {f(e['recent_packet_count'])}\n"
            f"- Mean packet size: {f(e['mean_packet_size_bytes'])} bytes\n"
            f"- Approx. active destination hosts: {f(e['approx_active_destination_hosts'])}\n"
            f"- Approx. active sockets (host:port pairs): {f(e['approx_active_sockets'])}\n"
            f"- Channel jitter (mean inter-packet time): {f(e['channel_jitter_mean_s'])} s\n")


def build(gc, s, variant):
    p = gc._build_prompt(context(s))
    if variant == "EVIDENCE":
        i = p.index("\nTASK:")
        p = p[:i] + evidence_block(s["evidence"]) + p[i:]
    return p


def call(gc, prompt):
    body = json.dumps({"model": gc.model, "prompt": prompt, "system": gc.system_prompt,
                       "stream": False, "format": "json"}).encode()
    req = urllib.request.Request(gc.base_url, data=body, headers={"Content-Type": "application/json"})
    t0 = time.perf_counter()
    out = json.load(urllib.request.urlopen(req, timeout=300))
    return out.get("response", ""), time.perf_counter() - t0, out


def grade(raw, category):
    try:
        j = json.loads(raw)
        valid = isinstance(j, dict) and SCHEMA.issubset(j.keys())
    except Exception:
        j, valid = None, False
    tech = tactic = None
    tech_ok = tactic_ok = False
    if valid:
        m = TECH_RE.findall(str(j.get("technique_id", "")))
        tech = m[0] if m else None                 # first ID = primary (see PREREGISTRATION)
        tech_ok = bool(tech) and tech.split(".")[0] in ACCEPT_TECH[category]
        tactic = str(j.get("tactic", ""))
        tactic_ok = any(a in tactic.lower() for a in ACCEPT_TACTIC[category])
    return {"valid_json": valid, "technique": tech, "technique_ok": tech_ok,
            "tactic": tactic, "tactic_ok": tactic_ok, "parsed": j}


if __name__ == "__main__":
    src = sys.argv[1]
    out_path = sys.argv[2] if len(sys.argv) > 2 else "results/llm_results.json"
    samples = json.load(open(src))["samples"]
    gc = GemmaClassifier(base_url=os.environ.get("OLLAMA_URL"))

    done = {}
    if os.path.exists(out_path):                                 # resumable
        for r in json.load(open(out_path))["results"]:
            done[(r["id"], r["variant"])] = r

    jobs = [(s, v) for s in samples for v in ("AS_BUILT", "EVIDENCE")]
    random.Random(0).shuffle(jobs)                                # interleave variants

    _, warm, _ = call(gc, "Reply with {}")                        # load weights; not scored
    print(f"warm-up (model load) {warm:.1f}s  model={gc.model}", flush=True)

    results = list(done.values())
    for i, (s, v) in enumerate(jobs):
        if (s["id"], v) in done:
            continue
        raw, dt, meta = call(gc, build(gc, s, v))
        g = grade(raw, s["category"])
        results.append({"id": s["id"], "variant": v, "host": HOST, "botnet": s["botnet"], "attack": s["attack"],
                        "category": s["category"], "device": s["device"], "group": s["group"],
                        "latency_s": dt, "eval_count": meta.get("eval_count"),
                        "prompt_eval_count": meta.get("prompt_eval_count"),
                        "raw": raw, **{k: g[k] for k in ("valid_json", "technique", "technique_ok",
                                                          "tactic", "tactic_ok")}})
        print(f"[{i+1:3d}/{len(jobs)}] {v:<8} {s['id']:<18} {dt:5.1f}s  json={g['valid_json']} "
              f"tech={g['technique']} ok={g['technique_ok']} tactic_ok={g['tactic_ok']}", flush=True)
        if (i + 1) % 10 == 0:
            json.dump({"model": gc.model, "results": results}, open(out_path, "w"), indent=1)
    json.dump({"model": gc.model, "results": results}, open(out_path, "w"), indent=1)
    print("done")
