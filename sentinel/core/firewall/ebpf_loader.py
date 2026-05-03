"""
SENTINEL Layer 5 — eBPF/XDP Loader

Loads the XDP fast-drop program and manages the blacklist map.
"""

import os
import ctypes
import socket
import structlog
from bcc import BPF
from typing import List

from sentinel.config.settings import settings

logger = structlog.get_logger(__name__)

class XDPFirewall:
    """
    Manages the high-performance XDP firewall.
    """
    def __init__(self, interface: str = None):
        self.interface = interface or settings.capture_interface
        self.bpf = None
        self.blacklist_map = None
        
        # Load the C code
        c_file = os.path.join(os.path.dirname(__file__), "xdp_drop.c")
        try:
            with open(c_file, "r") as f:
                c_code = f.read()
            
            self.bpf = BPF(text=c_code)
            self.fn = self.bpf.load_func("xdp_drop_func", BPF.XDP)
            self.blacklist_map = self.bpf.get_table("blacklist")
            
            logger.info("ebpf_program_compiled", interface=self.interface)
        except Exception as e:
            logger.error("ebpf_load_failed", error=str(e))
            logger.warning("ebpf_mock_mode_active", reason="Kernel headers missing or incompatible")
            self.bpf = None
            self.blacklist_map = {} # Mock map for testing logic

    def attach(self):
        """Attach the XDP program to the interface."""
        if not self.bpf:
            return False
        
        try:
            self.bpf.attach_xdp(self.interface, self.fn, flags=0)
            logger.info("xdp_attached", interface=self.interface)
            return True
        except Exception as e:
            logger.error("xdp_attach_failed", error=str(e))
            return False

    def detach(self):
        """Detach the XDP program."""
        if not self.bpf:
            return
        
        try:
            self.bpf.remove_xdp(self.interface, flags=0)
            logger.info("xdp_detached", interface=self.interface)
        except Exception as e:
            logger.error("xdp_detach_failed", error=str(e))

    def add_to_blacklist(self, ip_str: str):
        """Add an IPv4 address to the fast-drop blacklist."""
        if self.blacklist_map is None:
            return
        
        try:
            # Convert IP string to network byte order u32
            ip_u32 = ctypes.c_uint32(
                socket.ntohl(struct.unpack("!I", socket.inet_aton(ip_str))[0])
            )
            self.blacklist_map[ip_u32] = ctypes.c_uint64(0)
            logger.warning("ip_added_to_xdp_blacklist", ip=ip_str)
        except Exception as e:
            logger.error("xdp_blacklist_add_failed", ip=ip_str, error=str(e))

    def get_stats(self):
        """Get drop statistics from the BPF map."""
        stats = {}
        if self.blacklist_map is None:
            return stats
            
        for key, value in self.blacklist_map.items():
            ip_str = socket.inet_ntoa(struct.pack("!I", socket.htonl(key.value)))
            stats[ip_str] = value.value
        return stats

import struct
if __name__ == "__main__":
    # Test loading
    fw = XDPFirewall(interface="wlan0")
    if fw.attach():
        print("XDP Firewall is active on wlan0. Press Ctrl+C to stop.")
        try:
            import time
            while True:
                time.sleep(1)
        except KeyboardInterrupt:
            fw.detach()
