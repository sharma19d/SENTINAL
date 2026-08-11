<div align="center">
<img width="1464" height="923" alt="Screenshot 2026-05-22 at 9 55 33 AM" src="https://github.com/user-attachments/assets/e03464b0-b1cc-4ef4-88fd-e2522af97e8b" />


# SENTINEL
### Agentic AI IoT Security System

[![Python](https://img.shields.io/badge/Python-3.11+-blue)](https://python.org)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.100+-green)](https://fastapi.tiangolo.com)
[![React](https://img.shields.io/badge/React-18-blue)](https://react.dev)
[![License](https://img.shields.io/badge/License-Apache_2.0-orange)](LICENSE)

A 7-layer, multi-agent AI security appliance that discovers, monitors, and actively defends every IoT device on your home network — running entirely locally on a Raspberry Pi 5 or any Linux machine.

</div>

---

## What is SENTINEL?

SENTINEL is a plug-and-play network security appliance that sits **transparently between your router and your devices** as a Layer 2 bridge. It requires zero reconfiguration on your router or devices and gives you full visibility and automated protection over your entire home network.

**What it does automatically:**
- **Network-aware discovery** — identifies which network it is attached to (keyed on the gateway's MAC, not just the subnet) and scopes every device, threat, and firewall rule to that network, so moving between Wi-Fi networks never mixes old devices into the current view
- Discovers every device on the network and builds a risk profile using OUI lookup, Nmap, and NVD CVE data
- Detects anomalous traffic per device using a locally trained LSTM Autoencoder
- Classifies threats against the **MITRE ATT&CK for ICS/IoT** framework using Gemma 4 (local LLM via Ollama — no cloud)
- **Plug-and-play honeypots** — Cowrie and OpenCanary start automatically with the system (bridge or macvlan mode auto-selected from the interface) to trap and study attackers
- **Closed detection→prevention loop** — a detected attacker (from the AI pipeline *or* a honeypot hit) is auto-blocked with a real `nftables` DROP rule, recorded in the Firewall tab, with a **safety guard** that refuses to block the appliance's own host or the gateway
- Enriches attacker IPs with **AlienVault OTX** and **AbuseIPDB** threat intelligence
- Streams everything live to a React dashboard with WebSocket alerts

> Automated blocking is gated by the dashboard's **Auto-Quarantine / Manual Approval** switch: in Manual Approval mode the AI still detects, decides, and alerts, but applies no rule until a human acts.

---

## System Architecture

```
Layer 0  →  IoT Devices (TVs, cameras, bulbs, thermostats, wearables)
                |  [all traffic passes through SENTINEL]
Layer 1  →  Network Capture & Packet Engine
                |  libpcap · nDPI DPI · mDNS/SSDP/ARP passive sniff
Layer 2  →  Device Discovery & Risk Profiler
                |  OUI lookup · Nmap active scan · NVD CVE API · SQLite registry
Layer 3  →  Agentic AI Engine  (LangGraph + Redis pub/sub)
            ├── Anomaly Detector Agent   (LSTM Autoencoder + Isolation Forest)
            ├── Threat Classifier Agent  (Gemma 4 → MITRE ATT&CK JSON output)
            └── Response Planner Agent   (YAML policy → nftables/honeypot actions)
                |
        ┌───────┴───────────┐
Layer 4  →  Deception Layer      Layer 5  →  Firewall & Response Engine
            Cowrie (SSH/Telnet)               eBPF/XDP packet filter
            OpenCanary (HTTP/SMB/FTP)         nftables rule injection
            UPnP honeypot                     Auto quarantine (DHCP + ARP)
            Honeytokens                       VLAN micro-segmentation
                |                                      |
Layer 6  →  Threat Intelligence Bus
                |  STIX/TAXII feeds · AlienVault OTX · AbuseIPDB · IoC enrichment
Layer 7  →  Dashboard & REST API
                React 18 + Vite · FastAPI + Uvicorn · WebSockets
```

**Physical network topology:**
```
[Internet] → [ISP Router] → [SENTINEL eth0 | br0 bridge | eth1] → [Home Switch/AP] → [IoT Devices]
```

---

## Dashboard Screens

| Screen | Controls |
|--------|----------|
| **Dashboard** | Network health gauge, active threat & device counts, live topology map, recent activity feed |
| **Devices** | Full device registry, risk scores, CVE list per device, live port scanner, quarantine toggle |
| **Threats** | Live MITRE ATT&CK threat feed, confidence scores, per-IP OTX + AbuseIPDB intel lookup, **Acknowledge** (persisted), **View Logs / Investigate** evidence panel (indicators, captured credentials, attacker commands) |
| **Firewall** | View/create/toggle/delete nftables rules with **real host enforcement**, per-rule **Enforced / Logical** badge, self-lockout safety guard, auto-quarantine policy, system metrics |
| **Honeypots** | Live attacker sessions, credential capture log, top attacker IPs, block IP → firewall rule, IP intel |
| **Diagnostics** | Health check for all 7 system layers with live status indicators |
| **Logs** | Filterable live logs from all services (level, file, search) |
| **Settings** | LLM model, scan interval, alert thresholds, auto-quarantine, notification preferences |

---

## Tech Stack

### AI & Machine Learning

| Component | Technology |
|-----------|-----------|
| Anomaly detection | LSTM Autoencoder (PyTorch → ONNX Runtime) |
| Cold-start / statistical | Isolation Forest (scikit-learn, unsupervised) |
| Threat classification LLM | **Gemma 4 E4B** via Ollama (dev) / **Gemma 4 E2B** (Pi 5) |
| Agent orchestration | **LangGraph** multi-agent state machines |
| ONNX inference | ONNX Runtime — fast ARM64 + x86_64 |

### Network & Security

| Component | Technology |
|-----------|-----------|
| Packet capture | Scapy + libpcap (AF_PACKET) |
| Deep packet inspection | nDPI — 300+ protocols incl. MQTT, UPnP, Zigbee |
| Device fingerprinting | Nmap + passive mDNS/SSDP/ARP/DHCP/OUI |
| Firewall | nftables + eBPF/XDP (BCC toolkit) |
| Honeypots | Cowrie (SSH/Telnet), OpenCanary (HTTP/SMB/FTP), custom UPnP |
| Threat intel | AlienVault OTX, AbuseIPDB, STIX/TAXII feeds, NVD CVE API |

### Infrastructure

| Component | Technology |
|-----------|-----------|
| Event bus | Redis pub/sub |
| Device registry | SQLite + SQLAlchemy |
| Backend API | FastAPI + Uvicorn (WebSockets) |
| Frontend | React 18 + Vite + Tailwind CSS v4 + Framer Motion |
| Containerisation | Docker + Docker Compose |

---

## Getting Started

### Prerequisites

- **Linux** (tested on Kali Linux ARM64, Ubuntu 22.04) or WSL2
- Python 3.11+
- Node.js 18+
- Redis — `sudo apt install redis`
- Ollama — install from [ollama.com](https://ollama.com), then `ollama pull gemma4:e4b`

### 1. Clone and set up Python environment

```bash
git clone https://github.com/sharma19d/SENTINAL.git
cd SENTINAL

python3 -m venv env
source env/bin/activate
pip install -r requirements.txt
```

### 2. Configure environment

```bash
cp .env.example .env
nano .env
```

Key settings to fill in:

```env
# Network interface for live packet capture
CAPTURE_INTERFACE=wlan0        # use 'br0' on Pi 5 in bridge mode

# Ollama / LLM
OLLAMA_BASE_URL=http://localhost:11434
LLM_MODEL=gemma4:e4b           # use gemma4:e2b on Pi 5

# Threat Intel API keys (free — highly recommended)
NVD_API_KEY=your_key_here
OTX_API_KEY=your_key_here
ABUSEIPDB_API_KEY=your_key_here
```

Free API keys:
- **NVD (CVE data):** https://nvd.nist.gov/developers/request-an-api-key
- **AlienVault OTX:** https://otx.alienvault.com/
- **AbuseIPDB:** https://www.abuseipdb.com/api

### 3. Install dashboard dependencies

```bash
cd dashboard
npm install
cd ..
```

### 4. Start the full system

```bash
bash run.sh
```

This starts every service in order:

```
[1/10] Redis
[2/10] FastAPI backend          → http://localhost:8000
[3/10] Packet capture (sudo)    → wlan0
[4/10] Discovery agent (Layer 2 — writes devices into the registry)
[5/10] Honeypots (Layer 4 — Cowrie + OpenCanary, auto bridge/macvlan)
[6/10] Anomaly detection worker
[7/10] Threat classifier (Gemma)
[8/10] Response planner (LangGraph) — applies auto-blocks
[9/10] Honeypot monitor (turns attacker sessions into threats + blocks)
[10/10] React dashboard         → http://localhost:3000
```

> Run with `sudo bash run.sh` (or ensure the process can escalate): live packet
> capture and real `nftables` enforcement both require root.

Open **http://localhost:3000** to access the dashboard.
API docs (Swagger UI) at **http://localhost:8000/docs**

### 5. Stop the system

```bash
bash stop.sh
```

---

## Quick Test Without Live Capture

To populate the dashboard with realistic demo data (devices, threats, honeypot sessions, firewall rules) without running live capture:

```bash
python seed_data.py
```

To replay a PCAP file through the capture engine:

```bash
source env/bin/activate
python -m sentinel.core.capture.main --pcap your_file.pcap --no-redis
```

---

## Log Files

| File | Contents |
|------|----------|
| `logs/api.log` | FastAPI backend |
| `logs/capture.log` | Layer 1 — live packet capture |
| `logs/discovery.log` | Layer 2 — device discovery |
| `logs/anomaly.log` | Agent 1 — LSTM anomaly detection |
| `logs/classifier.log` | Agent 2 — Gemma threat classification |
| `logs/responder.log` | Agent 3 — LangGraph response planner (auto-block) |
| `logs/honeypot.log` | Honeypot monitor — sessions → threats → blocks |
| `logs/dashboard.log` | React/Vite dev server |

---

## Redis Event Channels

All agents communicate over Redis pub/sub:

| Channel | Published by | Content |
|---------|-------------|---------|
| `sentinel:flows` | Layer 1 capture | Flow lifecycle events |
| `sentinel:packets` | Layer 1 capture | Raw packet metadata |
| `sentinel:discovery` | Layer 1 capture | Device seen events (ARP/mDNS/DHCP) |
| `sentinel:anomaly` | Anomaly Agent | Anomaly score + device_id |
| `sentinel:threat` | Classifier Agent, Honeypot Monitor | MITRE ATT&CK JSON threat events |
| `sentinel:actions` | Response Agent, Honeypot Monitor | Enforcement actions (block/quarantine) with applied-rule status |
| `sentinel:alerts` | Response Agent | Alerts + pending human-approval notices |

---

## Raspberry Pi 5 Deployment

SENTINEL is **designed and targeted for the Raspberry Pi 5**. Development and
testing to date have been on an **ARM64 laptop (Kali Linux)**; the codebase is
already ARM64-native, so no porting is required. Performance and inline
enforcement have **not yet been validated on Pi 5 hardware** — the items below
are the deployment changes, and the notes call out what still needs on-hardware
verification.

| What | Dev (laptop, ARM64) | Pi 5 |
|------|---------------------|------|
| Capture interface | `wlan0` (managed Wi-Fi) | `br0` (inline Ethernet bridge) |
| LLM model | `gemma4:e4b` | `gemma4:e2b` — **latency/RAM to be measured on-device** |
| Honeypot mode | `bridge` (Wi-Fi can't do macvlan) | `macvlan` (honeypots get their own LAN IPs) |
| Real internet-cutoff blocking | host-directed only (laptop is not inline) | full forward-chain drops (Pi sits inline) |
| Docker | Same images | Same (ARM64 auto-pulled) |

> **Evaluation note.** Because no Pi 5 hardware is currently available, benchmarks
> are produced by dataset/PCAP replay under cgroup-constrained resources that
> approximate the Pi 5, **not** by measuring on the device. Results are reported
> as Pi-5-*targeted* under stated constraints, and laptop/cloud ARM performance
> is **not** presented as equivalent to a Pi 5.

**Pi 5 bridge setup (netplan):**
```yaml
# /etc/netplan/99-sentinel-bridge.yaml
network:
  version: 2
  ethernets:
    eth0: {}
    eth1: {}
  bridges:
    br0:
      interfaces: [eth0, eth1]
      dhcp4: true
```

Then update `.env`:
```env
CAPTURE_INTERFACE=br0
LLM_MODEL=gemma4:e2b
```

---

## Project Structure

```
SENTINAL/
├── sentinel/                     # Core Python system
│   ├── config/
│   │   └── settings.py           # Centralised Pydantic settings
│   ├── core/
│   │   ├── capture/              # Layer 1 — packet capture & flow parsing
│   │   │   ├── main.py           # CLI entry point
│   │   │   ├── sniffer.py        # Scapy AsyncSniffer
│   │   │   ├── flow_parser.py    # 5-tuple flow aggregation
│   │   │   ├── metadata_extractor.py  # DNS/TLS/HTTP/ARP/mDNS
│   │   │   └── redis_publisher.py
│   │   ├── fingerprinting/       # Layer 2 — device discovery & CVE
│   │   │   ├── discovery.py      # Discovery agent
│   │   │   ├── registry.py       # SQLite device registry (SQLAlchemy)
│   │   │   ├── cve.py            # NVD CVE scanner
│   │   │   ├── oui.py            # OUI vendor lookup
│   │   │   └── scanner.py        # Nmap active scanner
│   │   ├── firewall/             # Layer 5 — enforcement
│   │   │   ├── host_firewall.py  # Real nftables block/unblock + safety guard
│   │   │   ├── nftables_manager.py
│   │   │   ├── quarantine.py
│   │   │   └── engine.py         # Response engine (Redis actions → nft/XDP)
│   │   └── network_identity.py   # Gateway-MAC network fingerprint
│   └── agents/
│       ├── anomaly/              # Layer 3 — LSTM + Isolation Forest
│       │   ├── worker.py         # Redis consumer
│       │   ├── inference.py      # ONNX Runtime LSTM inference
│       │   └── kitsune.py        # Feature extraction (KitNET-style)
│       ├── classifier/           # Layer 3 — Gemma threat classifier
│       │   ├── worker.py         # Redis consumer
│       │   └── gemma_client.py   # Ollama API client
│       ├── responder/            # Layer 3 — LangGraph response planner
│       │   ├── worker.py         # Redis consumer — applies auto-blocks
│       │   ├── graph.py          # LangGraph agent graph
│       │   └── policy.py         # YAML policy loader
│       └── honeypot/             # Layer 4 → pipeline bridge
│           └── worker.py         # Cowrie sessions → threats → auto-block
├── api/
│   └── main.py                   # FastAPI app — all Layer 7 endpoints
├── dashboard/                    # React + Vite frontend
│   └── src/
│       ├── screens/              # Dashboard, Devices, Threats, Firewall...
│       ├── layout/               # TopNavBar, SideNavBar, Footer
│       └── lib/
│           └── api.ts            # Typed API client
├── deception/                    # Cowrie & OpenCanary configs (Layer 4)
├── data/                         # SQLite DB + OUI lookup JSON
├── logs/                         # Runtime logs (gitignored)
├── docker-compose.yml            # Redis + discovery
├── requirements.txt              # All Python dependencies
├── run.sh                        # Full system startup (10 steps)
├── start_honeypots.sh            # Layer 4 honeypot deployment (auto bridge/macvlan)
├── stop.sh                       # Full system shutdown
├── attack_test.sh                # End-to-end attack simulation + verification
└── seed_data.py                  # Demo data generator
```

---

## Layer-by-Layer Reference

### Layer 1 — Packet Capture CLI

```bash
# Live capture on wlan0
sudo python -m sentinel.core.capture.main -i wlan0

# Replay PCAP (no sudo, no Redis needed)
python -m sentinel.core.capture.main --pcap test.pcap --no-redis

# List available interfaces
sudo python -m sentinel.core.capture.main --list-interfaces
```

| Flag | Description |
|------|-------------|
| `-i, --interface` | Network interface (default: `wlan0`) |
| `-f, --filter` | BPF filter expression |
| `--pcap FILE` | Replay PCAP instead of live capture |
| `--no-redis` | Disable Redis publishing |
| `--no-dpi` | Disable NFStream DPI |
| `-v, --verbose` | Debug logging |

### Layer 2 — Device Discovery

```bash
python -m sentinel.core.fingerprinting.discovery
```

Passively monitors Redis for ARP/mDNS/DHCP/SSDP events, fingerprints each new device (OUI lookup + Nmap), fetches CVEs from NVD, and writes everything to the SQLite registry.

### Layer 3 — AI Agents

```bash
# Anomaly detection
python -m sentinel.agents.anomaly.worker

# Threat classification
python -m sentinel.agents.classifier.worker

# Response planning
python -m sentinel.agents.responder.worker
```

### Layer 7 — API

```bash
PYTHONPATH=. uvicorn api.main:app --host 0.0.0.0 --port 8000
```

Key endpoints:

| Method | Path | Description |
|--------|------|-------------|
| GET | `/api/health` | System health check |
| GET | `/api/dashboard/stats` | Dashboard summary stats |
| GET | `/api/devices` | All registered devices |
| POST | `/api/devices/{id}/quarantine` | Toggle device quarantine |
| GET | `/api/network/current` | Currently attached network (gateway-MAC identity) |
| GET | `/api/detection/status` | Anomaly pipeline warm-up / active state |
| GET | `/api/threats` | Live threat feed (scoped to current network) |
| GET | `/api/threats/{id}` | Full event evidence (indicators, credentials, commands) |
| POST | `/api/threats/{id}/acknowledge` | Mark a threat acknowledged |
| GET | `/api/firewall/rules` | Active rules + per-rule `enforced` flag |
| POST | `/api/firewall/rules` | Create rule — applies real `nftables` DROP (guarded) |
| DELETE | `/api/firewall/rules/{id}` | Unblock — removes exactly that host rule |
| GET | `/api/honeypots/sessions` | Cowrie session log |
| GET | `/api/intel/{ip}` | OTX + AbuseIPDB enrichment |
| GET | `/api/diagnostics` | Full system health check |
| WS | `/ws/events` | WebSocket live event stream |

Full interactive docs: **http://localhost:8000/docs**

<img width="1464" height="923" alt="Screenshot 2026-05-22 at 9 55 56 AM" src="https://github.com/user-attachments/assets/e53dc7c1-eb45-4985-8f1e-4df320389aac" />
<img width="1464" height="923" alt="Screenshot 2026-05-22 at 9 56 07 AM" src="https://github.com/user-attachments/assets/895332ff-58d0-40f2-8fe9-aed77147ded1" />
<img width="1464" height="923" alt="Screenshot 2026-05-22 at 9 56 13 AM" src="https://github.com/user-attachments/assets/54e39e10-f69f-4728-b8ce-f84e79caed7b" />
<img width="1464" height="923" alt="Screenshot 2026-05-22 at 9 56 18 AM" src="https://github.com/user-attachments/assets/ce898248-9124-43c4-aa10-279cdf9fa1bf" />
<img width="1464" height="923" alt="Screenshot 2026-05-22 at 9 56 25 AM" src="https://github.com/user-attachments/assets/7aec4bad-181b-4ee0-a50f-6ed92296196a" />
<img width="1464" height="923" alt="Screenshot 2026-05-22 at 9 56 34 AM" src="https://github.com/user-attachments/assets/97a93979-e785-4d53-a478-47121d32235d" />
<img width="1464" height="923" alt="Screenshot 2026-05-22 at 9 56 51 AM" src="https://github.com/user-attachments/assets/d7885881-5b52-4c43-903d-2b144fba1dc5" />
<img width="1464" height="923" alt="Screenshot 2026-05-22 at 9 55 45 AM" src="https://github.com/user-attachments/assets/14cf2ed5-f04d-4098-9c5a-fb72d480d002" />
<img width="1464" height="923" alt="Screenshot 2026-05-22 at 9 55 33 AM" src="https://github.com/user-attachments/assets/b2f5e6a4-aa52-4dfc-a340-adfa546375ae" />
<img width="1464" height="923" alt="Screenshot 2026-05-22 at 9 55 40 AM" src="https://github.com/user-attachments/assets/ea94e53b-1420-41bf-a276-583be0399b0c" />


---

## License

Apache 2.0 — see [LICENSE](LICENSE)

---

*Built by Vinay (sharma19d) · Security Engineer · CTF Player · Final Year Project 2026*
