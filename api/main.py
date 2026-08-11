"""
SENTINEL — FastAPI Backend

Provides REST endpoints and WebSocket streams for the Dashboard.
"""

import hashlib
import ipaddress
import json
import asyncio
import os
import glob
import re
import socket
import subprocess
import time
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta
from pathlib import Path
from typing import Optional

import redis.asyncio as redis
from redis.exceptions import RedisError
from sqlalchemy.exc import SQLAlchemyError
from fastapi import FastAPI, HTTPException, Query, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
import structlog

from sentinel.config.settings import settings as app_settings
from sentinel.core.fingerprinting.registry import DeviceRegistry
from sentinel.core.firewall.host_firewall import HostFirewall
from sentinel.core.network_identity import detect_current_network, ip_in_subnet
from intel.bus import IntelBus

logger = structlog.get_logger(__name__)

app = FastAPI(title="SENTINEL API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

registry = DeviceRegistry(db_url=app_settings.db_url)
host_firewall = HostFirewall()
intel_bus = IntelBus()
redis_client = redis.Redis(
    host=app_settings.redis_host,
    port=app_settings.redis_port,
    decode_responses=True
)

# ── Settings file ────────────────────────────────────────────────
SETTINGS_FILE = Path("data/sentinel_ui_settings.json")

DEFAULT_UI_SETTINGS = {
    "anomaly_threshold": 0.75,
    "threat_confidence_cutoff": 0.70,
    "auto_quarantine": True,
    "auto_honeypot": False,
    "auto_block_honeypot": True,
    "min_severity_alert": 7,
    "alert_enabled": True,
    "capture_interface": app_settings.capture_interface,
    "monitored_subnets": "192.168.0.0/24",
    "scan_interval_minutes": 5,
}

def load_ui_settings() -> dict:
    if SETTINGS_FILE.exists():
        try:
            return json.loads(SETTINGS_FILE.read_text())
        except Exception:
            pass
    return DEFAULT_UI_SETTINGS.copy()

def save_ui_settings(data: dict):
    SETTINGS_FILE.parent.mkdir(parents=True, exist_ok=True)
    merged = {**DEFAULT_UI_SETTINGS, **data}
    SETTINGS_FILE.write_text(json.dumps(merged, indent=2))

# ── Cowrie log parser ─────────────────────────────────────────────
COWRIE_LOG_DIR = Path("deception/cowrie/log")
OPENCANARY_LOG = Path("deception/opencanary/opencanary.log")
HONEYPOT_CONTAINERS = {"cowrie": "sentinel-cowrie", "opencanary": "sentinel-opencanary"}
LOGS_DIR = Path("logs")
LOG_LINE_RE = re.compile(r"^(?P<timestamp>[\d\-:T.Z+ ]+)\s+\[(?P<level>[^\]]+)\]\s+(?P<message>.*)$")
ANSI_ESCAPE_RE = re.compile(r"\x1B\[[0-?]*[ -/]*[@-~]")

def container_running(name: str) -> Optional[bool]:
    """
    Whether a honeypot container is running.

    Returns None when Docker cannot be queried at all (not installed, or no
    permission) — that is genuinely "unknown", and must not be reported as
    running. Honeypots sit on a macvlan network the host usually cannot
    reach directly, so a TCP probe from here is not a reliable liveness
    check; container state is.
    """
    try:
        result = subprocess.run(
            ["docker", "inspect", "-f", "{{.State.Running}}", name],
            capture_output=True, text=True, timeout=3, check=False,
        )
        if result.returncode != 0:
            # Container absent — Docker answered, so this is a real "no".
            if "No such object" in (result.stderr or ""):
                return False
            return None
        return result.stdout.strip() == "true"
    except (subprocess.TimeoutExpired, FileNotFoundError, OSError):
        return None


def honeypot_state(container: str, has_activity: bool) -> str:
    """
    Report honeypot state honestly.

    ONLINE  — container confirmed running
    STANDBY — deployed and has produced activity, but not currently running
    OFFLINE — confirmed not running
    UNKNOWN — Docker could not be queried; state cannot be asserted
    """
    running = container_running(container)
    if running is True:
        return "ONLINE"
    if running is False:
        return "STANDBY" if has_activity else "OFFLINE"
    return "STANDBY" if has_activity else "UNKNOWN"


def _looks_like_ip(value: str) -> bool:
    try:
        ipaddress.ip_address(value)
        return True
    except ValueError:
        return False


def parse_cowrie_sessions() -> list[dict]:
    sessions: dict[str, dict] = {}
    log_files = sorted(glob.glob(str(COWRIE_LOG_DIR / "cowrie.json*")), reverse=True)

    for log_file in log_files[:5]:  # last 5 log files max
        try:
            with open(log_file) as f:
                for line in f:
                    line = line.strip()
                    if not line:
                        continue
                    try:
                        evt = json.loads(line)
                    except json.JSONDecodeError:
                        continue

                    sid = evt.get("session", "")
                    if not sid:
                        continue

                    if sid not in sessions:
                        sessions[sid] = {
                            "session_id": sid,
                            "src_ip": evt.get("src_ip", "unknown"),
                            "start_time": evt.get("timestamp", ""),
                            "end_time": None,
                            "duration": None,
                            "service": "SSH",
                            "login_attempts": [],
                            "commands": [],
                            "success": False,
                        }

                    eid = evt.get("eventid", "")
                    if eid == "cowrie.session.connect":
                        sessions[sid]["src_ip"] = evt.get("src_ip", sessions[sid]["src_ip"])
                        sessions[sid]["start_time"] = evt.get("timestamp", sessions[sid]["start_time"])
                    elif eid in ("cowrie.login.failed", "cowrie.login.success"):
                        sessions[sid]["login_attempts"].append({
                            "username": evt.get("username", ""),
                            "password": evt.get("password", ""),
                            "success": eid == "cowrie.login.success",
                        })
                        if eid == "cowrie.login.success":
                            sessions[sid]["success"] = True
                    elif eid == "cowrie.command.input":
                        sessions[sid]["commands"].append(evt.get("input", ""))
                    elif eid == "cowrie.session.closed":
                        sessions[sid]["end_time"] = evt.get("timestamp", "")
                        sessions[sid]["duration"] = evt.get("duration", None)
        except Exception:
            continue

    result = sorted(sessions.values(), key=lambda s: s["start_time"], reverse=True)
    return result[:100]


def _strip_ansi(value: str) -> str:
    return ANSI_ESCAPE_RE.sub("", value)


def _parse_log_line(line: str, line_no: int) -> dict:
    cleaned = _strip_ansi(line.rstrip("\n"))
    if not cleaned:
        return {"line_no": line_no, "timestamp": None, "level": "info", "message": "", "raw": ""}

    match = LOG_LINE_RE.match(cleaned)
    if not match:
        return {"line_no": line_no, "timestamp": None, "level": "info", "message": cleaned, "raw": cleaned}

    return {
        "line_no": line_no,
        "timestamp": match.group("timestamp").strip() or None,
        "level": match.group("level").strip().lower() or "info",
        "message": match.group("message").strip(),
        "raw": cleaned,
    }

# ── System metrics ─────────────────────────────────────────────────
def _read_cpu_counters() -> tuple[int, int]:
    with open("/proc/stat") as f:
        parts = f.readline().split()
    values = [int(x) for x in parts[1:]]
    idle = values[3] + (values[4] if len(values) > 4 else 0)
    total = sum(values)
    return idle, total


async def read_cpu_percent() -> float:
    try:
        idle1, total1 = _read_cpu_counters()
        await asyncio.sleep(0.12)
        idle2, total2 = _read_cpu_counters()
        idle_delta = idle2 - idle1
        total_delta = total2 - total1
        if total_delta <= 0:
            return 0.0
        busy_pct = (1 - (idle_delta / total_delta)) * 100
        return round(max(0.0, min(100.0, busy_pct)), 1)
    except Exception:
        return 0.0

def read_mem_info() -> dict:
    try:
        info = {}
        with open("/proc/meminfo") as f:
            for line in f:
                k, v = line.split(":")
                info[k.strip()] = int(v.split()[0])
        total_kb = info.get("MemTotal", 0)
        avail_kb = info.get("MemAvailable", 0)
        used_kb = max(total_kb - avail_kb, 0)
        total_gb = round(total_kb / 1024 / 1024, 2)
        used_gb = round(used_kb / 1024 / 1024, 2)
        pct = round((used_kb / total_kb) * 100, 2) if total_kb else 0.0
        return {"total_gb": total_gb, "used_gb": used_gb, "percent": pct}
    except Exception:
        return {"total_gb": 0, "used_gb": 0, "percent": 0}

# ── Port scanning helpers ──────────────────────────────────────────
COMMON_IOT_PORTS = [
    21, 22, 23, 25, 53, 80, 110, 139, 443, 445,
    554, 993, 995, 1883, 3306, 3389, 5900, 8080, 8443, 8554,
]

_scan_executor = ThreadPoolExecutor(max_workers=20, thread_name_prefix="port-scan")

def _tcp_check(ip: str, port: int, timeout: float = 0.5) -> bool:
    try:
        with socket.create_connection((ip, port), timeout=timeout):
            return True
    except (socket.timeout, ConnectionRefusedError, OSError):
        return False

async def socket_scan(ip: str, ports: list[int] = COMMON_IOT_PORTS) -> list[int]:
    loop = asyncio.get_event_loop()
    results = await asyncio.gather(
        *[loop.run_in_executor(_scan_executor, _tcp_check, ip, p) for p in ports]
    )
    return [port for port, is_open in zip(ports, results) if is_open]

def normalize_open_ports(raw: list) -> list[int]:
    result = []
    for p in raw:
        if isinstance(p, int):
            result.append(p)
        elif isinstance(p, dict) and isinstance(p.get("port"), int):
            result.append(p["port"])
    return result


# A device is considered online if it has been seen (passively or via the
# active ARP sweep in Layer 1) within this window. The ARP sweep runs every
# ~45s by default, so a genuinely-connected device's last_seen is refreshed
# well within this threshold; a device that actually disconnected falls
# outside it and is shown as offline instead of lingering forever.
DEVICE_ONLINE_THRESHOLD = timedelta(minutes=5)

# ── Current network ───────────────────────────────────────────────
# Detection shells out to `ip`, so it is cached briefly rather than run on
# every request. The TTL is short because the appliance can be moved to a
# different network at any moment and the dashboard must follow it.
_NETWORK_CACHE_TTL = 15.0
_network_cache: dict = {"identity": None, "checked_at": 0.0}


def current_network():
    """Network the appliance is attached to right now, or None if no uplink."""
    now = time.monotonic()
    if (now - _network_cache["checked_at"]) > _NETWORK_CACHE_TTL:
        identity = detect_current_network()
        previous = _network_cache["identity"]
        if identity and (previous is None or identity.network_id != previous.network_id):
            logger.info(
                "api_network_changed",
                network_id=identity.network_id,
                subnet=identity.subnet,
            )
            try:
                registry.record_network(identity)
            except SQLAlchemyError as e:
                logger.error("record_network_failed", error=str(e))
        _network_cache["identity"] = identity
        _network_cache["checked_at"] = now
    return _network_cache["identity"]


def current_network_id() -> Optional[str]:
    identity = current_network()
    return identity.network_id if identity else None

# An unresolved threat older than this is history, not an active incident.
# Without a window, test/seed events from months ago are still reported as
# "active threats" forever because nothing ever marks them resolved.
THREAT_ACTIVE_WINDOW = timedelta(hours=24)


def compute_is_online(last_seen: Optional[datetime]) -> bool:
    if not last_seen:
        return False
    return (datetime.utcnow() - last_seen) <= DEVICE_ONLINE_THRESHOLD


# ── Pydantic request models ────────────────────────────────────────
class FirewallRuleCreate(BaseModel):
    protocol: str
    target: str
    action: str
    description: Optional[str] = ""

class NodeDeployRequest(BaseModel):
    ip: str
    label: str
    mac: Optional[str] = None

class SettingsUpdate(BaseModel):
    anomaly_threshold: Optional[float] = None
    threat_confidence_cutoff: Optional[float] = None
    auto_quarantine: Optional[bool] = None
    auto_honeypot: Optional[bool] = None
    auto_block_honeypot: Optional[bool] = None
    min_severity_alert: Optional[int] = None
    alert_enabled: Optional[bool] = None
    capture_interface: Optional[str] = None
    monitored_subnets: Optional[str] = None
    scan_interval_minutes: Optional[int] = None


# ═══════════════════════════════════════════════════════════════════
# Endpoints
# ═══════════════════════════════════════════════════════════════════

@app.get("/api/health")
async def health():
    return {"status": "online", "version": "1.0.0"}


# ── Dashboard ─────────────────────────────────────────────────────

@app.get("/api/dashboard/stats")
async def dashboard_stats():
    net_id = current_network_id()
    # Scope to the current network first: hardware from a network we are no
    # longer attached to must not be counted at all.
    all_devices = registry.get_devices_for_network(net_id)
    # Then to devices seen recently — the rest are on this network but offline.
    devices = [d for d in all_devices if compute_is_online(d.last_seen)]

    recent_threats = registry.get_recent_threats(limit=100, network_id=net_id)
    threat_cutoff = datetime.utcnow() - THREAT_ACTIVE_WINDOW
    active_threats = [
        t for t in recent_threats
        if not t.resolved and t.timestamp and t.timestamp >= threat_cutoff
    ]
    quarantined = [d for d in devices if d.is_quarantined]
    critical_devices = [d for d in devices if (d.risk_score or 0) >= 7.0]

    activity = []
    for t in recent_threats[:10]:
        ts = t.timestamp.isoformat() if t.timestamp else ""
        activity.append({
            "id": t.event_id,
            "type": "threat",
            "message": t.summary or "Threat detected",
            "detail": t.tactic or "",
            "severity": t.severity or 0,
            "timestamp": ts,
        })

    return {
        "total_devices": len(devices),
        "known_devices": len(all_devices),
        "active_threats": len(active_threats),
        "quarantined": len(quarantined),
        "critical_devices": len(critical_devices),
        "recent_activity": activity,
    }


@app.get("/api/notifications")
async def notifications(limit: int = Query(8, ge=1, le=50)):
    events = registry.get_recent_threats(limit=100, network_id=current_network_id())
    items = []
    unread = 0

    for event in events[:limit]:
        is_unread = not bool(event.resolved)
        if is_unread:
            unread += 1

        items.append({
            "id": event.event_id,
            "type": "threat",
            "title": event.summary or "Threat detected",
            "detail": event.tactic or event.action_taken or "Security event",
            "severity": event.severity or 0,
            "timestamp": event.timestamp.isoformat() if event.timestamp else None,
            "unread": is_unread,
        })

    return {
        "total": len(items),
        "unread": unread,
        "items": items,
    }


@app.get("/api/activity/pulse")
async def activity_pulse():
    cpu = await read_cpu_percent()
    mem = read_mem_info()
    net_id = current_network_id()
    devices = registry.get_devices_for_network(net_id)
    recent_threats = registry.get_recent_threats(limit=50, network_id=net_id)
    active_threats = [t for t in recent_threats if not t.resolved]
    recent_events = [
        {
            "id": t.event_id,
            "message": t.summary or "Threat detected",
            "severity": t.severity or 0,
            "timestamp": t.timestamp.isoformat() if t.timestamp else None,
        }
        for t in recent_threats[:5]
    ]

    redis_ok = False
    try:
        redis_ok = bool(await redis_client.ping())
    except RedisError:
        redis_ok = False

    cowrie_logs = list(COWRIE_LOG_DIR.glob("cowrie.json*")) if COWRIE_LOG_DIR.exists() else []
    cowrie_ok = len(cowrie_logs) > 0

    services = [
        {"name": "api", "status": "healthy"},
        {"name": "redis", "status": "healthy" if redis_ok else "critical"},
        {"name": "cowrie", "status": "healthy" if cowrie_ok else "degraded"},
    ]

    if any(s["status"] == "critical" for s in services):
        overall = "critical"
    elif any(s["status"] == "degraded" for s in services):
        overall = "degraded"
    else:
        overall = "healthy"

    return {
        "overall_status": overall,
        "metrics": {
            "cpu_percent": cpu,
            "memory_percent": mem.get("percent", 0),
            "total_devices": len(devices),
            "active_threats": len(active_threats),
        },
        "services": services,
        "recent_events": recent_events,
    }


# ── Devices ──────────────────────────────────────────────────────

@app.get("/api/network/current")
async def get_current_network():
    """The network the appliance is attached to, plus every network it knows."""
    identity = current_network()
    known = []
    for n in registry.list_networks():
        row = n.to_dict()
        row["is_current"] = identity is not None and n.network_id == identity.network_id
        known.append(row)

    return {
        "current": identity.to_dict() if identity else None,
        "known_networks": known,
    }


@app.get("/api/devices")
async def get_devices(scope: str = Query("current", pattern="^(current|all)$")):
    """
    Devices on the current network by default.

    `scope=all` returns every device ever recorded, including those from
    other networks — useful for history, but they are not reachable now.
    """
    if scope == "all":
        devices = registry.get_all_devices()
    else:
        devices = registry.get_devices_for_network(current_network_id())

    return [
        {
            "device_id": d.device_id,
            "mac": d.mac,
            "ip": d.ip,
            "vendor": d.vendor,
            "os_guess": d.os_guess,
            "risk_score": d.risk_score or 0.0,
            "open_ports": normalize_open_ports(json.loads(d.open_ports or "[]")),
            "cve_list": json.loads(d.cve_list or "[]"),
            "is_quarantined": bool(d.is_quarantined),
            "last_seen": d.last_seen.isoformat() if d.last_seen else None,
            "is_online": compute_is_online(d.last_seen),
        } for d in devices
    ]


@app.get("/api/devices/{device_id}")
async def get_device(device_id: str):
    d = registry.get_device(device_id)
    if not d:
        raise HTTPException(status_code=404, detail="Device not found")
    threats = registry.get_device_threats(device_id)
    return {
        "device_id": d.device_id,
        "mac": d.mac,
        "ip": d.ip,
        "vendor": d.vendor,
        "os_guess": d.os_guess,
        "firmware_ver": d.firmware_ver,
        "risk_score": d.risk_score or 0.0,
        "open_ports": normalize_open_ports(json.loads(d.open_ports or "[]")),
        "cve_list": json.loads(d.cve_list or "[]"),
        "is_quarantined": bool(d.is_quarantined),
        "last_seen": d.last_seen.isoformat() if d.last_seen else None,
        "is_online": compute_is_online(d.last_seen),
        "baseline_path": d.baseline_path,
        "recent_threats": [
            {
                "event_id": e.event_id,
                "tactic": e.tactic,
                "technique_id": e.technique_id,
                "severity": e.severity,
                "summary": e.summary,
                "timestamp": e.timestamp.isoformat() if e.timestamp else None,
            } for e in threats[:10]
        ],
    }


# ── Threats ──────────────────────────────────────────────────────

@app.get("/api/detection/status")
async def detection_status():
    """
    Warm-up state of the anomaly detection pipeline.

    A device yields no anomaly score until its sliding window is full, so an
    empty threat list is ambiguous on its own. This reports whether detection
    is still warming up or is actually running and finding nothing.
    """
    try:
        raw = await redis_client.hgetall(app_settings.anomaly_status_key)
    except RedisError:
        raw = {}

    if not raw:
        return {
            "worker_online": False,
            "state": "offline",
            "detail": "Anomaly detection worker is not reporting. Threat analysis is not running.",
            "devices_seen": 0,
            "devices_ready": 0,
            "packets_processed": 0,
            "window_size": 0,
            "progress": 0.0,
        }

    def _num(key, cast=float, default=0):
        try:
            return cast(raw.get(key, default))
        except (TypeError, ValueError):
            return default

    devices_seen = _num("devices_seen", int)
    devices_ready = _num("devices_ready", int)
    window_size = _num("window_size", int)
    packets = _num("packets_processed", int)

    progress = (devices_ready / devices_seen) if devices_seen else 0.0

    if devices_seen == 0:
        state = "waiting"
        detail = "Waiting for traffic. No packets seen yet on this network."
    elif devices_ready == 0:
        state = "warming_up"
        detail = (
            f"Building traffic baselines — 0 of {devices_seen} device(s) ready. "
            f"Each needs {window_size} packets before analysis can begin."
        )
    elif devices_ready < devices_seen:
        state = "warming_up"
        detail = (
            f"Analysing {devices_ready} of {devices_seen} device(s). "
            "The rest are still building their baseline."
        )
    else:
        state = "active"
        detail = f"Actively analysing all {devices_seen} device(s)."

    return {
        "worker_online": True,
        "state": state,
        "detail": detail,
        "devices_seen": devices_seen,
        "devices_ready": devices_ready,
        "packets_processed": packets,
        "window_size": window_size,
        "progress": round(progress, 3),
    }


@app.get("/api/threats")
async def get_threats(limit: int = 50,
                      scope: str = Query("current", pattern="^(current|all)$")):
    net_id = None if scope == "all" else current_network_id()
    events = registry.get_recent_threats(limit=limit, network_id=net_id)
    return [
        {
            "event_id": e.event_id,
            "device_id": e.device_id,
            "tactic": e.tactic,
            "technique_id": e.technique_id,
            "confidence": e.confidence,
            "severity": e.severity,
            "summary": e.summary,
            "indicators": json.loads(e.indicators or "[]"),
            "action_taken": e.action_taken,
            "resolved": bool(e.resolved),
            "timestamp": e.timestamp.isoformat() if e.timestamp else None,
        } for e in events
    ]


@app.get("/api/threats/{event_id}")
async def get_threat_detail(event_id: str):
    """
    Full evidence for one event — backs the "View Logs / Investigate" panel.
    Includes everything stored plus, for honeypot-sourced events, the captured
    credentials and commands recovered from the Cowrie session log.
    """
    e = registry.get_threat(event_id)
    if e is None:
        raise HTTPException(status_code=404, detail="threat event not found")

    indicators = json.loads(e.indicators or "[]")
    detail = {
        "event_id": e.event_id,
        "device_id": e.device_id,
        "tactic": e.tactic,
        "technique_id": e.technique_id,
        "confidence": e.confidence,
        "severity": e.severity,
        "summary": e.summary,
        "indicators": indicators,
        "action_taken": e.action_taken,
        "resolved": bool(e.resolved),
        "network_id": e.network_id,
        "timestamp": e.timestamp.isoformat() if e.timestamp else None,
        "captured_credentials": [],
        "commands": [],
    }

    # Honeypot events carry the attacker IP as the source indicator; pull the
    # matching Cowrie session so the analyst sees exactly what was attempted.
    src_ip = next((i for i in indicators if isinstance(i, str) and _looks_like_ip(i)), None)
    if src_ip and (e.device_id or "").startswith("honeypot:"):
        for s in parse_cowrie_sessions():
            if s.get("src_ip") == src_ip:
                detail["captured_credentials"].extend(
                    f"{a.get('username','')}:{a.get('password','')}"
                    for a in s.get("login_attempts", [])
                )
                detail["commands"].extend(s.get("commands", []))
        # De-dup while keeping order
        detail["captured_credentials"] = list(dict.fromkeys(detail["captured_credentials"]))[:20]
        detail["commands"] = detail["commands"][:50]

    return detail


@app.post("/api/threats/{event_id}/acknowledge")
async def acknowledge_threat(event_id: str, resolved: bool = True):
    """Mark a threat acknowledged/resolved (analyst has triaged it)."""
    if not registry.set_threat_resolved(event_id, resolved):
        raise HTTPException(status_code=404, detail="threat event not found")
    return {"event_id": event_id, "resolved": resolved}


def _build_indicator_text(indicators_raw: str) -> str:
    try:
        indicators = json.loads(indicators_raw or "[]")
    except json.JSONDecodeError:
        return ""

    tokens: list[str] = []
    for indicator in indicators:
        if isinstance(indicator, str):
            tokens.append(indicator)
            continue
        if isinstance(indicator, dict):
            value = indicator.get("value")
            kind = indicator.get("type")
            if isinstance(kind, str):
                tokens.append(kind)
            if isinstance(value, str):
                tokens.append(value)
    return " ".join(tokens)


@app.get("/api/search")
async def global_search(
    query: str = Query(..., min_length=1),
    limit: int = Query(8, ge=1, le=50),
):
    needle = query.strip().lower()
    if not needle:
        return {"query": query, "total": 0, "devices": [], "threats": []}

    net_id = current_network_id()

    matched_devices = []
    for device in registry.get_devices_for_network(net_id):
        fields = [
            device.device_id or "",
            device.mac or "",
            device.ip or "",
            device.vendor or "",
            device.os_guess or "",
        ]
        if any(needle in field.lower() for field in fields):
            matched_devices.append({
                "device_id": device.device_id,
                "mac": device.mac,
                "ip": device.ip,
                "vendor": device.vendor,
                "os_guess": device.os_guess,
                "risk_score": device.risk_score or 0.0,
            })

    matched_threats = []
    for threat in registry.get_recent_threats(limit=300, network_id=net_id):
        fields = [
            threat.event_id or "",
            threat.device_id or "",
            threat.tactic or "",
            threat.technique_id or "",
            threat.summary or "",
            _build_indicator_text(threat.indicators or ""),
        ]
        if any(needle in field.lower() for field in fields):
            matched_threats.append({
                "event_id": threat.event_id,
                "device_id": threat.device_id,
                "tactic": threat.tactic,
                "technique_id": threat.technique_id,
                "summary": threat.summary,
                "severity": threat.severity or 0,
                "timestamp": threat.timestamp.isoformat() if threat.timestamp else None,
            })

    return {
        "query": query,
        "total": len(matched_devices) + len(matched_threats),
        "devices": matched_devices[:limit],
        "threats": matched_threats[:limit],
    }


# ── Actions ──────────────────────────────────────────────────────

@app.post("/api/actions/quarantine/{device_id}")
async def quarantine_device(device_id: str):
    action = {
        "device_id": device_id,
        "action": "quarantine_device",
        "severity": 10,
        "event_id": "manual-ui-action",
    }
    await redis_client.publish("sentinel:actions", json.dumps(action))
    return {"status": "action_dispatched", "device_id": device_id}


@app.post("/api/devices/{device_id}/scan")
async def scan_device_ports(device_id: str):
    """Run a TCP connect scan on common IoT ports for a device."""
    d = registry.get_device(device_id)
    if not d:
        raise HTTPException(status_code=404, detail="Device not found")
    ip = d.ip or ""
    if not ip:
        raise HTTPException(status_code=400, detail="Device has no known IP address to scan")

    try:
        addr = ipaddress.ip_address(ip)
    except ValueError:
        raise HTTPException(status_code=400, detail=f"{ip!r} is not a valid IP address")

    if addr.is_multicast:
        raise HTTPException(status_code=400, detail=f"{ip} is a multicast address, not a scannable device")
    if addr.is_unspecified:
        raise HTTPException(status_code=400, detail=f"{ip} is an unspecified address, not a scannable device")
    if addr.is_link_local:
        raise HTTPException(status_code=400, detail=f"{ip} is a link-local address, not a scannable device")
    if ip == "255.255.255.255" or ip.endswith(".255"):
        raise HTTPException(status_code=400, detail=f"{ip} is a broadcast address, not a scannable device")

    open_ports = await socket_scan(ip)
    registry.upsert_device(mac=d.mac, device_id=device_id, open_ports=open_ports)
    return {"device_id": device_id, "ip": ip, "open_ports": open_ports, "ports_found": len(open_ports)}


@app.post("/api/actions/honeypot/{device_id}")
async def redirect_to_honeypot(device_id: str):
    action = {
        "device_id": device_id,
        "action": "redirect_to_honeypot",
        "severity": 7,
        "event_id": "manual-ui-action",
    }
    await redis_client.publish("sentinel:actions", json.dumps(action))
    return {"status": "action_dispatched", "device_id": device_id}


# ── Node Deployment ───────────────────────────────────────────────

@app.post("/api/nodes/deploy")
async def deploy_node(body: NodeDeployRequest):
    """Register a new monitored node into the device registry."""
    try:
        ipaddress.ip_address(body.ip)
    except ValueError:
        raise HTTPException(status_code=400, detail=f"Invalid IP address: {body.ip!r}")

    if not body.label.strip():
        raise HTTPException(status_code=400, detail="Node label must not be empty")

    # Derive a stable MAC from the IP if caller didn't supply one
    if body.mac:
        mac = body.mac.strip().lower()
    else:
        digest = hashlib.md5(body.ip.encode()).hexdigest()
        mac = ":".join(digest[i:i+2] for i in range(0, 12, 2))

    device = registry.upsert_device(
        mac=mac,
        ip=body.ip,
        vendor=body.label.strip(),
    )
    return {
        "device_id": device.device_id,
        "ip": device.ip,
        "mac": device.mac,
        "label": device.vendor,
        "message": f"Node '{body.label}' registered at {body.ip}",
    }


# ── Threat Intelligence ──────────────────────────────────────────

@app.get("/api/intel/{ip}")
async def get_ip_intel(ip: str):
    """Enrich an IP with AlienVault OTX and AbuseIPDB data."""
    try:
        data = await intel_bus.enrich_ip(ip)
        return data
    except Exception as e:
        logger.error("intel_lookup_failed", ip=ip, error=str(e))
        return {"ip": ip, "otx_pulse_count": 0, "otx_tags": [], "abuse_score": 0, "is_malicious": False}


# ── Firewall Rules ─────────────────────────────────────────────────

def _rule_is_block(rule) -> bool:
    """A rule enforces a drop only when its action denies traffic."""
    return (rule.action or "").upper() in ("DROP", "DENY", "BLOCK", "REJECT")


@app.get("/api/firewall/rules")
async def get_firewall_rules(scope: str = Query("current", pattern="^(current|all)$")):
    net_id = None if scope == "all" else current_network_id()
    rules = registry.get_firewall_rules(network_id=net_id)
    # One nft read for the whole list, so each rule can report whether it is
    # actually enforced on the host or only recorded logically.
    enforced_ips = host_firewall.blocked_ips()
    return [
        {
            "rule_id": r.rule_id,
            "protocol": r.protocol,
            "target": r.target,
            "action": r.action,
            "enabled": bool(r.enabled),
            "description": r.description or "",
            "created_at": r.created_at.isoformat() if r.created_at else None,
            "network_id": r.network_id,
            "enforced": (r.target.split("/")[0] in enforced_ips) if r.target else False,
        } for r in rules
    ]


@app.post("/api/firewall/rules")
async def create_firewall_rule(body: FirewallRuleCreate):
    # Scope the rule to the current network only when its target is a
    # specific address inside this subnet. Broad targets (0.0.0.0/0 and
    # similar) stay network-agnostic so they keep applying everywhere.
    identity = current_network()
    scoped_network_id = None
    if identity and ip_in_subnet(body.target.split("/")[0], identity.subnet):
        scoped_network_id = identity.network_id

    rule = registry.add_firewall_rule(
        protocol=body.protocol,
        target=body.target,
        action=body.action,
        description=body.description or "",
        network_id=scoped_network_id,
    )

    # Apply the real nftables drop for enabled block rules. The safety guard
    # inside HostFirewall refuses self/gateway/broad targets and, in that case,
    # the rule is kept as a logical record with the reason surfaced to the UI.
    enforced, note = False, "logical rule (no drop action)"
    if bool(rule.enabled) and _rule_is_block(rule):
        result = host_firewall.block(rule.target)
        enforced, note = result.enforced, result.note

    return {
        "rule_id": rule.rule_id,
        "protocol": rule.protocol,
        "target": rule.target,
        "action": rule.action,
        "enabled": bool(rule.enabled),
        "description": rule.description or "",
        "created_at": rule.created_at.isoformat() if rule.created_at else None,
        "enforced": enforced,
        "enforcement_note": note,
    }


@app.put("/api/firewall/rules/{rule_id}/toggle")
async def toggle_firewall_rule(rule_id: str):
    rule = registry.toggle_firewall_rule(rule_id)
    if not rule:
        raise HTTPException(status_code=404, detail="Rule not found")

    # Enabling re-applies the drop; disabling removes it from the host so the
    # target regains connectivity, matching what the toggle shows in the UI.
    enforced, note = False, ""
    if _rule_is_block(rule):
        result = host_firewall.block(rule.target) if rule.enabled else host_firewall.unblock(rule.target)
        enforced, note = result.enforced, result.note

    return {"rule_id": rule.rule_id, "enabled": bool(rule.enabled),
            "enforced": enforced, "enforcement_note": note}


@app.delete("/api/firewall/rules/{rule_id}")
async def delete_firewall_rule(rule_id: str):
    # Look up the rule first so we know which host rule to tear down. Removing
    # the nftables drop BEFORE dropping the DB row means an unblock genuinely
    # restores the target's traffic rather than orphaning a live drop.
    rule = registry.get_firewall_rule(rule_id)
    if not rule:
        raise HTTPException(status_code=404, detail="Rule not found")

    unblocked = host_firewall.unblock(rule.target) if _rule_is_block(rule) else None

    deleted = registry.delete_firewall_rule(rule_id)
    if not deleted:
        raise HTTPException(status_code=404, detail="Rule not found")
    return {
        "status": "deleted",
        "rule_id": rule_id,
        "enforcement_removed": bool(unblocked and unblocked.enforced),
        "enforcement_note": unblocked.note if unblocked else "logical rule (no drop action)",
    }


# ── Honeypots ─────────────────────────────────────────────────────

@app.get("/api/honeypots/sessions")
async def honeypot_sessions():
    return parse_cowrie_sessions()


@app.get("/api/honeypots/status")
async def honeypot_status():
    cowrie_logs = list(COWRIE_LOG_DIR.glob("cowrie.json*")) if COWRIE_LOG_DIR.exists() else []
    sessions = parse_cowrie_sessions()
    successful = [s for s in sessions if s["success"]]
    unique_ips = len({s["src_ip"] for s in sessions})

    # Honeypot addresses were hardcoded to a 192.168.0.x network. Derive them
    # from the current subnet instead, so they stay meaningful after the
    # appliance moves to a different network.
    identity = current_network()
    cowrie_ip, canary_ip = "unassigned", "unassigned"
    if identity:
        try:
            hosts = ipaddress.ip_network(identity.subnet, strict=False)
            cowrie_ip = str(hosts.network_address + 201)
            canary_ip = str(hosts.network_address + 202)
        except ValueError:
            pass

    return {
        "cowrie": {
            "name": "Cowrie (SSH/Telnet)",
            "ip": cowrie_ip,
            "status": honeypot_state(HONEYPOT_CONTAINERS["cowrie"], bool(cowrie_logs)),
            "total_sessions": len(sessions),
            "successful_logins": len(successful),
            "unique_attackers": unique_ips,
        },
        "opencanary": {
            "name": "OpenCanary",
            "ip": canary_ip,
            # Previously hardcoded to ONLINE regardless of reality, which
            # reported a honeypot as protecting the network even when it had
            # never been deployed.
            "status": honeypot_state(HONEYPOT_CONTAINERS["opencanary"], OPENCANARY_LOG.exists()),
            "services": ["SMB", "HTTP", "FTP"],
        },
    }


# ── Settings ──────────────────────────────────────────────────────

@app.get("/api/settings")
async def get_settings():
    ui = load_ui_settings()
    identity = current_network()

    # Reflect the live network rather than the stored default: a subnet
    # saved while on another network is misleading once we have moved.
    if identity:
        ui = {
            **ui,
            "monitored_subnets": identity.subnet,
            "capture_interface": identity.interface,
        }

    return {
        **ui,
        "system": {
            "version": "1.0.0",
            "db_url": app_settings.db_url,
            "redis_host": app_settings.redis_host,
            "redis_port": app_settings.redis_port,
            "ollama_base_url": app_settings.ollama_base_url,
            "llm_model": app_settings.llm_model,
        },
        "network": identity.to_dict() if identity else None,
    }


@app.put("/api/settings")
async def update_settings(body: SettingsUpdate):
    current = load_ui_settings()
    patch = {k: v for k, v in body.model_dump().items() if v is not None}
    current.update(patch)
    save_ui_settings(current)
    return current


# ── System Metrics ────────────────────────────────────────────────

@app.get("/api/system/metrics")
async def system_metrics():
    cpu = await read_cpu_percent()
    mem = read_mem_info()
    return {
        "cpu_percent": cpu,
        "memory": mem,
        "lstm_latency_ms": None,
        "llm_latency_ms": None,
    }


@app.get("/api/diagnostics")
async def run_diagnostics():
    now = datetime.utcnow().isoformat() + "Z"
    checks = []

    checks.append({
        "name": "api",
        "status": "healthy",
        "ok": True,
        "detail": "FastAPI backend is responding.",
        "checked_at": now,
    })

    redis_ok = False
    redis_detail = "Redis ping failed."
    try:
        redis_ok = bool(await redis_client.ping())
        if redis_ok:
            redis_detail = "Redis connection is healthy."
    except RedisError as e:
        redis_detail = f"Redis error: {e}"
    checks.append({
        "name": "redis",
        "status": "healthy" if redis_ok else "critical",
        "ok": redis_ok,
        "detail": redis_detail,
        "checked_at": now,
    })

    db_ok = True
    db_detail = "SQLite registry query succeeded."
    total_devices = 0
    try:
        devices = registry.get_all_devices()
        total_devices = len(devices)
        db_detail = f"SQLite registry reachable ({total_devices} devices indexed)."
    except (OSError, ValueError, RuntimeError, SQLAlchemyError) as e:
        db_ok = False
        db_detail = f"Registry query failed: {e}"
    checks.append({
        "name": "registry",
        "status": "healthy" if db_ok else "critical",
        "ok": db_ok,
        "detail": db_detail,
        "checked_at": now,
    })

    cowrie_logs = list(COWRIE_LOG_DIR.glob("cowrie.json*")) if COWRIE_LOG_DIR.exists() else []
    cowrie_ok = len(cowrie_logs) > 0
    checks.append({
        "name": "cowrie",
        "status": "healthy" if cowrie_ok else "degraded",
        "ok": cowrie_ok,
        "detail": f"{len(cowrie_logs)} Cowrie log file(s) detected.",
        "checked_at": now,
    })

    if any(c["status"] == "critical" for c in checks):
        overall_status = "critical"
    elif any(c["status"] == "degraded" for c in checks):
        overall_status = "degraded"
    else:
        overall_status = "healthy"

    ui = load_ui_settings()
    metrics = {
        "cpu_percent": await read_cpu_percent(),
        "memory": read_mem_info(),
        "lstm_latency_ms": None,
        "llm_latency_ms": None,
    }

    return {
        "overall_status": overall_status,
        "generated_at": now,
        "checks": checks,
        "system_metrics": metrics,
        "context": {
            "capture_interface": ui.get("capture_interface", app_settings.capture_interface),
            "monitored_subnets": ui.get("monitored_subnets", "192.168.0.0/24"),
            "total_devices": total_devices,
        },
    }


@app.get("/api/logs")
async def get_logs(
    file: Optional[str] = None,
    lines: int = Query(200, ge=20, le=2000),
    level: Optional[str] = None,
    query: Optional[str] = None,
):
    if not LOGS_DIR.exists():
        return {"files": [], "active_file": None, "entries": []}

    files = sorted(
        [p for p in LOGS_DIR.glob("*.log") if p.is_file()],
        key=lambda p: p.stat().st_mtime,
        reverse=True,
    )
    file_index = {p.name: p for p in files}
    selected_path = file_index.get(file) if file else (files[0] if files else None)

    file_meta = [
        {
            "name": p.name,
            "size_bytes": p.stat().st_size,
            "modified_at": datetime.utcfromtimestamp(p.stat().st_mtime).isoformat() + "Z",
        }
        for p in files
    ]

    if not selected_path:
        return {"files": file_meta, "active_file": None, "entries": []}

    with selected_path.open("r", encoding="utf-8", errors="replace") as log_file:
        all_lines = log_file.readlines()

    start_idx = max(len(all_lines) - lines, 0)
    parsed = [
        _parse_log_line(line, start_idx + idx + 1)
        for idx, line in enumerate(all_lines[start_idx:])
    ]

    normalized_level = level.strip().lower() if level else None
    normalized_query = query.strip().lower() if query else None
    if normalized_level:
        parsed = [entry for entry in parsed if entry["level"] == normalized_level]
    if normalized_query:
        parsed = [
            entry for entry in parsed
            if normalized_query in entry["message"].lower() or normalized_query in entry["raw"].lower()
        ]

    parsed.reverse()
    return {
        "files": file_meta,
        "active_file": selected_path.name,
        "entries": parsed,
    }


# ── WebSocket ─────────────────────────────────────────────────────

@app.websocket("/ws/events")
async def websocket_endpoint(websocket: WebSocket):
    await websocket.accept()
    pubsub = redis_client.pubsub()
    await pubsub.subscribe("sentinel:anomaly", "sentinel:threat", "sentinel:alerts", "sentinel:actions")
    logger.info("websocket_connected")
    try:
        while True:
            message = await pubsub.get_message(ignore_subscribe_messages=True, timeout=0.5)
            if message:
                try:
                    await websocket.send_json({
                        "channel": message["channel"],
                        "data": json.loads(message["data"])
                    })
                except Exception:
                    break
            await asyncio.sleep(0.1)
    except WebSocketDisconnect:
        logger.info("websocket_disconnected")
    except Exception as e:
        logger.error("websocket_error", error=str(e))
    finally:
        await pubsub.unsubscribe()


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
