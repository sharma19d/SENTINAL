#!/bin/bash
# Full N-BaIoT evaluation pipeline on a fresh Colab VM. Ordered so the most
# valuable artefacts exist earliest; each step leaves a .done marker so a rerun
# resumes. Artefacts land in /content/out, which is synced to the local repo as
# they appear (the VM can be reclaimed at any time).
set -u
cd /content/research
mkdir -p /content/out /content/runs
log() { echo "[$(date +%H:%M:%S)] $*" | tee -a /content/out/pipeline.log; }

if [ ! -f /content/data.done ]; then
  log "downloading N-BaIoT (UCI)"
  mkdir -p /content/nbaiot && cd /content/nbaiot
  wget -q -O nbaiot.zip "https://archive.ics.uci.edu/static/public/442/detection+of+iot+botnet+attacks+n+baiot.zip" && unzip -o -q nbaiot.zip && rm -f nbaiot.zip
  (which unrar >/dev/null || apt-get install -y -qq unrar >/dev/null 2>&1)
  for d in */; do (cd "$d" && for r in *.rar; do [ -f "$r" ] && mkdir -p "${r%.rar}" && unrar x -o+ -inul "$r" "${r%.rar}/" && rm -f "$r"; done); done
  cd /content/research; touch /content/data.done; log "data ready"
fi
pip install -q onnxscript onnxruntime pypdf >/dev/null 2>&1

train() {  # $1 = seed
  if [ ! -f /content/runs/seed$1/meta.json ]; then
    log "training seed $1"
    python3 -u train_anomaly.py --seed $1 --out /content/runs/seed$1 > /content/out/train_seed$1.log 2>&1
    mkdir -p /content/out/runs/seed$1 && cp /content/runs/seed$1/{meta.json,model.pt,scaler.pkl} /content/out/runs/seed$1/ 2>/dev/null
    cp /content/runs/seed$1/model.onnx /content/out/runs/seed$1/ 2>/dev/null
    log "seed $1 done: $(tail -1 /content/out/train_seed$1.log)"
  fi
}

train 0
if [ ! -f /content/out/llm_samples.json ]; then
  log "drawing LLM samples"; python3 -u gen_llm_samples.py > /content/out/gen_llm_samples.log 2>&1
  cp /content/llm_samples.json /content/out/llm_samples.json && log "llm samples ready"
fi
for s in 1 2 3 4; do train $s; done
log "evaluating models + baselines"
python3 -u eval_models.py > /content/out/eval_models.log 2>&1
cp /content/res_models/*.json /content/out/ 2>/dev/null
log "ALL DONE"; touch /content/out/ALL.done
