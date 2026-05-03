"""
SENTINEL Layer 5 — Quarantine Manager

Handles Link-Layer (L2) isolation using MAC blocking and ARP spoofing.
"""

import subprocess
import structlog
from scapy.all import send, ARP, Ether
from typing import Optional

logger = structlog.get_logger(__name__)

class QuarantineManager:
    """
    Advanced device isolation at the MAC and ARP levels.
    """
    def __init__(self, interface: str = "wlan0"):
        self.interface = interface
        self.nft_path = "/usr/sbin/nft"

    def block_mac(self, mac: str):
        """Hard-block a device MAC address using nftables."""
        try:
            # Add rule to drop all traffic from/to this MAC in the forward chain (bridge)
            # and input chain (local host)
            subprocess.run([
                self.nft_path, "add", "rule", "inet", "sentinel", "forward", 
                "ether", "saddr", mac, "drop"
            ], check=True)
            subprocess.run([
                self.nft_path, "add", "rule", "inet", "sentinel", "input", 
                "ether", "saddr", mac, "drop"
            ], check=True)
            
            logger.warning("mac_blocked", mac=mac)
            return True
        except subprocess.CalledProcessError as e:
            logger.error("mac_block_failed", mac=mac, error=str(e))
            return False

    def isolate_via_arp(self, target_ip: str, target_mac: str, gateway_ip: str):
        """
        Perform ARP isolation (soft quarantine).
        Tells the target that the gateway's MAC is non-existent.
        """
        try:
            # Poison the target's ARP cache for the gateway
            # We use a fake MAC address
            fake_mac = "00:de:ad:be:ef:00"
            pkt = Ether(dst=target_mac)/ARP(op=2, pdst=target_ip, hwdst=target_mac, psrc=gateway_ip, hwsrc=fake_mac)
            
            # Send once (in a real scenario, this would be a background loop)
            send(pkt, iface=self.interface, verbose=False)
            
            logger.warning("arp_isolation_packet_sent", target=target_ip, gateway=gateway_ip)
            return True
        except Exception as e:
            logger.error("arp_isolation_failed", target=target_ip, error=str(e))
            return False

    def unblock_mac(self, mac: str):
        """Remove MAC blocking rules (requires rule handle tracking or flushing)."""
        # For simplicity in this prototype, we'll just flush the table if needed
        # or rely on the user to flush.
        logger.info("mac_unblock_requested", mac=mac, hint="Flush sentinel table to clear")
