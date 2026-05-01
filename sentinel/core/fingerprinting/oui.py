"""
SENTINEL Layer 2 — OUI Lookup

Provides MAC address vendor identification using the IEEE OUI database.
"""

from __future__ import annotations
from sentinel.core.capture.utils import mac_to_vendor

def get_vendor(mac_address: str) -> str:
    """
    Identifies the manufacturer of a device based on its MAC address.
    
    Args:
        mac_address: MAC address (e.g., 'AA:BB:CC:DD:EE:FF')
        
    Returns:
        Vendor name or 'Unknown'.
    """
    return mac_to_vendor(mac_address)
