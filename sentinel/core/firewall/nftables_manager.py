"""
SENTINEL Layer 5 — Nftables Manager

Handles nftables rule injection for redirection and blocking.
"""

import subprocess
import structlog
from typing import Optional

logger = structlog.get_logger(__name__)

class NftablesManager:
    """
    Interface for managing nftables rules via subprocess.
    """
    def __init__(self):
        self._setup_base_table()

    def _setup_base_table(self):
        """Initialize the SENTINEL table and chains."""
        try:
            # Create table
            subprocess.run(["nft", "add", "table", "inet", "sentinel"], check=True)
            
            # Create chains
            subprocess.run(["nft", "add", "chain", "inet", "sentinel", "prerouting", "{ type nat hook prerouting priority dstnat; }"], check=True)
            subprocess.run(["nft", "add", "chain", "inet", "sentinel", "postrouting", "{ type nat hook postrouting priority srcnat; }"], check=True)
            subprocess.run(["nft", "add", "chain", "inet", "sentinel", "input", "{ type filter hook input priority filter; }"], check=True)
            subprocess.run(["nft", "add", "chain", "inet", "sentinel", "forward", "{ type filter hook forward priority filter; }"], check=True)
            
            logger.info("nftables_base_setup_complete")
        except subprocess.CalledProcessError as e:
            logger.error("nftables_setup_failed", error=str(e))

    def redirect_traffic(self, attacker_ip: str, victim_ip: str, honeypot_ip: str):
        """
        Redirect all traffic from an attacker intended for a victim to a honeypot.
        """
        try:
            # Add DNAT rule in prerouting
            # Match traffic from attacker to victim, change destination to honeypot
            rule = f"ip saddr {attacker_ip} ip daddr {victim_ip} dnat to {honeypot_ip}"
            subprocess.run(["nft", "add", "rule", "inet", "sentinel", "prerouting", rule], check=True)
            
            # Add SNAT/Masquerade in postrouting to ensure return traffic goes back through SENTINEL 
            # (If victim and attacker are in same subnet, this is crucial)
            masq_rule = f"ip saddr {attacker_ip} ip daddr {honeypot_ip} masquerade"
            subprocess.run(["nft", "add", "rule", "inet", "sentinel", "postrouting", masq_rule], check=True)
            
            logger.warning("traffic_redirected", attacker=attacker_ip, victim=victim_ip, honeypot=honeypot_ip)
            return True
        except subprocess.CalledProcessError as e:
            logger.error("redirect_failed", error=str(e))
            return False

    def block_ip(self, ip: str):
        """Block all traffic from an IP."""
        try:
            subprocess.run(["nft", "add", "rule", "inet", "sentinel", "input", "ip saddr", ip, "drop"], check=True)
            subprocess.run(["nft", "add", "rule", "inet", "sentinel", "forward", "ip saddr", ip, "drop"], check=True)
            logger.warning("ip_blocked", ip=ip)
            return True
        except subprocess.CalledProcessError as e:
            logger.error("block_failed", error=str(e))
            return False

    def flush_rules(self):
        """Clear all SENTINEL rules."""
        try:
            subprocess.run(["nft", "flush", "table", "inet", "sentinel"], check=True)
            logger.info("nftables_rules_flushed")
        except subprocess.CalledProcessError as e:
            logger.error("flush_failed", error=str(e))
