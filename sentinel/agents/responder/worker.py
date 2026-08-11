"""
SENTINEL Agent 3 — Response Worker

Subscribes to classified threats and runs the Response Graph (LangGraph).
"""

import asyncio
import ipaddress
import json
from pathlib import Path
import redis.asyncio as redis
import structlog
from typing import Dict, Any, List

from sentinel.config.settings import settings as app_settings
from sentinel.agents.responder.graph import ResponseGraph
from sentinel.core.firewall.host_firewall import HostFirewall
from sentinel.core.fingerprinting.registry import DeviceRegistry
from sentinel.core.network_identity import detect_current_network

logger = structlog.get_logger(__name__)

# Actions from the policy that mean "stop this attacker on the wire".
ENFORCING_ACTIONS = {"block_ip", "block_attacker", "quarantine_device"}
UI_SETTINGS_FILE = Path("data/sentinel_ui_settings.json")

class ResponseWorker:
    """
    Agent 3 Worker: Orchestrates the final response using LangGraph.
    """
    def __init__(self):
        self.redis_client = redis.Redis(
            host=app_settings.redis_host,
            port=app_settings.redis_port,
            db=app_settings.redis_db,
            password=app_settings.redis_password,
            decode_responses=True
        )
        self.graph = ResponseGraph()
        self.host_firewall = HostFirewall()
        self.registry = DeviceRegistry(db_url=app_settings.db_url)

        # IPs already enforced this run, so repeated detections of the same
        # attacker don't pile up duplicate rules.
        self._blocked_ips: set[str] = set()

        # Channels
        self.threat_channel = "sentinel:threat"
        self.action_channel = "sentinel:actions"
        self.alert_channel = "sentinel:alerts"

    async def run(self):
        """Main loop to process classified threats."""
        pubsub = self.redis_client.pubsub()
        try:
            await pubsub.subscribe(self.threat_channel)
            logger.info("response_worker_started", channel=self.threat_channel)
            
            async for message in pubsub.listen():
                if message["type"] == "message":
                    asyncio.create_task(self._process_threat(message["data"]))
                    
        except Exception as e:
            logger.error("response_worker_failed", error=str(e))
        finally:
            await pubsub.unsubscribe()
            await self.redis_client.close()
            logger.info("response_worker_stopped")

    async def _process_threat(self, data_str: str):
        """
        Run the Response Graph for a threat.
        """
        try:
            threat = json.loads(data_str)
            logger.info("processing_response", event_id=threat["event_id"], severity=threat["severity"])
            
            # Run LangGraph
            final_state = await self.graph.run(threat)
            
            # Dispatch based on final state
            if final_state["status"] == "authorized":
                await self._dispatch_actions(final_state)
            elif final_state["status"] == "wait_for_user":
                await self._notify_user_pending(final_state)
                
        except Exception as e:
            logger.error("response_processing_error", error=str(e))

    def _auto_enforce_enabled(self) -> bool:
        """
        Honour the dashboard's Auto-Quarantine / Manual Approval switch. In
        Manual Approval mode the AI still decides and alerts, but no rule is
        applied until a human acts — the human-in-the-loop the UI advertises.
        """
        try:
            if UI_SETTINGS_FILE.exists():
                return bool(json.loads(UI_SETTINGS_FILE.read_text()).get("auto_quarantine", True))
        except Exception:
            pass
        return True

    @staticmethod
    def _extract_ips(indicators: List[Any]) -> List[str]:
        """Pull IP addresses out of indicators (which may be strings or dicts)."""
        ips: List[str] = []
        for ind in indicators or []:
            value = ind if isinstance(ind, str) else (ind.get("value", "") if isinstance(ind, dict) else "")
            value = (value or "").split("/")[0].strip()
            try:
                ipaddress.ip_address(value)
                ips.append(value)
            except ValueError:
                continue
        return ips

    def _enforce_block(self, event_id: str, device_id: str, indicators: List[Any]) -> List[dict]:
        """
        Turn an AI decision into a real block: apply the nftables drop (guarded
        against self/gateway) and record it in the registry so it appears in the
        Firewall tab. Runs in a worker thread (blocking subprocess + DB calls).
        """
        results: List[dict] = []
        network = None
        try:
            network = detect_current_network()
        except Exception:
            network = None
        network_id = network.network_id if network else None

        for ip in self._extract_ips(indicators):
            if ip in self._blocked_ips:
                continue
            outcome = self.host_firewall.block(ip)
            # Record the rule regardless of enforcement so the decision is
            # visible; the guard case (e.g. our own host) is stored as logical.
            try:
                rule = self.registry.add_firewall_rule(
                    protocol="ANY",
                    target=ip,
                    action="DROP",
                    description=f"AI auto-block (event {event_id}, device {device_id})",
                    network_id=network_id,
                )
                rule_id = rule.rule_id
            except Exception as e:
                logger.error("ai_block_registry_failed", ip=ip, error=str(e))
                rule_id = None
            self._blocked_ips.add(ip)
            results.append({"ip": ip, "enforced": outcome.enforced,
                            "note": outcome.note, "rule_id": rule_id})
            logger.warning("ai_attacker_blocked", event_id=event_id, ip=ip,
                           enforced=outcome.enforced, note=outcome.note)
        return results

    async def _dispatch_actions(self, state: Dict[str, Any]):
        """Publish authorized actions to Redis and enforce blocking ones."""
        auto = self._auto_enforce_enabled()

        for action in state["actions"]:
            # Some actions go to alerts, some to firewall/honeypot
            if "alert" in action:
                await self.redis_client.publish(self.alert_channel, json.dumps({
                    "event_id": state["event_id"],
                    "action": action,
                    "summary": state["summary"]
                }))
                continue

            enforcement = []
            if action in ENFORCING_ACTIONS and auto:
                # Off-load blocking subprocess/DB work so the event loop keeps
                # servicing other threats.
                enforcement = await asyncio.to_thread(
                    self._enforce_block, state["event_id"], state["device_id"], state["indicators"]
                )

            await self.redis_client.publish(self.action_channel, json.dumps({
                "event_id": state["event_id"],
                "device_id": state["device_id"],
                "action": action,
                "indicators": state["indicators"],
                "auto_enforced": bool(enforcement),
                "enforcement": enforcement,
                "pending_approval": (action in ENFORCING_ACTIONS and not auto),
            }))

        logger.info("actions_dispatched", event_id=state["event_id"],
                    count=len(state["actions"]), auto_enforce=auto)

    async def _notify_user_pending(self, state: Dict[str, Any]):
        """Notify the dashboard that an action is waiting for confirmation."""
        await self.redis_client.publish(self.alert_channel, json.dumps({
            "event_id": state["event_id"],
            "status": "pending_confirmation",
            "summary": f"CRITICAL: {state['summary']} - Actions: {state['actions']}",
            "severity": state["severity"]
        }))
        logger.warning("user_confirmation_required", event_id=state["event_id"])

if __name__ == "__main__":
    worker = ResponseWorker()
    asyncio.run(worker.run())
