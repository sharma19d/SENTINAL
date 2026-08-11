"""
SENTINEL — Network Identity

Determines *which physical network* the appliance is currently attached to.

Everything SENTINEL records — devices, threats, firewall rules — is only
meaningful in the context of one network. Without an identity for that
network the registry is a single flat list, so moving the appliance to a
different Wi-Fi/LAN leaves the dashboard reporting hardware that is no
longer reachable, mixed in with hardware that is.

Identity is keyed on the **default gateway's MAC address**:

  * unique per physical router, so two networks that both use
    192.168.1.0/24 (extremely common on consumer routers) stay distinct —
    subnet alone is not sufficient;
  * stable across reboots and DHCP lease changes, unlike the appliance's
    own IP;
  * works for both Wi-Fi and wired uplinks, unlike SSID/BSSID;
  * readable without extra privileges (default route + ARP/neighbour table).
"""

from __future__ import annotations

import ipaddress
import re
import subprocess
from dataclasses import dataclass, asdict
from typing import Optional

import structlog

logger = structlog.get_logger(__name__)

_UNKNOWN_MACS = {"", "00:00:00:00:00:00", "ff:ff:ff:ff:ff:ff"}


@dataclass(frozen=True)
class NetworkIdentity:
    """The network the appliance is currently attached to."""

    network_id: str          # normalised gateway MAC — the stable key
    gateway_ip: str
    gateway_mac: str
    interface: str
    subnet: str              # CIDR, e.g. "192.168.1.0/24"
    local_ip: str

    def to_dict(self) -> dict:
        return asdict(self)


def _run(cmd: list[str], timeout: float = 3.0) -> str:
    try:
        result = subprocess.run(
            cmd, capture_output=True, text=True, timeout=timeout, check=False
        )
        return result.stdout
    except (subprocess.TimeoutExpired, FileNotFoundError, OSError):
        return ""


def _default_route() -> tuple[Optional[str], Optional[str]]:
    """Return (gateway_ip, interface) for the default route, preferring the
    lowest-metric route so a VM/docker uplink doesn't shadow the real one."""
    output = _run(["ip", "-4", "route", "show", "default"])

    best: tuple[int, Optional[str], Optional[str]] = (10**9, None, None)
    for line in output.splitlines():
        match = re.search(r"default via (\S+) dev (\S+)", line)
        if not match:
            continue
        gateway_ip, interface = match.group(1), match.group(2)

        metric_match = re.search(r"metric (\d+)", line)
        metric = int(metric_match.group(1)) if metric_match else 0

        if metric < best[0]:
            best = (metric, gateway_ip, interface)

    return best[1], best[2]


def _mac_for_ip(ip: str, interface: Optional[str] = None) -> Optional[str]:
    """Resolve an IP to its MAC via the kernel neighbour table."""
    output = _run(["ip", "neigh", "show", ip])
    match = re.search(r"lladdr (\S+)", output)
    if match:
        return match.group(1).lower()

    # Neighbour entry may be absent if we haven't spoken to the gateway
    # recently. A single ping repopulates it.
    if interface:
        _run(["ping", "-c", "1", "-W", "1", "-I", interface, ip], timeout=4.0)
    else:
        _run(["ping", "-c", "1", "-W", "1", ip], timeout=4.0)

    output = _run(["ip", "neigh", "show", ip])
    match = re.search(r"lladdr (\S+)", output)
    return match.group(1).lower() if match else None


def _local_addr_and_subnet(interface: str) -> tuple[Optional[str], Optional[str]]:
    """Return (local_ip, subnet_cidr) for an interface."""
    output = _run(["ip", "-4", "-o", "addr", "show", interface])
    match = re.search(r"inet (\S+)", output)
    if not match:
        return None, None

    cidr = match.group(1)
    try:
        iface = ipaddress.ip_interface(cidr)
        return str(iface.ip), str(iface.network)
    except ValueError:
        return None, None


def detect_current_network() -> Optional[NetworkIdentity]:
    """
    Detect the network the appliance is attached to right now.

    Returns None when there is no usable uplink (no default route, or the
    gateway MAC cannot be resolved) — callers should treat that as
    "network unknown" rather than assuming a previous network is still
    valid.
    """
    gateway_ip, interface = _default_route()
    if not gateway_ip or not interface:
        logger.warning("network_identity_no_default_route")
        return None

    gateway_mac = _mac_for_ip(gateway_ip, interface)
    if not gateway_mac or gateway_mac in _UNKNOWN_MACS:
        logger.warning(
            "network_identity_gateway_mac_unresolved",
            gateway_ip=gateway_ip,
            interface=interface,
        )
        return None

    local_ip, subnet = _local_addr_and_subnet(interface)
    if not subnet:
        logger.warning("network_identity_no_subnet", interface=interface)
        return None

    return NetworkIdentity(
        network_id=gateway_mac,
        gateway_ip=gateway_ip,
        gateway_mac=gateway_mac,
        interface=interface,
        subnet=subnet,
        local_ip=local_ip or "",
    )


def ip_in_subnet(ip: Optional[str], subnet: Optional[str]) -> bool:
    """True when `ip` falls inside `subnet`. Used to decide whether a stored
    record can still be relevant on the current network."""
    if not ip or not subnet:
        return False
    try:
        return ipaddress.ip_address(ip) in ipaddress.ip_network(subnet, strict=False)
    except ValueError:
        return False


if __name__ == "__main__":
    identity = detect_current_network()
    if identity is None:
        print("No network detected (no default route or unresolved gateway).")
    else:
        for key, value in identity.to_dict().items():
            print(f"  {key:<12} {value}")
