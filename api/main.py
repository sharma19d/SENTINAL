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
import time
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime
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
LOGS_DIR = Path("logs")
LOG_LINE_RE = re.compile(r"^(?P<timestamp>[\d\-:T.Z+ ]+)\s+\[(?P<level>[^\]]+)\]\s+(?P<message>.*)$")
ANSI_ESCAPE_RE = re.compile(r"\x1B\[[0-?]*[ -/]*[@-~]")

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
    devices = registry.get_all_devices()
    recent_threats = registry.get_recent_threats(limit=100)
    active_threats = [t for t in recent_threats if not t.resolved]
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
        "active_threats": len(active_threats),
        "quarantined": len(quarantined),
        "critical_devices": len(critical_devices),
        "recent_activity": activity,
    }


@app.get("/api/notifications")
async def notifications(limit: int = Query(8, ge=1, le=50)):
    events = registry.get_recent_threats(limit=100)
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
    devices = registry.get_all_devices()
    recent_threats = registry.get_recent_threats(limit=50)
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

@app.get("/api/devices")
async def get_devices():
    devices = registry.get_all_devices()
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

@app.get("/api/threats")
async def get_threats(limit: int = 50):
    events = registry.get_recent_threats(limit=limit)
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

    matched_devices = []
    for device in registry.get_all_devices():
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
    for threat in registry.get_recent_threats(limit=300):
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
    if not ip or ip in ("0.0.0.0", "255.255.255.255") or ip.startswith("224."):
        raise HTTPException(status_code=400, detail=f"Device IP {ip!r} is not scannable")

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

@app.get("/api/firewall/rules")
async def get_firewall_rules():
    rules = registry.get_firewall_rules()
    return [
        {
            "rule_id": r.rule_id,
            "protocol": r.protocol,
            "target": r.target,
            "action": r.action,
            "enabled": bool(r.enabled),
            "description": r.description or "",
            "created_at": r.created_at.isoformat() if r.created_at else None,
        } for r in rules
    ]


@app.post("/api/firewall/rules")
async def create_firewall_rule(body: FirewallRuleCreate):
    rule = registry.add_firewall_rule(
        protocol=body.protocol,
        target=body.target,
        action=body.action,
        description=body.description or "",
    )
    return {
        "rule_id": rule.rule_id,
        "protocol": rule.protocol,
        "target": rule.target,
        "action": rule.action,
        "enabled": bool(rule.enabled),
        "description": rule.description or "",
        "created_at": rule.created_at.isoformat() if rule.created_at else None,
    }


@app.put("/api/firewall/rules/{rule_id}/toggle")
async def toggle_firewall_rule(rule_id: str):
    rule = registry.toggle_firewall_rule(rule_id)
    if not rule:
        raise HTTPException(status_code=404, detail="Rule not found")
    return {"rule_id": rule.rule_id, "enabled": bool(rule.enabled)}


@app.delete("/api/firewall/rules/{rule_id}")
async def delete_firewall_rule(rule_id: str):
    deleted = registry.delete_firewall_rule(rule_id)
    if not deleted:
        raise HTTPException(status_code=404, detail="Rule not found")
    return {"status": "deleted", "rule_id": rule_id}


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

    return {
        "cowrie": {
            "name": "Cowrie (SSH/Telnet)",
            "ip": "192.168.0.201",
            "status": "ONLINE" if cowrie_logs else "STANDBY",
            "total_sessions": len(sessions),
            "successful_logins": len(successful),
            "unique_attackers": unique_ips,
        },
        "opencanary": {
            "name": "OpenCanary",
            "ip": "192.168.0.202",
            "status": "ONLINE",
            "services": ["SMB", "HTTP", "FTP"],
        },
    }


# ── Settings ──────────────────────────────────────────────────────

@app.get("/api/settings")
async def get_settings():
    ui = load_ui_settings()
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
