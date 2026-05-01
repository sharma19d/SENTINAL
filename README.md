# SENTINEL — Agentic AI-Powered IoT Security System

> Final Year Project — charon19d — April 2026

## Overview

SENTINEL is a consumer-grade, plug-and-play network security appliance powered by an agentic AI system. It sits inline between a home ISP router and the internal network, acting as a transparent Layer 2 bridge with full visibility into all home network traffic.

## Layer 1 — Network Capture & Packet Engine

The currently implemented layer. Captures raw network traffic, classifies protocols via DPI, tracks network flows, and publishes structured metadata to Redis.

### Quick Start (Kali Linux)

```bash
# 1. Install dependencies
pip install -r requirements.txt

# 2. Copy and edit environment config
cp .env.example .env

# 3. Start Redis (via Docker)
docker-compose up -d

# 4. List available interfaces
sudo python -m sentinel.core.capture.main --list-interfaces

# 5. Start live capture on wlan0
sudo python -m sentinel.core.capture.main -i wlan0

# 6. Or replay a PCAP file (no sudo needed)
python -m sentinel.core.capture.main --pcap test.pcap --no-redis
```

### CLI Options

| Flag | Description |
|---|---|
| `-i, --interface` | Network interface (default: wlan0) |
| `-f, --filter` | BPF filter expression |
| `--pcap FILE` | Replay PCAP file instead of live capture |
| `--no-redis` | Run without Redis |
| `--no-dpi` | Disable NFStream DPI |
| `-v, --verbose` | Debug logging |
| `--list-interfaces` | List interfaces and exit |

### Architecture

```
┌─────────────┐    ┌──────────────┐    ┌───────────────┐
│   Sniffer   │───▶│ Flow Parser  │───▶│ Redis Pub/Sub │
│  (Scapy)    │    │  (5-tuple)   │    │               │
└─────────────┘    └──────────────┘    └───────────────┘
      │                  │
      ▼                  ▼
┌─────────────┐    ┌──────────────┐
│  Metadata   │    │  Protocol    │
│  Extractor  │    │  Analyzer    │
│  DNS/TLS/   │    │  (NFStream)  │
│  HTTP/ARP   │    │              │
└─────────────┘    └──────────────┘
```

### Redis Channels

| Channel | Content |
|---|---|
| `capture:flows` | Flow lifecycle events (new/update/end) |
| `capture:packets` | Raw packet metadata (high frequency) |
| `capture:discovery` | Device discovery (ARP/mDNS/SSDP/DHCP) |
| `capture:stats` | Capture engine statistics |

### Project Structure

```
sentinel/
  config/
    settings.py              # Centralized configuration
  core/
    capture/
      main.py                # CLI entry point
      sniffer.py             # Scapy AsyncSniffer engine
      flow_parser.py         # 5-tuple flow aggregation
      protocol_analyzer.py   # NFStream DPI + port inference
      metadata_extractor.py  # DNS/TLS/HTTP/ARP/mDNS/SSDP/DHCP
      redis_publisher.py     # Redis pub/sub publisher
      models.py              # Pydantic data models
      config.py              # Layer 1 specific config
      utils.py               # MAC vendor lookup, helpers
    fingerprinting/
      discovery.py           # Layer 2 Discovery Agent
      registry.py            # SQLite Device Registry
      cve.py                 # NVD CVE Scanner
      oui.py                 # OUI Vendor Lookup
      scanner.py             # Nmap Active Scanner
  data/
    oui_lookup.json          # IEEE OUI vendor database
```

## Layer 2 — Device Discovery & Risk Profiler

Automatically discovers and risk-profiles every device on the home network. Uses passive fingerprinting (mDNS, SSDP, DHCP, ARP) and active scanning (Nmap) to identify vendors and vulnerabilities.

### Quick Start

```bash
# Start the Discovery Agent
python -m sentinel.core.fingerprinting.discovery
```

## License

Apache 2.0
