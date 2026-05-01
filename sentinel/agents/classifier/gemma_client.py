"""
SENTINEL Agent 2 — Gemma 4 Client

Handles communication with the local Ollama instance for threat classification.
"""

import json
import httpx
import structlog
from typing import Optional, Dict, Any

from sentinel.config.settings import settings

logger = structlog.get_logger(__name__)

class GemmaClassifier:
    """
    Interface for Gemma 4 via Ollama REST API.
    """
    def __init__(self, model: str = None, base_url: str = None):
        self.model = model or settings.llm_model
        ollama_url = base_url or settings.ollama_base_url
        self.base_url = f"{ollama_url.rstrip('/')}/api/generate"
        self.system_prompt = (
            "You are a SENTINEL Cybersecurity AI Analyst specializing in IoT security. "
            "Your task is to classify network anomalies into MITRE ATT&CK for ICS/IoT tactics and techniques. "
            "You will be provided with an anomaly event containing device metadata and traffic stats. "
            "Analyze the risk and return a structured JSON response. "
            "Return ONLY valid JSON. No conversational text. No markdown blocks."
        )

    async def classify(self, event_context: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """
        Send threat context to Gemma 4 and parse the classification JSON.
        """
        prompt = self._build_prompt(event_context)
        
        payload = {
            "model": self.model,
            "prompt": prompt,
            "system": self.system_prompt,
            "stream": False,
            "format": "json"
        }

        try:
            async with httpx.AsyncClient(timeout=60.0) as client:
                response = await client.post(self.base_url, json=payload)
                response.raise_for_status()
                
                result = response.json()
                raw_response = result.get("response", "")
                
                logger.debug("gemma_raw_response", response=raw_response)
                
                # Parse JSON from response string
                return json.loads(raw_response)
                
        except json.JSONDecodeError as je:
            logger.error("gemma_json_parse_failed", error=str(je), raw=raw_response)
            return None
        except Exception as e:
            logger.error("gemma_classification_failed", error=str(e))
            return None

    def _build_prompt(self, ctx: Dict[str, Any]) -> str:
        """
        Format the anomaly and device context into a prompt.
        """
        return f"""
ANOMALY EVENT:
- Device: {ctx.get('device_id')} ({ctx.get('vendor', 'Unknown')})
- IP: {ctx.get('src_ip')} -> {ctx.get('dst_ip')}
- Protocol: {ctx.get('protocol')}
- Anomaly Score: {ctx.get('anomaly_score')}
- Alert Level: {ctx.get('alert_level')}
- Known Vulnerabilities (CVEs): {ctx.get('cves', 'None')}

TASK:
Classify this behavior using MITRE ATT&CK. Identify the Tactic, Technique ID, Severity (1-10), and provide a brief Summary.
Recommend an action: "monitor", "honeypot", or "quarantine".

EXPECTED JSON SCHEMA:
{{
  "tactic": "string",
  "technique_id": "string",
  "confidence": float,
  "severity": int,
  "summary": "string",
  "recommended_action": "string"
}}
"""
