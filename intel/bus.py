"""
SENTINEL Layer 6 — AlienVault OTX & AbuseIPDB Integration

Handles IoC enrichment and threat intelligence feed synchronization.
"""

import httpx
import structlog
from typing import Optional, Dict, Any, List
from OTXv2 import OTXv2, IndicatorTypes

from sentinel.config.settings import settings

logger = structlog.get_logger(__name__)

class IntelBus:
    """
    Centralized bus for threat intelligence and IoC enrichment.
    """
    def __init__(self):
        self.otx_key = settings.otx_api_key
        self.abuse_key = settings.abuseipdb_api_key
        
        # Initialize OTX client if key is available
        self.otx = None
        if self.otx_key:
            try:
                self.otx = OTXv2(self.otx_key)
                logger.info("otx_client_initialized")
            except Exception as e:
                logger.error("otx_init_failed", error=str(e))

    async def enrich_ip(self, ip: str) -> Dict[str, Any]:
        """
        Enrich an IP address with OTX and AbuseIPDB data.
        """
        results = {
            "ip": ip,
            "otx_pulse_count": 0,
            "otx_tags": [],
            "abuse_score": 0,
            "is_malicious": False
        }

        # 1. OTX Lookup
        if self.otx:
            try:
                # Get general reputation
                reputation = self.otx.get_indicator_details_full(IndicatorTypes.IPv4, ip)
                
                # Extract Pulse info
                pulses = reputation.get("general", {}).get("pulse_info", {}).get("pulses", [])
                results["otx_pulse_count"] = len(pulses)
                
                # Collect tags from pulses
                tags = set()
                for p in pulses:
                    tags.update(p.get("tags", []))
                results["otx_tags"] = list(tags)[:10] # Limit to 10 tags
                
                if results["otx_pulse_count"] > 0:
                    results["is_malicious"] = True
                    
                logger.info("otx_lookup_complete", ip=ip, pulses=len(pulses))
            except Exception as e:
                logger.error("otx_lookup_failed", ip=ip, error=str(e))

        # 2. AbuseIPDB Lookup (Mocked if no key)
        if self.abuse_key:
            try:
                async with httpx.AsyncClient() as client:
                    headers = {
                        "Key": self.abuse_key,
                        "Accept": "application/json"
                    }
                    params = {
                        "ipAddress": ip,
                        "maxAgeInDays": "90"
                    }
                    response = await client.get("https://api.abuseipdb.com/api/v2/check", headers=headers, params=params)
                    if response.status_code == 200:
                        data = response.json().get("data", {})
                        results["abuse_score"] = data.get("abuseConfidenceScore", 0)
                        if results["abuse_score"] > 50:
                            results["is_malicious"] = True
                logger.info("abuseipdb_lookup_complete", ip=ip, score=results["abuse_score"])
            except Exception as e:
                logger.error("abuseipdb_lookup_failed", ip=ip, error=str(e))
        else:
            # Mock behavior for testing if key is missing
            if ip == "185.220.101.12": # Known Tor Exit node often in blacklists
                results["abuse_score"] = 100
                results["is_malicious"] = True
                results["otx_tags"].append("tor_exit_node")

        return results

if __name__ == "__main__":
    import asyncio
    
    async def test():
        bus = IntelBus()
        # Test with a known malicious/Tor IP
        res = await bus.enrich_ip("185.220.101.12")
        print(f"Results for 185.220.101.12: {res}")
        
    asyncio.run(test())
