"""
SENTINEL — FastAPI Backend

Provides REST endpoints and WebSocket streams for the Dashboard.
"""

import json
import asyncio
import redis.asyncio as redis
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
import structlog

from sentinel.config.settings import settings as app_settings
from sentinel.core.fingerprinting.registry import DeviceRegistry

logger = structlog.get_logger(__name__)

app = FastAPI(title="SENTINEL API")

# Allow Dashboard to connect
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"], # In production, restrict to dashboard URL
    allow_methods=["*"],
    allow_headers=["*"],
)

# Registry & Redis
registry = DeviceRegistry(db_url=app_settings.db_url)
redis_client = redis.Redis(
    host=app_settings.redis_host, 
    port=app_settings.redis_port, 
    decode_responses=True
)

@app.get("/api/health")
async def health():
    return {"status": "online", "version": "1.0.0"}

@app.get("/api/devices")
async def get_devices():
    devices = registry.get_all_devices()
    return [
        {
            "device_id": d.device_id,
            "mac": d.mac,
            "ip": d.ip,
            "vendor": d.vendor,
            "risk_score": d.risk_score,
            "is_quarantined": bool(d.is_quarantined),
            "last_seen": d.last_seen
        } for d in devices
    ]

@app.get("/api/threats")
async def get_threats(limit: int = 50):
    events = registry.get_recent_threats(limit=limit)
    return [
        {
            "event_id": e.event_id,
            "device_id": e.device_id,
            "tactic": e.tactic,
            "technique_id": e.technique_id,
            "severity": e.severity,
            "summary": e.summary,
            "timestamp": e.timestamp
        } for e in events
    ]

@app.post("/api/actions/quarantine/{device_id}")
async def quarantine_device(device_id: str):
    # This manually triggers a quarantine action via Redis
    action = {
        "device_id": device_id,
        "action": "quarantine_device",
        "severity": 10,
        "event_id": "manual-ui-action"
    }
    await redis_client.publish("sentinel:actions", json.dumps(action))
    return {"status": "action_dispatched", "device_id": device_id}

@app.websocket("/ws/events")
async def websocket_endpoint(websocket: WebSocket):
    """
    Real-time stream of all SENTINEL events.
    """
    await websocket.accept()
    pubsub = redis_client.pubsub()
    await pubsub.subscribe("sentinel:anomaly", "sentinel:threat", "sentinel:alerts", "sentinel:actions")
    
    logger.info("websocket_connected")
    
    try:
        while True:
            # Check for messages from Redis
            message = await pubsub.get_message(ignore_subscribe_messages=True, timeout=1.0)
            if message:
                await websocket.send_json({
                    "channel": message["channel"],
                    "data": json.loads(message["data"])
                })
            
            # Keep-alive/Heartbeat
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
