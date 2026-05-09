"""
SENTINEL — FastAPI Backend

Provides REST endpoints and WebSocket streams for the Dashboard.
"""

import json
import asyncio
import os
import glob
from datetime import datetime
from pathlib import Path
from typing import Optional

import redis.asyncio as redis
from fastapi import FastAPI, HTTPException, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
import structlog

from sentinel.config.settings import settings as app_settings
from sentinel.core.fingerprinting.registry import DeviceRegistry

logger = structlog.get_logger(__name__)

app = FastAPI(title="SENTINEL API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

registry = DeviceRegistry(db_url=app_settings.db_url)
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

# ── System metrics ─────────────────────────────────────────────────
def read_cpu_percent() -> float:
    try:
        with open("/proc/stat") as f:
            line = f.readline()
        parts = line.split()
        total = sum(int(x) for x in parts[1:])
        idle = int(parts[4])
        return round((1 - idle / total) * 100, 1) if total else 0.0
    except Exception:
        return 0.0

def read_mem_info() -> dict:
    try:
        info = {}
        with open("/proc/meminfo") as f:
            for line in f:
                k, v = line.split(":")
                info[k.strip()] = int(v.split()[0])
        total_gb = round(info.get("MemTotal", 0) / 1024 / 1024, 1)
        avail_gb = round(info.get("MemAvailable", 0) / 1024 / 1024, 1)
        used_gb = round(total_gb - avail_gb, 1)
        pct = round(used_gb / total_gb * 100, 1) if total_gb else 0.0
        return {"total_gb": total_gb, "used_gb": used_gb, "percent": pct}
    except Exception:
        return {"total_gb": 0, "used_gb": 0, "percent": 0}

# ── Pydantic request models ────────────────────────────────────────
class FirewallRuleCreate(BaseModel):
    protocol: str
    target: str
    action: str
    description: Optional[str] = ""

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
            "open_ports": json.loads(d.open_ports or "[]"),
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
        "open_ports": json.loads(d.open_ports or "[]"),
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
    cpu = read_cpu_percent()
    mem = read_mem_info()
    return {
        "cpu_percent": cpu,
        "memory": mem,
        "lstm_latency_ms": None,
        "llm_latency_ms": None,
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
            message = await pubsub.get_message(ignore_subscribe_messages=True, timeout=1.0)
            if message:
                await websocket.send_json({
                    "channel": message["channel"],
                    "data": json.loads(message["data"])
                })
            await asyncio.sleep(0.01)
    except WebSocketDisconnect:
        logger.info("websocket_disconnected")
    except Exception as e:
        logger.error("websocket_error", error=str(e))
    finally:
        await pubsub.unsubscribe()


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
