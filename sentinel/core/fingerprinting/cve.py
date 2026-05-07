"""
SENTINEL Layer 2 — CVE Scanner

Interfaces with the NIST NVD (National Vulnerability Database) API to
identify known vulnerabilities associated with discovered devices.
"""

from __future__ import annotations

import asyncio
import time
from typing import Any, Optional

import httpx
import structlog

from sentinel.config.settings import settings

logger = structlog.get_logger(__name__)


class CVEScanner:
    """
    Client for the NIST NVD API 2.0.
    Fetches CVE records based on device fingerprints (vendor, OS, services).
    """

    BASE_URL = "https://services.nvd.nist.gov/rest/json/cves/2.0"

    def __init__(self, api_key: Optional[str] = None):
        self.api_key = api_key or settings.nvd_api_key
        self._headers = {"apiKey": self.api_key} if self.api_key else {}
        self._last_request_time = 0.0
        # Rate limit: 50 requests per 30 seconds with API key, 5 without
        self._request_delay = 0.6 if self.api_key else 6.0

    async def _rate_limit(self):
        """Ensure we don't exceed NVD API rate limits."""
        elapsed = time.time() - self._last_request_time
        if elapsed < self._request_delay:
            await asyncio.sleep(self._request_delay - elapsed)
        self._last_request_time = time.time()

    async def search_cves(self, keyword: str, limit: int = 10) -> list[dict[str, Any]]:
        """
        Search for CVEs using a keyword (e.g., 'Hikvision', 'TP-Link').
        """
        if not keyword or keyword == "Unknown":
            return []

        params = {
            "keywordSearch": keyword,
            "resultsPerPage": limit
        }

        logger.info("nvd_api_search", keyword=keyword)
        
        try:
            await self._rate_limit()
            async with httpx.AsyncClient(headers=self._headers, timeout=10.0) as client:
                resp = await client.get(self.BASE_URL, params=params)
                if resp.status_code == 200:
                    return self._parse_vulnerabilities(resp.json())
                elif resp.status_code == 403:
                    logger.error("nvd_api_forbidden", msg="Invalid API key or rate limit exceeded")
                else:
                    logger.warning("nvd_api_error", status=resp.status_code)
        except Exception as e:
            logger.error("nvd_api_request_failed", error=str(e))
        
        return []

    def _parse_vulnerabilities(self, data: dict[str, Any]) -> list[dict[str, Any]]:
        """Extract relevant fields from NVD API response."""
        results = []
        vulnerabilities = data.get("vulnerabilities", [])
        
        for v in vulnerabilities:
            cve = v.get("cve", {})
            cve_id = cve.get("id")
            
            # Extract CVSS score (prefer v3.1 if available)
            metrics = cve.get("metrics", {})
            cvss_score = 0.0
            
            # Check v3.1 metrics
            v31 = metrics.get("cvssMetricV31", [])
            if v31:
                cvss_score = v31[0].get("cvssData", {}).get("baseScore", 0.0)
            else:
                # Fallback to v2
                v2 = metrics.get("cvssMetricV2", [])
                if v2:
                    cvss_score = v2[0].get("cvssData", {}).get("baseScore", 0.0)

            # Extract description
            descriptions = cve.get("descriptions", [])
            desc_text = "No description available."
            for d in descriptions:
                if d.get("lang") == "en":
                    desc_text = d.get("value")
                    break
            
            results.append({
                "cve_id": cve_id,
                "cvss_score": cvss_score,
                "description": desc_text[:200] + "..." if len(desc_text) > 200 else desc_text
            })
            
        return results

    async def get_device_vulnerabilities(self, vendor: str, model: Optional[str] = None) -> list[dict[str, Any]]:
        """
        Comprehensive search for a device based on available info.
        """
        query = vendor
        if model:
            query = f"{vendor} {model}"
            
        return await self.search_cves(query)
