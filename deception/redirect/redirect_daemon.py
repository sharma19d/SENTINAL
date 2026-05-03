"""
SENTINEL Layer 4 — Redirect Daemon

Subscribes to Redis actions and manages nftables redirection to honeypots.
"""

import json
import redis
import structlog
from typing import Dict, Any

from sentinel.config.settings import settings as app_settings
from sentinel.core.firewall.nftables_manager import NftablesManager
from sentinel.core.fingerprinting.registry import DeviceRegistry

logger = structlog.get_logger(__name__)

class RedirectDaemon:
    """
    Worker that translates AI decisions into network-level redirections.
    """
    def __init__(self):
        self.redis_client = redis.Redis(
            host=app_settings.redis_host,
            port=app_settings.redis_port,
            db=app_settings.redis_db,
            password=app_settings.redis_password,
            decode_responses=True
        )
        self.pubsub = self.redis_client.pubsub()
        self.nft_manager = NftablesManager()
        self.registry = DeviceRegistry(db_url=app_settings.db_url)
        
        # Honeypot IPs (from docker-compose.yml)
        self.honeypots = {
            "cowrie": "192.168.0.201",
            "opencanary": "192.168.0.202"
        }
        
        # Channels
        self.action_channel = "sentinel:actions"

    def run(self):
        """Main loop."""
        try:
            self.pubsub.subscribe(self.action_channel)
            logger.info("redirect_daemon_started", channel=self.action_channel)
            
            for message in self.pubsub.listen():
                if message["type"] == "message":
                    self._process_action(message["data"])
                    
        except Exception as e:
            logger.error("redirect_daemon_failed", error=str(e))
        finally:
            self.pubsub.unsubscribe()
            logger.info("redirect_daemon_stopped")

    def _process_action(self, data_str: str):
        """Handle a response action."""
        try:
            data = json.loads(data_str)
            action = data.get("action")
            
            if action == "redirect_to_honeypot":
                self._handle_redirect(data)
            elif action == "quarantine_device":
                self._handle_quarantine(data)
                
        except Exception as e:
            logger.error("action_processing_error", error=str(e))

    def _handle_redirect(self, data: Dict[str, Any]):
        """Execute redirection to a honeypot."""
        attacker_ips = data.get("indicators", [])
        victim_device_id = data.get("device_id")
        
        if not attacker_ips or not victim_device_id:
            return
            
        # Get victim IP
        victim = self.registry.get_device(victim_device_id)
        if not victim or not victim.ip:
            logger.error("victim_ip_not_found", device_id=victim_device_id)
            return

        # Choose honeypot based on some heuristic or just default to OpenCanary
        # For now, let's use OpenCanary as default.
        honeypot_ip = self.honeypots["opencanary"]
        
        for attacker_ip in attacker_ips:
            success = self.nft_manager.redirect_traffic(
                attacker_ip=attacker_ip,
                victim_ip=victim.ip,
                honeypot_ip=honeypot_ip
            )
            if success:
                logger.info("redirection_applied", 
                             attacker=attacker_ip, 
                             victim=victim.ip, 
                             honeypot=honeypot_ip)

    def _handle_quarantine(self, data: Dict[str, Any]):
        """Execute quarantine (blocking)."""
        # In a real scenario, we might block the device MAC.
        # For Layer 5 simplicity, we'll block the attacker IP detected.
        attacker_ips = data.get("indicators", [])
        for ip in attacker_ips:
            self.nft_manager.block_ip(ip)

if __name__ == "__main__":
    daemon = RedirectDaemon()
    daemon.run()
