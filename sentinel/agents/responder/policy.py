"""
SENTINEL Agent 3 — Policy Loader

Loads and parses the YAML response policy.
"""

import yaml
import structlog
from typing import List, Dict, Any, Optional

logger = structlog.get_logger(__name__)

class ResponsePolicy:
    """
    Manages security response rules.
    """
    def __init__(self, policy_path: str = "sentinel/config/policy.yaml"):
        self.policy_path = policy_path
        self.rules = []
        self.load()

    def load(self):
        try:
            with open(self.policy_path, "r") as f:
                config = yaml.safe_load(f)
                self.rules = config.get("rules", [])
            logger.info("policy_loaded", path=self.policy_path, rules_count=len(self.rules))
        except Exception as e:
            logger.error("policy_load_failed", error=str(e))
            self.rules = []

    def get_action_for_severity(self, severity: int) -> Dict[str, Any]:
        """
        Find the matching rule for a given severity level.
        """
        for rule in self.rules:
            if rule["severity_min"] <= severity <= rule["severity_max"]:
                return {
                    "rule_name": rule["name"],
                    "actions": rule["actions"],
                    "require_confirmation": rule.get("require_confirmation", False)
                }
        
        # Default fallback
        return {
            "rule_name": "default_log",
            "actions": ["log_event"],
            "require_confirmation": False
        }
