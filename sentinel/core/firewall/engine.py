"""
SENTINEL Layer 5 — Response Engine

The master worker that translates Agent 3 decisions into 
Layer 4 (Deception) and Layer 5 (Firewall) actions.
"""

import json
import redis
import structlog
from typing import Dict, Any

from sentinel.config.settings import settings as app_settings
from sentinel.core.firewall.nftables_manager import NftablesManager
from sentinel.core.firewall.ebpf_loader import XDPFirewall
from sentinel.core.firewall.quarantine import QuarantineManager
from sentinel.core.fingerprinting.registry import DeviceRegistry

logger = structlog.get_logger(__name__)

class ResponseEngine:
    """
    Unified engine for all defensive actions.
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
        
        # Components
        self.nft_manager = NftablesManager()
        self.xdp_firewall = XDPFirewall()
        self.quarantine = QuarantineManager(interface=app_settings.capture_interface)
        self.registry = DeviceRegistry(db_url=app_settings.db_url)
        
        # Attach XDP if available
        if self.xdp_firewall.bpf:
            self.xdp_firewall.attach()
        
        # Honeypot IPs
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
            logger.info("response_engine_started", 
                         channel=self.action_channel,
                         xdp_enabled=self.xdp_firewall.bpf is not None)
            
            for message in self.pubsub.listen():
                if message["type"] == "message":
                    self._process_action(message["data"])
                    
        except Exception as e:
            logger.error("response_engine_failed", error=str(e))
        finally:
            self.pubsub.unsubscribe()
            if self.xdp_firewall:
                self.xdp_firewall.detach()
            logger.info("response_engine_stopped")

    def _process_action(self, data_str: str):
        """Handle a response action from Agent 3."""
        try:
            data = json.loads(data_str)
            action = data.get("action")
            severity = data.get("severity", 0)
            
            logger.info("executing_action", action=action, event_id=data.get("event_id"))
            
            if action == "redirect_to_honeypot":
                self._handle_redirect(data)
            elif action == "quarantine_device":
                self._handle_quarantine(data)
            elif action == "block_attacker":
                self._handle_block(data, fast_drop=(severity >= 9))
                
        except Exception as e:
            logger.error("action_execution_error", error=str(e))

    def _handle_redirect(self, data: Dict[str, Any]):
        """Execute Layer 4 redirection."""
        attacker_ips = data.get("indicators", [])
        victim_device_id = data.get("device_id")
        
        victim = self.registry.get_device(victim_device_id)
        if not victim or not victim.ip:
            return

        honeypot_ip = self.honeypots["opencanary"]
        
        for attacker_ip in attacker_ips:
            self.nft_manager.redirect_traffic(attacker_ip, victim.ip, honeypot_ip)

    def _handle_quarantine(self, data: Dict[str, Any]):
        """Execute Layer 5 quarantine (MAC-based)."""
        victim_device_id = data.get("device_id")
        victim = self.registry.get_device(victim_device_id)
        
        if victim and victim.mac:
            self.quarantine.block_mac(victim.mac)
            # Also notify via Redis that device is quarantined
            self.registry.upsert_device(mac=victim.mac, is_quarantined=1)

    def _handle_block(self, data: Dict[str, Any], fast_drop: bool = False):
        """Block attacker IPs using nftables or XDP."""
        attacker_ips = data.get("indicators", [])
        
        for ip in attacker_ips:
            if fast_drop and self.xdp_firewall.bpf:
                self.xdp_firewall.add_to_blacklist(ip)
            else:
                self.nft_manager.block_ip(ip)

if __name__ == "__main__":
    engine = ResponseEngine()
    engine.run()
