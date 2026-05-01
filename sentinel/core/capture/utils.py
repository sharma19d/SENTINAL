"""
SENTINEL Layer 1 — Utilities

Helper functions used across the capture engine:
  • MAC → vendor OUI lookup
  • Bidirectional flow ID generation
  • Network interface detection
  • Timestamp formatting
"""

from __future__ import annotations

import hashlib
import json
import socket
import struct
import time
from datetime import datetime, timezone
from functools import lru_cache
from pathlib import Path
from typing import Optional

import structlog

logger = structlog.get_logger(__name__)

# Path to the bundled OUI vendor database
_OUI_DB_PATH = Path(__file__).parent.parent.parent.parent / "data" / "oui_lookup.json"

# In-memory cache for the OUI database (loaded once)
_oui_db: Optional[dict[str, str]] = None


# ── MAC Vendor Lookup ────────────────────────────────────────────────

def _load_oui_db() -> dict[str, str]:
    """
    Load the IEEE OUI database from the bundled JSON file.
    Format: {"AA:BB:CC": "Vendor Name", ...}
    Keys are uppercase 3-byte OUI prefixes with colons.
    """
    global _oui_db
    if _oui_db is not None:
        return _oui_db

    if _OUI_DB_PATH.exists():
        try:
            with open(_OUI_DB_PATH, "r", encoding="utf-8") as f:
                _oui_db = json.load(f)
            logger.info("oui_db_loaded", entries=len(_oui_db), path=str(_OUI_DB_PATH))
            return _oui_db
        except (json.JSONDecodeError, OSError) as e:
            logger.warning("oui_db_load_failed", error=str(e))
    else:
        logger.warning("oui_db_not_found", path=str(_OUI_DB_PATH))

    _oui_db = {}
    return _oui_db


def mac_to_vendor(mac_address: str) -> str:
    """
    Look up the vendor/manufacturer name for a MAC address
    using the IEEE OUI (Organizationally Unique Identifier) database.

    Args:
        mac_address: MAC in any common format
                     (aa:bb:cc:dd:ee:ff, AA-BB-CC-DD-EE-FF, aabbccddeeff)

    Returns:
        Vendor name string, or "Unknown" if not found.
    """
    if not mac_address:
        return "Unknown"

    # Normalize: strip separators, uppercase, take first 6 hex chars (OUI)
    clean = mac_address.upper().replace(":", "").replace("-", "").replace(".", "")
    if len(clean) < 6:
        return "Unknown"

    # Format as OUI prefix with colons: "AA:BB:CC"
    oui = f"{clean[0:2]}:{clean[2:4]}:{clean[4:6]}"

    db = _load_oui_db()
    return db.get(oui, "Unknown")


# ── Flow ID Generation ───────────────────────────────────────────────

def generate_flow_id(
    src_ip: str,
    dst_ip: str,
    src_port: Optional[int],
    dst_port: Optional[int],
    protocol: str,
) -> str:
    """
    Generate a deterministic, bidirectional flow ID from the 5-tuple.

    The ID is the same regardless of direction:
        flow_id(A→B) == flow_id(B→A)

    This is achieved by sorting the (ip, port) pairs before hashing.

    Args:
        src_ip: Source IP address
        dst_ip: Destination IP address
        src_port: Source port (None for ICMP/non-port protocols)
        dst_port: Destination port (None for ICMP/non-port protocols)
        protocol: L4 protocol string (TCP, UDP, ICMP, etc.)

    Returns:
        A 16-character hex string (truncated SHA-256).
    """
    # Normalize ports to 0 if None
    sp = src_port if src_port is not None else 0
    dp = dst_port if dst_port is not None else 0

    # Sort endpoints to ensure bidirectional consistency
    endpoint_a = (src_ip, sp)
    endpoint_b = (dst_ip, dp)
    if endpoint_a > endpoint_b:
        endpoint_a, endpoint_b = endpoint_b, endpoint_a

    key = f"{endpoint_a[0]}:{endpoint_a[1]}-{endpoint_b[0]}:{endpoint_b[1]}-{protocol}"
    return hashlib.sha256(key.encode()).hexdigest()[:16]


def canonicalize_flow_tuple(
    src_ip: str,
    dst_ip: str,
    src_port: Optional[int],
    dst_port: Optional[int],
) -> tuple[str, str, Optional[int], Optional[int], bool]:
    """
    Canonicalize the direction of a flow so lower IP is always 'src'.
    Returns (canon_src_ip, canon_dst_ip, canon_src_port, canon_dst_port, is_reversed).

    The `is_reversed` flag indicates whether the original packet was
    in the "backward" direction relative to the canonical flow.
    """
    sp = src_port if src_port is not None else 0
    dp = dst_port if dst_port is not None else 0

    if (src_ip, sp) > (dst_ip, dp):
        return dst_ip, src_ip, dst_port, src_port, True
    return src_ip, dst_ip, src_port, dst_port, False


# ── Network Interface Helpers ────────────────────────────────────────

def get_available_interfaces() -> list[dict[str, str]]:
    """
    List available network interfaces on the system.
    Returns a list of dicts with 'name' and 'description' keys.

    Uses Scapy's interface listing for cross-platform compatibility.
    """
    try:
        from scapy.interfaces import get_if_list, get_if_hwaddr
        interfaces = []
        for iface_name in get_if_list():
            try:
                mac = get_if_hwaddr(iface_name)
            except Exception:
                mac = "N/A"
            interfaces.append({
                "name": iface_name,
                "mac": mac,
            })
        return interfaces
    except ImportError:
        logger.warning("scapy_not_installed", msg="Cannot list interfaces without Scapy")
        return []


def get_default_interface() -> str:
    """
    Auto-detect the best network interface for capturing.

    Priority:
        1. br0 (Bridge interface — target for transparent bridge mode)
        2. wlan0 (Wi-Fi — common for home IoT monitoring)
        3. eth0 (Ethernet)
        4. First non-loopback interface found
        5. Fallback to "any" (Linux capture-all pseudo-interface)
    """
    try:
        from scapy.interfaces import get_if_list
        ifaces = get_if_list()
    except ImportError:
        return "any"

    # Priority order
    for preferred in ["br0", "wlan0", "wlan1", "eth0", "eth1", "ens33", "enp0s3"]:
        if preferred in ifaces:
            return preferred

    # First non-loopback
    for iface in ifaces:
        if iface != "lo" and not iface.startswith("docker") and not iface.startswith("veth"):
            return iface

    return "any"


def validate_interface(name: str) -> bool:
    """Check if a network interface exists and is available."""
    if name == "auto" or name == "any":
        return True
    try:
        from scapy.interfaces import get_if_list
        return name in get_if_list()
    except ImportError:
        return True  # Assume valid if we can't check


# ── Timestamp Helpers ────────────────────────────────────────────────

def now_epoch() -> float:
    """Current time as UTC epoch float."""
    return time.time()


def epoch_to_iso(epoch: float) -> str:
    """Convert UTC epoch float to ISO 8601 string."""
    return datetime.fromtimestamp(epoch, tz=timezone.utc).isoformat()


def format_duration(seconds: float) -> str:
    """Format a duration in seconds to a human-readable string."""
    if seconds < 1:
        return f"{seconds * 1000:.1f}ms"
    if seconds < 60:
        return f"{seconds:.1f}s"
    if seconds < 3600:
        minutes = int(seconds // 60)
        secs = seconds % 60
        return f"{minutes}m {secs:.0f}s"
    hours = int(seconds // 3600)
    minutes = int((seconds % 3600) // 60)
    return f"{hours}h {minutes}m"


# ── IP Helpers ───────────────────────────────────────────────────────

def is_private_ip(ip: str) -> bool:
    """Check if an IP address is in a private/reserved range."""
    try:
        packed = socket.inet_aton(ip)
        addr = struct.unpack("!I", packed)[0]

        # 10.0.0.0/8
        if (addr >> 24) == 10:
            return True
        # 172.16.0.0/12
        if (addr >> 20) == (172 << 4 | 1):  # 172.16-31.x.x
            first_two = addr >> 16
            if 0xAC10 <= first_two <= 0xAC1F:
                return True
        # 192.168.0.0/16
        if (addr >> 16) == 0xC0A8:
            return True
        # 127.0.0.0/8
        if (addr >> 24) == 127:
            return True
        # 169.254.0.0/16 (link-local)
        if (addr >> 16) == 0xA9FE:
            return True

        return False
    except (socket.error, struct.error):
        return False


def is_broadcast_mac(mac: str) -> bool:
    """Check if a MAC address is the broadcast address."""
    clean = mac.upper().replace(":", "").replace("-", "")
    return clean == "FFFFFFFFFFFF"


def is_multicast_mac(mac: str) -> bool:
    """Check if a MAC address is a multicast address (bit 0 of first byte is set)."""
    clean = mac.replace(":", "").replace("-", "")
    if len(clean) < 2:
        return False
    first_byte = int(clean[0:2], 16)
    return bool(first_byte & 0x01)
