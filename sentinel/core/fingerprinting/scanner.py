"""
SENTINEL Layer 2 — Active Scanner

Uses Nmap to perform active port scanning and service identification
on discovered devices. Helps refine the device fingerprint and
identify potentially dangerous open ports.
"""

from __future__ import annotations

import asyncio
import json
from typing import Any, Optional

import nmap
import structlog

from sentinel.core.fingerprinting.registry import DeviceRegistry

logger = structlog.get_logger(__name__)


class ActiveScanner:
    """
    Wrapper for python-nmap to perform targeted device scans.
    """

    def __init__(self, registry: Optional[DeviceRegistry] = None):
        self.registry = registry or DeviceRegistry()
        self.nm = nmap.PortScanner()

    async def scan_device(self, ip: str, device_id: Optional[str] = None) -> dict[str, Any]:
        """
        Perform a service scan on a single IP address.
        """
        if not ip or ip == "0.0.0.0":
            return {}

        logger.info("active_scan_starting", ip=ip)
        
        # Run nmap in a thread pool since it's blocking
        loop = asyncio.get_event_loop()
        try:
            # -sV: service version detection
            # -T4: aggressive timing for faster results
            # -p: targeted common IoT ports
            ports = "21,22,23,25,53,80,111,139,443,445,1883,1900,3306,5353,5683,8080,8443,8883"
            
            scan_result = await loop.run_in_executor(
                None, 
                lambda: self.nm.scan(ip, ports, arguments="-sV -T4")
            )
            
            if ip in scan_result["scan"]:
                nmap_data = scan_result["scan"][ip]
                open_ports = []
                
                for proto in ["tcp", "udp"]:
                    if proto in nmap_data:
                        for port, info in nmap_data[proto].items():
                            if info["state"] == "open":
                                open_ports.append({
                                    "port": port,
                                    "protocol": proto,
                                    "service": info["name"],
                                    "product": info.get("product", ""),
                                    "version": info.get("version", ""),
                                })
                
                os_guess = ""
                if "osmatch" in nmap_data and nmap_data["osmatch"]:
                    os_guess = nmap_data["osmatch"][0]["name"]

                results = {
                    "open_ports": open_ports,
                    "os_guess": os_guess
                }

                if device_id:
                    self.registry.upsert_device(
                        mac="", 
                        device_id=device_id,
                        open_ports=open_ports,
                        os_guess=os_guess if os_guess else None
                    )
                
                logger.info("active_scan_complete", ip=ip, ports_found=len(open_ports))
                return results

        except Exception as e:
            logger.error("active_scan_failed", ip=ip, error=str(e))
            
        return {}


async def main():
    import sys
    if len(sys.argv) < 2:
        print("Usage: python -m sentinel.core.fingerprinting.scanner <ip>")
        return
    
    scanner = ActiveScanner()
    res = await scanner.scan_device(sys.argv[1])
    print(json.dumps(res, indent=2))


if __name__ == "__main__":
    asyncio.run(main())
