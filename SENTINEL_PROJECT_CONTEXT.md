# SENTINEL — Agentic AI IoT Security System
## Project Context Document for AI Assistants

> **How to use this file:** Paste this entire document at the start of any AI conversation.
> The AI will have full context about the project, stack, architecture, and coding conventions.

---

## 1. Who I Am

- **Name:** Vinay
- **Role:** Security Engineer
- **Channel:** charon19d (cybersecurity YouTube)
- **Project type:** Final Year Project (FYP)
- **Experience:** CTF competitor (forensics, reverse engineering, steganography, binary RE), mobile app security audits, web vulnerability research

---

## 2. Project Summary

**SENTINEL** is a consumer-grade, plug-and-play network security appliance powered by a multi-agent AI system. It protects home IoT devices from cyber attacks by:

- Automatically discovering and risk-profiling every device on the home network
- Running an LSTM anomaly detector trained on per-device traffic baselines
- Using a local LLM (Gemma 4) to classify threats using MITRE ATT&CK for ICS/IoT
- Deploying virtual honeypots and honeytokens to trap and study attackers
- Enforcing firewall rules via eBPF/XDP + nftables in real time
- Presenting everything through a Next.js PWA dashboard with live alerts

**Final target hardware:** Raspberry Pi 5 (8GB RAM) — inline bridge between ISP router and home switch.
**Current development:** PC/laptop (Linux or WSL2 Ubuntu) — full stack runs identically.

---

## 3. Development Strategy

### PC-First Approach
Everything is built and tested on a laptop first. The codebase is designed to be 99% identical on PC and Pi 5.

| What | PC (dev) | Pi 5 (deploy) |
|------|----------|---------------|
| Packet capture | libpcap on local Wi-Fi interface | libpcap on bridge interface (br0) |
| LLM model | Gemma 4 E4B via Ollama | Gemma 4 E2B via Ollama |
| llama.cpp | Pre-built x86_64 | Recompile for ARM64 |
| Docker containers | Same images | Same images (ARM64 auto-pulled) |
| nftables rules | Same syntax | Same syntax |
| All Python/Node code | Identical | Identical |

### Pi Porting Delta (only these 4 things change)
1. Add netplan bridge config (single YAML file)
2. `ollama run gemma4:e2b` instead of `gemma4:e4b`
3. Recompile llama.cpp for ARM64
4. Docker pulls ARM64 images automatically

---

## 4. System Architecture

### Layer Overview

```
Layer 0  →  IoT Devices (TVs, cameras, bulbs, thermostats, wearables)
                |  [all traffic passes through SENTINEL]
Layer 1  →  Network Capture & Packet Engine
                |  libpcap + nDPI DPI + mDNS/SSDP/ARP passive sniff
Layer 2  →  Device Discovery & Risk Profiler Agent
                |  OUI lookup + Nmap + NVD CVE API + SQLite registry
Layer 3  →  Agentic AI Engine  (multi-agent via LangGraph + Redis)
            ├── Anomaly Detector Agent  (LSTM Autoencoder + Isolation Forest)
            ├── Threat Classifier Agent (Gemma 4 E4B → MITRE ATT&CK JSON)
            └── Response Planner Agent  (YAML policy → nftables/honeypot actions)
                |
        ┌───────┴───────┐
Layer 4  →  Deception Layer      Layer 5  →  Firewall & Response Engine
            Cowrie (SSH)                     eBPF/XDP packet filter
            OpenCanary (multi)               nftables rule injection
            UPnP honeypot                    VLAN micro-segmentation
            Honeytokens                      Auto quarantine (DHCP + ARP)
                |                                    |
Layer 6  →  Threat Intel Bus + Log Store
                |  STIX/TAXII feeds + IoC enrichment + SQLite/Loki
Layer 7  →  Dashboard & Alert UI
                Next.js 14 PWA + D3.js + WebSockets + Web Push
```

### Physical Topology

```
[Internet] → [ISP Router] → [SENTINEL eth0 | br0 bridge | eth1] → [Home Switch/AP] → [IoT Devices]
```

SENTINEL is a **transparent Layer 2 bridge** — zero reconfiguration needed on the router or devices.

---

## 5. Complete Technology Stack

### AI & Machine Learning

| Component | Tool | Notes |
|-----------|------|-------|
| Anomaly detection | PyTorch LSTM Autoencoder | Self-trained on local network traffic (4 hrs collection + 30 min training) |
| Statistical outlier (cold start) | scikit-learn Isolation Forest | Unsupervised, no training data needed |
| Threat classification LLM | **Gemma 4 E4B** via Ollama (dev) | Native function calling, 128K context, Apache 2.0 |
| Pi 5 LLM | **Gemma 4 E2B** via Ollama | Confirmed 7.6 tok/s on Pi 5, fits in ~2GB RAM |
| LSTM inference runtime | ONNX Runtime | Fast ARM64 inference, export PyTorch → ONNX |
| Optional LLM fine-tune | QLoRA via Unsloth | Google Colab T4 free, ~500 MITRE ATT&CK examples, ~2 hrs |

### Network & Security

| Component | Tool | Notes |
|-----------|------|-------|
| Packet capture | Scapy + pyshark (libpcap) | Python-native; AF_PACKET for production |
| Deep packet inspection | nDPI Python bindings | 300+ protocols including MQTT, UPnP, Zigbee |
| Device fingerprinting | python-nmap + custom passive sniffer | OUI DB + Nmap + mDNS/SSDP/ARP/DHCP |
| Firewall control | nftables via Python subprocess | Same syntax PC and Pi |
| Fast kernel packet drop | eBPF via BCC toolkit | XDP hook, sub-millisecond latency |

### Honeypots & Deception

| Component | Tool | Docker Image |
|-----------|------|--------------|
| SSH/Telnet honeypot | Cowrie | `cowrie/cowrie:latest` |
| Multi-service honeypot | OpenCanary (HTTP, SMB, FTP, MySQL, Redis) | `thinkst/opencanary` |
| UPnP device emulator | Custom (U-POT style) | Custom Dockerfile (build from scratch) |
| Traffic redirect | nftables DNAT (Python daemon) | No container — Python subprocess |
| Honeytoken alerts | Canarytokens self-hosted | `thinkst/canarytokens-docker` |

Each honeypot gets its own virtual IP via **macvlan** — they appear as real separate devices on the network.

### Infrastructure & Data

| Component | Tool | Notes |
|-----------|------|-------|
| Agent orchestration | LangGraph (Python) | Multi-agent state machines |
| Inter-agent event bus | Redis pub/sub | Sub-ms latency, `docker: redis:alpine` |
| Device registry | SQLite + SQLAlchemy | Single .db file, zero config |
| Log storage | Loki + Grafana | Lighter than Elasticsearch on Pi |
| Container runtime | Docker + Docker Compose | ARM64 images auto-pulled on Pi |

### API & Dashboard

| Component | Tool | Notes |
|-----------|------|-------|
| Backend REST API | FastAPI + Uvicorn | Async Python, auto OpenAPI docs |
| Real-time events | WebSockets via FastAPI | Push to browser without polling |
| Frontend | Next.js 14 + TailwindCSS | PWA, mobile-ready |
| Device risk visualisation | D3.js force-directed graph | Nodes = devices, size = risk score |
| Charts | Recharts | React integration |
| Mobile push alerts | Web Push API | No Firebase, fully self-hosted |

### Threat Intelligence

| Source | Provides | Cost |
|--------|----------|------|
| NVD (NIST) | CVE data, CVSS scores | Free |
| AbuseIPDB | IP reputation | Free: 1000 checks/day |
| OTX AlienVault | IoC feeds (STIX/TAXII) | Free |
| MISP | Community IoC sharing | Free / self-hosted |
| MITRE ATT&CK for ICS | TTP taxonomy for LLM | Free / open STIX on GitHub |
| Quad9 | DNS malware domain blocking | Free (9.9.9.9) |

---

## 6. AI Agent Design Detail

### Agent 1 — Anomaly Detector

- **Model:** Kitsune-based LSTM Autoencoder (Pre-trained on Kaggle/IoT datasets)
- **Input features:** 115 Incremental Statistics (Kitsune framework) tracking Jitter, Magnitude, Radius, and Correlation across multiple time windows (L5, L3, L1, L0.1, L0.01).
- **Training Strategy:** 
  - **Pre-trained:** Initial deployment using models trained on high-quality public IoT datasets (e.g., IoT-23, Kitsune dataset).
  - **Fine-tuning:** Local adaptation where the model is fine-tuned on the specific home network baseline to reduce false positives.
- **Inference:** ONNX Runtime executing on packet-level statistics. Reconstruction error above `sentinel_threshold.txt` = anomaly event.
- **Output:** publishes `{device_id, anomaly_score, feature_vector, alert_level}` to Redis channel `anomaly:events`.

### Agent 2 — Threat Classifier

- **Model:** Gemma 4 E4B (dev) / Gemma 4 E2B (Pi) via Ollama REST API
- **Input:** anomaly event from Redis + device profile from SQLite + local STIX IoC context
- **Native function calling:** LLM calls tools `classify_threat()`, `check_ioc()`, `recommend_action()`
- **Output JSON schema:**
```json
{
  "tactic": "Command and Control",
  "technique_id": "T0884",
  "confidence": 0.91,
  "severity": 9,
  "summary": "Camera communicating with likely C2 server",
  "recommended_action": "quarantine",
  "indicators": ["185.220.101.x", "update.hikvision-upgrade.ru"]
}
```
- **Publishes to Redis:** `threat:classified`

### Agent 3 — Response Planner

- **Input:** classified threat from Redis `threat:classified`
- **Policy tree (YAML-defined):**
  - Severity 9–10 → quarantine device + push dashboard alert (requires user confirmation via UI)
  - Severity 6–8 → redirect device traffic to honeypot + push alert
  - Severity 1–5 → log event + passive monitor
- **Actions via FastAPI internal endpoints:**
  - `POST /internal/firewall/block/{ip}`
  - `POST /internal/firewall/redirect/{ip}/{honeypot}`
  - `POST /internal/alert/push`
- **Security gate:** any severity 8+ action requires explicit confirmation via dashboard WebSocket ACK before execution — prevents LLM prompt injection from silently blocking devices

### Orchestration

```
Redis pub/sub channels:
  capture:flows       ← raw flow metadata from packet capture
  anomaly:events      ← LSTM/IF anomaly detections
  threat:classified   ← LLM TTP classifications
  action:execute      ← firewall/honeypot commands
  alert:push          ← dashboard WebSocket events
```

LangGraph manages the state machine for each active threat investigation.

---

## 7. Device Registry Schema (SQLite)

```sql
CREATE TABLE devices (
    device_id     TEXT PRIMARY KEY,
    mac           TEXT NOT NULL,
    ip            TEXT,
    vendor        TEXT,
    os_guess      TEXT,
    firmware_ver  TEXT,
    open_ports    TEXT,   -- JSON array
    cve_list      TEXT,   -- JSON array of {cve_id, cvss_score, description}
    risk_score    REAL,   -- 0.0 to 10.0
    last_seen     DATETIME,
    baseline_path TEXT,   -- path to .onnx model file for this device
    is_quarantined INTEGER DEFAULT 0
);

CREATE TABLE threat_events (
    event_id      TEXT PRIMARY KEY,
    device_id     TEXT,
    tactic        TEXT,
    technique_id  TEXT,
    confidence    REAL,
    severity      INTEGER,
    summary       TEXT,
    indicators    TEXT,   -- JSON array
    action_taken  TEXT,
    timestamp     DATETIME,
    resolved      INTEGER DEFAULT 0
);
```

---

## 8. Project Folder Structure

```
sentinel/
├── core/
│   ├── capture/
│   │   ├── sniffer.py          # Scapy raw capture + nDPI analysis
│   │   ├── flow_parser.py      # Per-flow feature extraction
│   │   └── redis_publisher.py  # Publish flows to Redis
│   ├── fingerprinting/
│   │   ├── discovery.py        # Passive listener (mDNS, SSDP, DHCP, ARP)
│   │   ├── scanner.py          # Active Nmap service scanner
│   │   ├── oui.py              # MAC-to-vendor lookup
│   │   ├── cve.py              # NIST NVD API scanner
│   │   └── registry.py         # SQLite + SQLAlchemy device registry
│   └── firewall/
│       ├── nftables_manager.py # nftables rule injection via subprocess
│       ├── ebpf_loader.py      # BCC eBPF/XDP program loader
│       └── quarantine.py       # DHCP starvation + ARP block
│
├── agents/
│   ├── anomaly/
│   │   ├── kitsune.py          # 115 Incremental Stats Extractor
│   │   ├── inference.py        # ONNX Runtime inference engine
│   │   └── finetune.py         # Local baseline adaptation script
│   ├── classifier/
│   │   ├── gemma_client.py     # Ollama REST API client
│   │   ├── prompt_builder.py   # System prompt + anomaly event formatter
│   │   ├── mitre_context.py    # Load local MITRE ATT&CK STIX data
│   │   └── tools.py            # LLM function calling tool definitions
│   └── responder/
│       ├── policy.py           # YAML policy loader + decision engine
│       ├── graph.py            # LangGraph agent graph definition
│       └── actions.py          # Action executor (calls FastAPI endpoints)
│
├── deception/
│   ├── docker-compose.yml      # Cowrie + OpenCanary + Canarytokens
│   ├── cowrie/
│   │   └── cowrie.cfg          # Cowrie config (virtual IPs, log format)
│   ├── opencanary/
│   │   └── opencanary.conf     # Services to emulate
│   └── redirect/
│       ├── redirect_daemon.py  # Redis subscriber → nftables DNAT rules
│       └── macvlan_setup.sh    # Virtual IP setup for honeypot isolation
│
├── api/
│   ├── main.py                 # FastAPI app entry point
│   ├── routes/
│   │   ├── devices.py          # GET /api/devices, /api/cve/{id}
│   │   ├── threats.py          # GET /api/threats
│   │   ├── actions.py          # POST /api/quarantine, /api/redirect
│   │   └── intel.py            # GET /api/intel/ioc/{ip}
│   ├── websocket.py            # WS /ws/events — real-time event stream
│   └── internal.py             # Internal endpoints for agent → firewall calls
│
├── dashboard/                  # Next.js 14 PWA
│   ├── pages/
│   │   ├── index.js            # Main dashboard (device risk map)
│   │   ├── threats.js          # Live threat feed
│   │   └── devices/[id].js     # Per-device CVE + traffic detail
│   ├── components/
│   │   ├── RiskGraph.jsx       # D3.js force-directed device graph
│   │   ├── ThreatFeed.jsx      # WebSocket live threat list
│   │   ├── DeviceCard.jsx      # Per-device risk card
│   │   └── QuarantineModal.jsx # Confirmation gate for severity 8+ actions
│   └── lib/
│       ├── websocket.js        # WebSocket client hook
│       └── api.js              # FastAPI client functions
│
├── intel/
│   ├── nvd_sync.py             # NVD CVE API background sync
│   ├── abuseipdb.py            # IP reputation check
│   ├── otx_sync.py             # OTX AlienVault STIX feed sync
│   └── mitre_loader.py         # Load MITRE ATT&CK STIX into local store
│
├── models/                     # Saved weights (gitignored for large files)
│   └── .gitkeep
│
├── data/                       # Runtime data (gitignored)
│   ├── sentinel.db             # SQLite device + threat registry
│   └── .gitkeep
│
├── config/
│   ├── policy.yaml             # Response Planner policy rules
│   ├── settings.py             # Centralised config (ports, thresholds, API keys)
│   └── logging.yaml            # Structured logging config
│
├── docker-compose.yml          # Full infra: Redis, Loki, Grafana, honeypots
├── requirements.txt            # Python dependencies
├── .env.example                # API keys template (NVD, AbuseIPDB, OTX)
└── README.md
```

---

## 9. Key API Endpoints

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/api/devices` | All devices with risk scores, CVEs, ports |
| GET | `/api/threats` | Recent threat events with TTP classification |
| POST | `/api/quarantine/{ip}` | Quarantine device (UI confirmation required ≥ severity 8) |
| POST | `/api/honeypot/redirect/{ip}` | Manually redirect IP to honeypot |
| GET | `/api/cve/{device_id}` | Full CVE list for a specific device |
| GET | `/api/intel/ioc/{ip}` | Check IP against all threat intel feeds |
| WS | `/ws/events` | Real-time WebSocket stream of threat events |

---

## 10. Response Policy (policy.yaml structure)

```yaml
rules:
  - name: critical_threat
    severity_min: 9
    severity_max: 10
    actions:
      - quarantine_device        # requires dashboard confirmation
      - push_alert_critical
    require_confirmation: true

  - name: high_threat
    severity_min: 6
    severity_max: 8
    actions:
      - redirect_to_honeypot     # automatic, no confirmation needed
      - push_alert_high
    require_confirmation: false

  - name: medium_low_threat
    severity_min: 1
    severity_max: 5
    actions:
      - log_event
              - passive_monitor
    require_confirmation: false
```

---

## 11. Build Order (What to Build First)

| Phase | Weeks | Goal | Done When |
|-------|-------|------|-----------|
| 1 | 1–2 | Packet capture + device discovery + SQLite registry | All home devices visible with vendor, IP, ports, CVE scores |
| 2 | 3–4 | LSTM Autoencoder training + Isolation Forest | Model flags abnormal test traffic correctly |
| 3 | 5–6 | Gemma 4 via Ollama + LangGraph classifier agent | LLM classifies simulated port scan as T1046 |
| 4 | 7–8 | Cowrie + OpenCanary + nftables DNAT redirect daemon | nmap against honeypot logs session in Cowrie |
| 5 | 9–10 | FastAPI backend + WebSocket event stream | All endpoints return data, WebSocket streams live |
| 6 | 11–12 | Next.js dashboard (D3 graph, threat feed, quarantine UI) | Full end-to-end demo on PC |
| 7 | 13–14 | Integration testing with Metasploit + hping3 | Detection rate >90%, false positive rate <5% |
| 8 | 15–16 | Raspberry Pi 5 port + physical appliance demo | Demo-ready on real hardware |

---

## 12. Important Constraints & Decisions

- **No training from scratch for the LLM** — use Gemma 4 pre-trained via Ollama, prompt engineering only (optional LoRA fine-tune on Colab)
- **LSTM must be trained locally** — it learns this specific home network's baseline, not a generic dataset
- **Security gate is mandatory** — LLM output must never directly trigger severity 8+ firewall actions without dashboard user confirmation (prevents prompt injection attacks)
- **All processing is on-device** — no mandatory cloud dependency; cloud sync is optional and privacy-first (anonymised IoC sharing only)
- **Honeypot IPs use macvlan** — each honeypot has its own virtual IP, looks like a real device on the network
- **Same codebase PC and Pi** — do not write PC-specific code; use config flags for any differences
- **Apache 2.0 license for Gemma 4** — no licensing restrictions for publishing the full project

---

## 13. Hardware (Final Deployment)

| Component | Spec | Cost (INR) |
|-----------|------|------------|
| Raspberry Pi 5 8GB | Primary SBC — mandatory 8GB not 4GB | ~6,000–7,000 |
| Secondary NIC | USB 3.0 Gigabit adapter for two-NIC bridge | ~500–1,500 |
| Monitor mode adapter (dev) | TP-Link TL-WN722N v1 | ~800 |
| Storage | 64GB+ microSD A2 or USB 3.0 SSD | ~500–1,500 |
| Power supply | Official Pi 5 27W USB-C | ~800 |

---

## 14. Novel Research Contributions (for paper/report)

1. **On-device LLM TTP classification at <10W** — Gemma 4 E2B at 7.6 tok/s on Pi 5 with no cloud, no GPU
2. **AI-driven dynamic honeypot coordination** — Response Planner agent selects which honeypot to redirect each attacker to based on classified TTP (not static rules)
3. **Consumer-grade threat attribution on a $75 device** — passive fingerprinting + LSTM baselining + deception telemetry combined on a single SBC

---

## 15. Key Resources

| Resource | URL |
|----------|-----|
| Gemma 4 on Ollama | ollama.com/library/gemma4 |
| MITRE ATT&CK for ICS | attack.mitre.org/matrices/ics/ |
| NVD CVE API | nvd.nist.gov/developers/vulnerabilities |
| Cowrie docs | github.com/cowrie/cowrie |
| OpenCanary | github.com/thinkst/opencanary |
| nDPI | github.com/ntop/nDPI |
| LangGraph | github.com/langchain-ai/langgraph |
| eBPF BCC toolkit | github.com/iovisor/bcc |
| OTX AlienVault | otx.alienvault.com |
| AbuseIPDB API | abuseipdb.com/api |
| Canarytokens | github.com/thinkst/canarytokens-docker |

---

*SENTINEL — Final Year Project by Vinay (charon19d) — April 2026*
