# SENTINEL — Evaluation Plan & Research Paper Roadmap

> Working document for producing the experimental results needed for a research paper.  
> Companion to [RESEARCH_PAPERS.md](RESEARCH_PAPERS.md) (literature review, 24 papers, 6 research gaps).
>
> **Status (updated 2026-09-25): EVALUATION DONE.** Results, code and the paper
> are in `research/` and `paper/`. This file is kept as the original plan.
> What changed from the plan: detection was evaluated on **N-BaIoT** (the model's
> actual training set, recovered from its scaler) rather than CICIoT2023, with a
> held-out-device split; baselines were a dense AE (N-BaIoT's own design) and
> Isolation Forest; the LLM test used N-BaIoT attack classes with a pre-registered
> mapping (`research/PREREGISTRATION.md`); timing ran on a 4-core aarch64 VM
> (no Pi). Plan items not done: CICIoT2023, KitNET baseline, honeypot dataset
> analysis, cgroup resource profiling.
>
> ~~**Status:** Literature review complete. Evaluation not started.~~  
> **Hard constraint:** No physical Raspberry Pi 5 available. No machine can run 24/7.  
> **Consequence:** Evaluation is dataset-replay based, not live-deployment based. This is standard practice and is defensible if stated correctly (see §3).

---

## 0. Current Status

| Paper section | Status |
|---|---|
| Problem statement | ✅ Done |
| Related work (24 papers) | ✅ Done — see RESEARCH_PAPERS.md |
| Research gaps (6 identified) | ✅ Done |
| System architecture (7 layers) | ✅ Done — implemented |
| Implementation | ✅ Done — working system |
| **Evaluation / results** | ✅ **Done — see `research/` and `paper/main.pdf`** |
| Discussion & conclusion | ❌ Blocked on evaluation |

**Roughly 60-70% of the paper is writable today.** The missing 30% is the evaluation section, which is what reviewers weight most heavily.

---

## 1. Verified Facts (checked August 2026)

These were fact-checked before being committed to this plan.

| Claim | Verdict | Detail |
|---|---|---|
| CICIoT2023 is free and public | ✅ **Confirmed** | 2.7GB compressed / ~13GB uncompressed. CSV + PCAP. 47M+ labeled flows, 33 attack types. From Canadian Institute for Cybersecurity, UNB. |
| Public Cowrie honeypot datasets exist | ✅ **Confirmed** | MURHCAD and a Kaggle dataset — see §4.6 |
| "UNSW Cowrie Dataset" | ❌ **Unverified — do not cite** | Could not confirm this exists. An earlier draft of this plan named it in error. Use the verified datasets in §4.6 instead. |
| Oracle Cloud free ARM64 as a Pi substitute | ⚠️ **Do not rely on** | AUP does not explicitly permit honeypots; user reports of account suspension; free-tier ARM capacity frequently unavailable. See §3.2 |
| "Cloud ARM64 ≈ Raspberry Pi 5" | ❌ **Methodologically invalid** | See §3.1 — this claim would likely get the paper rejected |

---

## 2. Datasets to Download

### 2.1 CICIoT2023 (primary — unblocks 5 of 7 experiments)

- **URL:** https://www.unb.ca/cic/datasets/iotdataset-2023.html
- **Size:** 2.7GB compressed → ~13GB uncompressed
- **Contents:** `PCAP/` (raw traffic), `CSV/` (extracted features, ML-ready), `Example/`, `Supplementary/`
- **Labels:** 33 attack types across 10 IoT device categories — DDoS, DoS, Mirai, Recon, Spoofing, Web-based, Brute Force, plus benign
- **Citation:** Neto et al., *CICIoT2023: A Real-Time Dataset and Benchmark for Large-Scale Attacks in IoT Environment*, Sensors (MDPI), 2023. https://www.mdpi.com/1424-8220/23/13/5941
- **Why this one:** It is the current standard IoT IDS benchmark, it is recent, and it has both PCAP (so SENTINEL's Layer 1 capture path can be exercised end-to-end) and CSV (for fast ML iteration).

**Use PCAP, not just CSV.** Replaying PCAP through `sentinel.core.capture.main --pcap` exercises the real pipeline (capture → flow parse → anomaly → classify → respond) and is what makes the latency numbers credible. CSV-only evaluation would only test the model, not the system.

### 2.2 Honeypot datasets (see §4.6)

---

## 3. The Hardware Problem — Correct Handling

### 3.1 Do NOT claim cloud ARM is equivalent to a Raspberry Pi 5

An earlier draft of this plan suggested writing *"evaluated on an ARM64 cloud instance equivalent to the target Raspberry Pi 5."* **This is indefensible and must not go in the paper.**

| | Raspberry Pi 5 (8GB) | Ampere A1 cloud (4c/24GB) |
|---|---|---|
| Thermal behaviour | **Throttles to ~1.5GHz within ~9 seconds** under sustained load without active cooling; 85°C cap | Never throttles |
| RAM | 8GB LPDDR4X | 24GB server-class |
| Memory bandwidth | Constrained | Substantially higher |
| Storage | microSD / NVMe HAT | Datacenter NVMe |

Why this matters specifically for SENTINEL:
- **LLM model choice is dictated by RAM.** Gemma E2B vs E4B is decided by the 8GB ceiling. A 24GB instance makes that constraint disappear, so any LLM latency measured there is not representative.
- **Sustained inference is thermally bound on a Pi.** Pi 5 throttles in seconds under load. A cloud instance running the same workload reports numbers the Pi can never sustain.

A reviewer working in edge ML will catch this immediately.

### 3.2 Do NOT depend on Oracle Cloud free tier

- Oracle's Acceptable Use Policy does not explicitly permit honeypots. Deliberately exposing vulnerable services puts your IP in abuse feeds.
- Multiple user reports (2025-2026) of Always Free accounts being suspended for perceived abuse or unusual load.
- Oracle reserves the right to terminate without detailed cause.
- Free-tier ARM (Ampere A1) capacity is frequently unavailable — "out of host capacity" is a well-known persistent issue.

Building the evaluation on this creates a dependency that can vanish mid-project.

### 3.3 What to do instead — three options in priority order

**Option A (best, cheap): Borrow a Raspberry Pi.**  
Most CS / engineering departments have Raspberry Pis in their labs. A Pi 5 8GB is ~$80 new. **Ask the supervisor or lab technician first.** One afternoon with real hardware produces the single measurement that makes the central claim real. Do this before accepting any substitute.

**Option B (zero cost, defensible): cgroup-constrained laptop run.**

```bash
# Docker
docker run --cpus=4 --memory=8g --memory-swap=8g sentinel

# Or without Docker
systemd-run --scope -p CPUQuota=400% -p MemoryMax=8G bash run.sh
```

Then write, verbatim:

> *"Resource measurements were collected under enforced cgroup limits of 4 CPU cores and 8 GB RAM, modelling the compute and memory envelope of the Raspberry Pi 5 target platform. We note this does not model the thermal throttling or memory-bandwidth constraints of the physical device; sustained-load performance on real hardware is expected to be lower, and physical-hardware validation is left to future work."*

This is honest, costs nothing, requires no hardware, and is acceptable to reviewers. It is strictly better than a false equivalence claim.

**Option C: Reframe the contribution.**  
If no hardware is obtainable, drop "runs on Raspberry Pi 5" from the *claims* and move it to *future work*. Frame the contribution as the architecture and the integration, evaluated under resource constraints. The 6 research gaps in RESEARCH_PAPERS.md do not actually depend on Pi hardware — only Gap 1 mentions consumer hardware, and it can be phrased as "consumer-grade resource envelope."

---

## 4. Experiments

### 4.1 Detection accuracy — CICIoT2023

**Goal:** Precision, Recall, F1, and **False Positive Rate** for SENTINEL's anomaly detector.

FPR matters more than accuracy here. A home appliance with a 5% FPR is unusable — say so explicitly in the paper and report it prominently.

- Input: CICIoT2023 CSV (fast iteration) and PCAP (end-to-end validation)
- Report per attack category, not just aggregate
- Include a confusion matrix

**Effort:** ~1 day. **Hardware:** laptop, one session.

---

### 4.2 Baseline comparison

You cannot claim to improve on prior work without running it on the same data.

| Baseline | Source | Notes |
|---|---|---|
| **Kitsune / KitNET** | https://github.com/ymirsky/Kitsune-py | Open source. Closest architectural ancestor (RESEARCH_PAPERS.md Paper 3). Most important baseline. |
| Plain Isolation Forest | scikit-learn | Already a SENTINEL component — isolates its contribution |
| Plain LSTM Autoencoder | Your own, LSTM only | Isolates the hybrid's contribution |

All three on the identical CICIoT2023 slice, identical train/test split.

**Effort:** ~1 day. **Hardware:** laptop.

---

### 4.3 Ablation study

Reviewers will ask what each of the 7 layers actually contributes. Without this, "7 layers" reads as complexity rather than contribution.

| Configuration | F1 | FPR | Latency | Notes |
|---|---|---|---|---|
| Isolation Forest only | | | | Cold-start path alone |
| LSTM-AE only | | | | Trained path alone |
| LSTM-AE + IF (no LLM) | | | | Detection without classification |
| **Full SENTINEL** (+ Gemma + LangGraph) | | | | Complete pipeline |

**Effort:** ~1 day. **Hardware:** laptop.

---

### 4.4 End-to-end latency — the headline number

This is the number that demonstrates Gap 4 (detection-to-response under 2 seconds). Instrument every stage handoff:

```
packet ingested
  → t1: flow parsed
  → t2: anomaly score produced          (ONNX inference)
  → t3: Gemma classification returned   (Ollama, expect this dominates)
  → t4: LangGraph response decided
  → t5: nftables rule written
TOTAL = t5 - t0
```

`seed_data.py` already exists and can drive this. Report per-stage breakdown, not just the total — the per-stage table is what makes the claim credible and shows where the bottleneck is (almost certainly the LLM).

Run 5+ times, report mean ± standard deviation.

**Effort:** ~0.5 day. **Hardware:** laptop, ~15 minutes of runtime.

---

### 4.5 Resource utilisation

Under the cgroup constraints from §3.3 Option B (or on a real Pi if borrowed):

- CPU % per agent — anomaly worker, classifier worker, responder worker, capture, API
- Peak and steady-state RAM, total and per-process
- Sustained packets/sec before the capture layer drops frames
- If on real hardware: power draw, and CPU temperature over a sustained run (this is where throttling shows up)

**Effort:** ~0.5 day.

---

### 4.6 Honeypot analysis — use published data, do not self-host

**Do not expose your own honeypots.** Two reasons:

1. **Ethics approval.** Collecting attacker IPs and credentials is personal data under GDPR. Most universities require ethics board sign-off, which takes weeks. **Ask the supervisor whether this is needed.** Using published datasets almost certainly avoids it.
2. **Hosting risk.** See §3.2.

Verified public datasets:

| Dataset | Contents | Link |
|---|---|---|
| **MURHCAD** — Multi-Regional Cloud Honeypot Dataset | Cowrie deployed across multiple geographic regions; temporal resolution, geolocation, protocol metadata; analysis code and data-access instructions published; explicitly designed for reproducible research | https://arxiv.org/pdf/2601.05813 |
| **Kaggle Cowrie** | Medium-interaction SSH honeypot sessions | https://www.kaggle.com/datasets/xmlyna/cowrie-honeypot |

Replay these through SENTINEL's Honeypots analysis path and report: total sessions, unique attacker IPs, top credential pairs, attack-type distribution (Mirai / brute force / RCE), and what proportion would have been auto-blocked by the OTX + AbuseIPDB → nftables pipeline.

That last metric directly evidences **Gap 5** (honeypot intelligence feeding automated firewall) — which is a genuine contribution and needs no live deployment to demonstrate.

**Effort:** ~1 day. **Hardware:** none.

---

### 4.7 LLM ATT&CK classification accuracy

**Do not hand-write 50 test cases and grade them yourself** — self-labelled data graded by the system's author gets discounted by reviewers.

**Better design:** CICIoT2023 already carries ground-truth attack-class labels (DDoS, DoS, Mirai, Recon, Spoofing, Web-based, Brute Force). Procedure:

1. Build a documented mapping from each CICIoT2023 attack class → MITRE ATT&CK technique(s). Do this **once, up front, before seeing any model output**, and publish the mapping table in the paper.
2. Sample several hundred flows across classes.
3. Run them through the Gemma classifier.
4. Measure agreement against the pre-registered mapping.

This gives defensible ground truth at scale instead of 50 self-made cases, and the pre-registration removes the bias objection.

Also report: classification latency distribution, and the rate of malformed / unparseable JSON output from the LLM (a real and reportable failure mode for structured LLM output).

**Effort:** 1-2 days.

---

### 4.8 Comparison table for the paper

| Feature | Kitsune | AgenticCyber | Pi 5 Edge IDS | **SENTINEL** |
|---|---|---|---|---|
| All 7 layers integrated | ❌ | ❌ | ❌ | ✅ |
| Local (non-cloud) LLM | ❌ | ❌ | ❌ | ✅ |
| Honeypot integration | ❌ | ❌ | ❌ | ✅ |
| Automated firewall response | ❌ | ❌ | ❌ | ✅ |
| CVE / risk profiling | ❌ | ❌ | ❌ | ✅ |
| Consumer-hardware resource envelope | ✅ | ❌ | ✅ | ✅ |
| F1-score | *fill* | 96.2% (reported) | *fill* | **?** |
| Detect → respond latency | — | 420 ms (reported) | — | **?** |

Fill the blanks from §4.1-4.4. Note in the caption where a figure is taken from the cited paper rather than reproduced by you.

---

## 5. Methodology Requirements

Standard reviewer expectations that must not be skipped:

- [ ] **Explicit threat model.** State what is in scope (network-observable attacks against IoT devices on the local segment) and out of scope (physical access, encrypted payload content analysis, supply-chain compromise, attacks on SENTINEL itself). Unstated scope is punished.
- [ ] **Statistical rigor.** Every number from 5+ runs, reported as mean ± std. No single-run figures.
- [ ] **Train/test discipline.** No test data in training. State the split explicitly.
- [ ] **Reproducibility.** Pin dataset version, model versions (Gemma tag, ONNX opset), random seeds. State the exact hardware and cgroup limits.
- [ ] **Limitations section.** Write it honestly — no physical hardware validation, dataset-replay rather than live deployment, honeypot data from third-party collection. Reviewers respect stated limitations far more than they punish them; unstated ones they punish hard.
- [ ] **Ethics statement.** Say that no personal data was collected by the authors and that honeypot data came from published datasets under their licence terms.

---

## 6. Venue Calibration

| Target | Evidence required | Achievable? |
|---|---|---|
| **FYP thesis / report** | §4.1-4.7 as scoped here | ✅ **Comfortably above the bar** |
| **Workshop paper** (IoT security / edge ML workshops) | §4.1-4.7 done properly + §5 | ✅ **Realistic** |
| Mid-tier conference or journal | Above + real Pi 5 hardware + longer honeypot study | ⚠️ Stretch |
| Top-tier (NDSS / CCS / USENIX / S&P) | Novel technique + months of evaluation + strong baselines | ❌ Not on this timeline |

**Recommended: target the thesis first, then adapt it into a workshop paper.** Both are achievable with zero hardware purchases.

---

## 7. Execution Checklist

### Immediate — ask the supervisor
- [ ] Does the department have a Raspberry Pi 5 (or Pi 4) that can be borrowed?
- [ ] Is ethics approval required for anything honeypot-related? (Using published datasets should avoid it — confirm.)
- [ ] What venue is being targeted? This sets the evidence bar (§6).

### Week 1 — unblock
- [ ] Download CICIoT2023 (~2.7GB) from UNB
- [ ] Add stage timestamps to the pipeline (15 min of work, produces the headline number)
- [ ] Clone Kitsune-py for the baseline
- [ ] Download MURHCAD and/or Kaggle Cowrie dataset

### Week 2 — core experiments
- [ ] §4.1 Detection accuracy + FPR + confusion matrix
- [ ] §4.2 Baseline comparison (Kitsune, IF, LSTM)
- [ ] §4.4 End-to-end latency, per-stage, 5+ runs

### Week 3 — depth
- [ ] §4.3 Ablation study
- [ ] §4.5 Resource utilisation under cgroup limits
- [ ] §4.7 Pre-register the CICIoT2023 → ATT&CK mapping, then run the LLM evaluation

### Week 4 — write up
- [ ] §4.6 Honeypot dataset analysis
- [ ] §4.8 Fill the comparison table
- [ ] §5 Threat model, limitations, ethics statement
- [ ] Assemble the evaluation section

**Total active effort: roughly 6-8 working days.** No purchases required, no machine running for weeks.

---

## 8. Open Questions

| Question | Owner | Status |
|---|---|---|
| Can a Raspberry Pi be borrowed from the department? | Ask supervisor | Open |
| Is ethics approval needed? | Ask supervisor | Open |
| Target venue — thesis only, or workshop paper too? | Decide | Open |
| Which Gemma variant to benchmark (E2B vs E4B)? | Depends on hardware answer | Open |
| Build the CICIoT2023 benchmark harness | Can be scripted | Not started |

---

*Created: August 2026 · SENTINEL FYP · Vinay (sharma19d)*  
*Companion document: [RESEARCH_PAPERS.md](RESEARCH_PAPERS.md)*
