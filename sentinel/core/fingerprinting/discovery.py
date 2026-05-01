"""
SENTINEL Layer 2 — Discovery Agent

The core logic for device discovery and risk profiling. Listens for
discovery events from Layer 1, maintains the device registry, and
coordinates OUI lookups and CVE scans to build complete risk profiles.
"""

from __future__ import annotations

import asyncio
import json
from datetime import datetime
from typing import Optional

import redis.asyncio as redis
import structlog

from sentinel.config.settings import settings
from sentinel.core.capture.models import DiscoveryEvent, FlowEvent, FlowEventType
from sentinel.core.fingerprinting.cve import CVEScanner
from sentinel.core.fingerprinting.oui import get_vendor
from sentinel.core.fingerprinting.registry import DeviceRegistry

logger = structlog.get_logger(__name__)


class DiscoveryAgent:
    """
    Orchestrator for device discovery and fingerprinting.
    
    Subscribes to Redis channels, processes incoming network events,
    and updates the Device Registry with enriched metadata.
    """

    def __init__(self):
        self.registry = DeviceRegistry(settings.db_url)
        self.cve_scanner = CVEScanner()
        self.redis_client: Optional[redis.Redis] = None
        self._running = False
        self._tasks = []

    async def start(self):
        """Start the discovery agent's event loop with retry logic."""
        self._running = True
        
        while self._running:
            try:
                self.redis_client = redis.Redis(
                    host=settings.redis_host,
                    port=settings.redis_port,
                    db=settings.redis_db,
                    password=settings.redis_password or None,
                    decode_responses=True
                )
                
                # Test connection
                await self.redis_client.ping()
                
                # Subscribe to discovery and flow channels
                pubsub = self.redis_client.pubsub()
                await pubsub.subscribe("sentinel:discovery", "sentinel:flows")
                
                logger.info("discovery_agent_started", 
                            channels=["sentinel:discovery", "sentinel:flows"])
                
                while self._running:
                    message = await pubsub.get_message(ignore_subscribe_messages=True, timeout=1.0)
                    if message:
                        channel = message["channel"]
                        data = json.loads(message["data"])
                        
                        if channel == "sentinel:discovery":
                            await self._handle_discovery_event(data)
                        elif channel == "sentinel:flows":
                            await self._handle_flow_event(data)
                            
            except (redis.ConnectionError, redis.TimeoutError) as e:
                logger.error("redis_connection_failed", error=str(e), retry_in="5s")
                await asyncio.sleep(5)
            except Exception as e:
                logger.error("discovery_agent_unexpected_error", error=str(e))
                await asyncio.sleep(5)
            finally:
                if self.redis_client:
                    await self.redis_client.close()

    def stop(self):
        """Stop the discovery agent."""
        self._running = False

    async def _handle_discovery_event(self, data: dict):
        """Process an ARP, mDNS, SSDP, or DHCP discovery event."""
        mac = data.get("mac_address")
        if not mac:
            return

        ip = data.get("ip_address")
        event_type = data.get("event_type")
        
        logger.info("discovery_event_received", type=event_type, mac=mac, ip=ip)

        # 1. Basic update/create
        vendor = data.get("vendor") or get_vendor(mac)
        
        device_update = {
            "mac": mac,
            "ip": ip,
            "vendor": vendor,
        }

        # 2. Enrich from specific protocol metadata
        if event_type == "mdns":
            device_update["os_guess"] = data.get("mdns_hostname")
        elif event_type == "dhcp":
            device_update["os_guess"] = data.get("dhcp_hostname")
            if data.get("dhcp_vendor_class"):
                device_update["firmware_ver"] = data.get("dhcp_vendor_class")

        # 3. Save to registry
        device = self.registry.upsert_device(mac, **device_update)
        
        # 4. If new device or missing CVEs, trigger background scan
        if not device.cve_list or device.cve_list == "[]":
            asyncio.create_task(self._enrich_device_risk(device.device_id, vendor))

    async def _handle_flow_event(self, data: dict):
        """Process a flow event to update device IP and activity."""
        # Only process NEW_FLOW or periodic updates to keep registry fresh
        event_type = data.get("event_type")
        flow = data.get("flow", {})
        
        # We care about the source device (canonical src in FlowRecord)
        src_mac = flow.get("src_mac")
        src_ip = flow.get("src_ip")
        
        if src_mac:
            self.registry.upsert_device(src_mac, ip=src_ip)
            
        # Also update destination device if it's local
        dst_mac = flow.get("dst_mac")
        dst_ip = flow.get("dst_ip")
        if dst_mac:
            self.registry.upsert_device(dst_mac, ip=dst_ip)

    async def _enrich_device_risk(self, device_id: str, vendor: str):
        """Background task to fetch CVEs and calculate risk score."""
        try:
            if not vendor or vendor == "Unknown":
                return

            logger.info("enriching_device_risk", device_id=device_id, vendor=vendor)
            
            cves = await self.cve_scanner.get_device_vulnerabilities(vendor)
            
            if cves:
                # Calculate simple risk score: average of top 3 CVSS scores
                scores = sorted([c["cvss_score"] for c in cves], reverse=True)
                top_scores = scores[:3]
                risk_score = sum(top_scores) / len(top_scores) if top_scores else 0.0
                
                self.registry.upsert_device(
                    mac="", # Not needed if device_id is provided
                    device_id=device_id,
                    cve_list=cves,
                    risk_score=round(risk_score, 1)
                )
                
                logger.info("device_risk_enriched", 
                            device_id=device_id, 
                            risk_score=risk_score, 
                            cve_count=len(cves))
        except Exception as e:
            logger.error("risk_enrichment_failed", device_id=device_id, error=str(e))


if __name__ == "__main__":
    agent = DiscoveryAgent()
    asyncio.run(agent.start())
