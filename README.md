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
- Discovers every device on the network and builds a risk profile using OUI lookup, Nmap, and NVD CVE data
- Detects anomalous traffic per device using a locally trained LSTM Autoencoder
- Classifies threats against the **MITRE ATT&CK for ICS/IoT** framework using Gemma 4 (local LLM via Ollama — no cloud)
- Deploys Cowrie and OpenCanary honeypots to trap and study attackers
- Blocks threats in real time via nftables rules and eBPF/XDP (sub-millisecond latency)
- Enriches attacker IPs with **AlienVault OTX** and **AbuseIPDB** threat intelligence
- Streams everything live to a React dashboard with WebSocket alerts

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
| **Threats** | Live MITRE ATT&CK threat feed, confidence scores, per-IP OTX + AbuseIPDB intel lookup |
| **Firewall** | View/create/toggle/delete nftables rules, auto-quarantine policy, system metrics |
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

This starts all 7 layers in order:

```
[1/7] Redis
[2/7] FastAPI backend          → http://localhost:8000
[3/7] Packet capture (sudo)   → wlan0
[4/7] Anomaly detection worker
[5/7] Threat classifier (Gemma)
[6/7] Response planner (LangGraph)
[7/7] React dashboard          → http://localhost:3000
```

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
| `logs/anomaly.log` | Agent 1 — LSTM anomaly detection |
| `logs/classifier.log` | Agent 2 — Gemma threat classification |
| `logs/responder.log` | Agent 3 — LangGraph response planner |
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
| `sentinel:threat` | Classifier Agent | MITRE ATT&CK JSON threat events |
| `sentinel:actions` | Response Agent | nftables / honeypot actions |

---

## Raspberry Pi 5 Deployment

SENTINEL is designed to run identically on Pi 5. Only 4 things change:

| What | Dev (PC) | Pi 5 |
|------|----------|------|
| Capture interface | `wlan0` | `br0` (bridge) |
| LLM model | `gemma4:e4b` | `gemma4:e2b` (~2GB RAM, 7.6 tok/s) |
| llama.cpp | Pre-built x86_64 | Recompile for ARM64 |
| Docker | Same images | Same (ARM64 auto-pulled) |

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
│   │   └── fingerprinting/       # Layer 2 — device discovery & CVE
│   │       ├── discovery.py      # Discovery agent
│   │       ├── registry.py       # SQLite device registry (SQLAlchemy)
│   │       ├── cve.py            # NVD CVE scanner
│   │       ├── oui.py            # OUI vendor lookup
│   │       └── scanner.py        # Nmap active scanner
│   └── agents/
│       ├── anomaly/              # Layer 3 — LSTM + Isolation Forest
│       │   ├── worker.py         # Redis consumer
│       │   ├── inference.py      # ONNX Runtime LSTM inference
│       │   └── kitsune.py        # Feature extraction (KitNET-style)
│       ├── classifier/           # Layer 3 — Gemma threat classifier
│       │   ├── worker.py         # Redis consumer
│       │   └── gemma_client.py   # Ollama API client
│       └── responder/            # Layer 3 — LangGraph response planner
│           ├── worker.py         # Redis consumer
│           ├── graph.py          # LangGraph agent graph
│           └── policy.py         # YAML policy loader
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
├── run.sh                        # Full system startup
├── stop.sh                       # Full system shutdown
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
| GET | `/api/threats` | Live threat feed |
| GET | `/api/firewall/rules` | Active nftables rules |
| POST | `/api/firewall/rules` | Create new rule |
| GET | `/api/honeypots/sessions` | Cowrie session log |
| GET | `/api/intel/{ip}` | OTX + AbuseIPDB enrichment |
| GET | `/api/diagnostics` | Full system health check |
| WS | `/ws/events` | WebSocket live event stream |

Full interactive docs: **http://localhost:8000/docs**

---

## License

Apache 2.0 — see [LICENSE](LICENSE)

---

*Built by Vinay (sharma19d) · Security Engineer · CTF Player · Final Year Project 2026*
