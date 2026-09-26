"""Mirror /content/out on the Colab VM into research/results/colab, incrementally.

The VM can be reclaimed at any moment (it happened mid-run once, losing trained
models); this loop pulls every artefact home as soon as it appears, so a
reclaim costs at most the step in flight.
"""
import json, os, subprocess, sys, time
SESSION = sys.argv[1] if len(sys.argv) > 1 else "paper2"
DEST = os.path.join(os.path.dirname(os.path.abspath(__file__)), "results", "colab")
ENV = {**os.environ, "PATH": f"{os.environ['HOME']}/.local/bin:{os.environ['HOME']}/google-cloud-sdk/bin:{os.environ['PATH']}"}
LIST = ("import os,json\nout={}\nfor r,_,fs in os.walk('/content/out'):\n"
        "    for f in fs:\n        p=os.path.join(r,f); out[os.path.relpath(p,'/content/out')]=os.path.getsize(p)\n"
        "print('LISTING'+json.dumps(out))\n")

def remote():
    r = subprocess.run(["colab", "--auth=adc", "exec", "-s", SESSION, "--timeout", "60"],
                       input=LIST, capture_output=True, text=True, env=ENV, timeout=120)
    for line in r.stdout.splitlines():
        if line.startswith("LISTING"): return json.loads(line[7:])
    raise RuntimeError((r.stdout + r.stderr)[-300:])

while True:
    try:
        files = remote()
    except Exception as e:
        print(time.strftime("%H:%M:%S"), "listing failed:", e, flush=True); time.sleep(60); continue
    for rel, size in sorted(files.items()):
        loc = os.path.join(DEST, rel)
        if os.path.exists(loc) and os.path.getsize(loc) == size: continue
        os.makedirs(os.path.dirname(loc), exist_ok=True)
        subprocess.run(["colab", "--auth=adc", "download", "-s", SESSION, f"/content/out/{rel}", loc],
                       capture_output=True, env=ENV, timeout=600)
        print(time.strftime("%H:%M:%S"), "synced", rel, size, flush=True)
    need = [m for m in os.environ.get("DONE_MARKERS", "ALL.done").split(",") if m]
    if all(m in files for m in need) and all(os.path.exists(os.path.join(DEST, f)) for f in files):
        print("all artefacts synced"); break
    time.sleep(90)
