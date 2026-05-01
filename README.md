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
docker run -d --name sentinel-redis -p 6379:6379 redis:alpine

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
│   Sniffer   │───▶│ Flow Tracker │───▶│ Redis Pub/Sub │
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
| `sentinel:flows` | Flow lifecycle events (new/update/end) |
| `sentinel:packets` | Raw packet metadata (high frequency) |
| `sentinel:discovery` | Device discovery (ARP/mDNS/SSDP/DHCP) |
| `sentinel:stats` | Capture engine statistics |

### Project Structure

```
sentinel/
  core/
    capture/
      main.py                # CLI entry point
      sniffer.py             # Scapy AsyncSniffer engine
      flow_tracker.py        # 5-tuple flow aggregation
      protocol_analyzer.py   # NFStream DPI + port inference
      metadata_extractor.py  # DNS/TLS/HTTP/ARP/mDNS/SSDP/DHCP
      redis_publisher.py     # Redis pub/sub publisher
      models.py              # Pydantic data models
      config.py              # Configuration management
      utils.py               # MAC vendor lookup, helpers
  data/
    oui_lookup.json          # IEEE OUI vendor database
```

## License

Apache 2.0
