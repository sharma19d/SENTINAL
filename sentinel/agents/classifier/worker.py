"""
SENTINEL Agent 2 — Classifier Worker

Subscribes to anomalies, enriches with device data, and classifies via Gemma 4.
"""

import asyncio
import json
import uuid
import redis.asyncio as redis
import structlog
from typing import Dict, Any

from sentinel.config.settings import settings as app_settings
from sentinel.agents.classifier.gemma_client import GemmaClassifier
from sentinel.core.fingerprinting.registry import DeviceRegistry
from intel.bus import IntelBus

logger = structlog.get_logger(__name__)

class ClassifierWorker:
    """
    Agent 2 Worker: Bridge between Anomaly Detector and LLM Classifier.
    """
    def __init__(self):
        self.redis_client = redis.Redis(
            host=app_settings.redis_host,
            port=app_settings.redis_port,
            db=app_settings.redis_db,
            password=app_settings.redis_password,
            decode_responses=True
        )
        self.registry = DeviceRegistry(db_url=app_settings.db_url)
        self.classifier = GemmaClassifier()
        self.intel_bus = IntelBus()
        
        # Channels
        self.anomaly_channel = "sentinel:anomaly"
        self.threat_channel = "sentinel:threat"

    async def run(self):
        """Main loop to process anomaly events."""
        pubsub = self.redis_client.pubsub()
        try:
            await pubsub.subscribe(self.anomaly_channel)
            logger.info("classifier_worker_started", channel=self.anomaly_channel)
            
            async for message in pubsub.listen():
                if message["type"] == "message":
                    # Run classification in background to not block the stream
                    asyncio.create_task(self._process_anomaly(message["data"]))
                    
        except Exception as e:
            logger.error("classifier_worker_failed", error=str(e))
        finally:
            await pubsub.unsubscribe()
            await self.redis_client.close()
            logger.info("classifier_worker_stopped")

    async def _process_anomaly(self, data_str: str):
        """
        Enrich anomaly with device data and call Gemma 4.
        """
        try:
            anomaly = json.loads(data_str)
            device_id = anomaly["device_id"]
            dst_ip = anomaly["dst_ip"]
            
            # 1. Enrich with Device Registry
            device = self.registry.get_device(device_id)
            context = {**anomaly}
            
            if device:
                context["vendor"] = device.vendor
                context["os"] = device.os_guess
                # Extract CVE IDs for the prompt
                cves = json.loads(device.cve_list or "[]")
                context["cves"] = ", ".join([c["cve_id"] for c in cves]) if cves else "None"
            
            # 2. Enrich with Global Intel (Layer 6)
            logger.info("enriching_with_global_intel", ip=dst_ip)
            intel_data = await self.intel_bus.enrich_ip(dst_ip)
            context["intel"] = intel_data
            
            logger.info("classifying_threat", device=device_id, score=anomaly["anomaly_score"])
            
            # 3. Gemma 4 Classification
            classification = await self.classifier.classify(context)
            
            if classification:
                # 4. Store and Publish Threat
                event_id = str(uuid.uuid4())
                threat_event = {
                    "event_id": event_id,
                    "device_id": device_id,
                    **classification,
                    "indicators": [anomaly["dst_ip"]],
                    "intel": intel_data,
                    "timestamp": anomaly["timestamp"]
                }
                
                # Save to DB
                self.registry.add_threat_event(
                    event_id=event_id,
                    device_id=device_id,
                    tactic=classification.get("tactic"),
                    technique_id=classification.get("technique_id"),
                    confidence=classification.get("confidence"),
                    severity=classification.get("severity"),
                    summary=classification.get("summary"),
                    indicators=[anomaly["dst_ip"]]
                )
                
                # Publish to Redis
                await self.redis_client.publish(self.threat_channel, json.dumps(threat_event))
                
                logger.warning("threat_classified", 
                                tactic=threat_event["tactic"], 
                                severity=threat_event["severity"],
                                device=device_id)
                
        except Exception as e:
            logger.error("threat_processing_error", error=str(e))

if __name__ == "__main__":
    worker = ClassifierWorker()
    asyncio.run(worker.run())
