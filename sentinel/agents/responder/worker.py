"""
SENTINEL Agent 3 — Response Worker

Subscribes to classified threats and runs the Response Graph (LangGraph).
"""

import asyncio
import json
import redis.asyncio as redis
import structlog
from typing import Dict, Any

from sentinel.config.settings import settings as app_settings
from sentinel.agents.responder.graph import ResponseGraph

logger = structlog.get_logger(__name__)

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

    async def _dispatch_actions(self, state: Dict[str, Any]):
        """Publish authorized actions to Redis."""
        for action in state["actions"]:
            # Some actions go to alerts, some to firewall/honeypot
            if "alert" in action:
                await self.redis_client.publish(self.alert_channel, json.dumps({
                    "event_id": state["event_id"],
                    "action": action,
                    "summary": state["summary"]
                }))
            else:
                await self.redis_client.publish(self.action_channel, json.dumps({
                    "event_id": state["event_id"],
                    "device_id": state["device_id"],
                    "action": action,
                    "indicators": state["indicators"]
                }))
                
        logger.info("actions_dispatched", event_id=state["event_id"], count=len(state["actions"]))

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
