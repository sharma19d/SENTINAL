"""
SENTINEL — Honeypot Monitor (Layer 4 → Layer 3/5 bridge)

Closes the loop between deception and detection.

Cowrie records attacker sessions to a JSON log, but nothing consumed that
log back into the threat pipeline — so an attacker could brute-force and
own the honeypot while the Threats feed stayed empty and the firewall did
nothing. Interaction with a honeypot is, by definition, hostile: a honeypot
has no legitimate users, so any connection to it is an attacker.

This agent tails the Cowrie log and, for each attacker session, turns that
certainty into action:

  * writes a MITRE ATT&CK-tagged threat event into the registry (so it
    appears in the Threats tab, scoped to the current network);
  * publishes it on `sentinel:threat` so the live dashboard feed and the
    LangGraph responder react to it exactly like any other threat;
  * optionally adds an nftables DROP rule for the attacker IP
    (auto_block_honeypot), publishing the action on `sentinel:actions`.

Severity scales with what the attacker achieved — a failed probe is low, a
successful login with post-exploitation commands is critical.
"""

from __future__ import annotations

import json
import time
import uuid
from pathlib import Path
from typing import Optional

import redis
import structlog

from sentinel.config.settings import settings as app_settings
from sentinel.core.fingerprinting.registry import DeviceRegistry
from sentinel.core.network_identity import detect_current_network

logger = structlog.get_logger(__name__)

COWRIE_LOG = Path("deception/cowrie/log/cowrie.json")
UI_SETTINGS_FILE = Path("data/sentinel_ui_settings.json")

# MITRE ATT&CK for ICS / enterprise techniques that map to honeypot activity.
TECHNIQUE_BRUTE_FORCE = ("T1110", "Credential Access")
TECHNIQUE_VALID_ACCOUNTS = ("T1078", "Initial Access")
TECHNIQUE_EXECUTION = ("T1059", "Execution")
TECHNIQUE_INGRESS = ("T1105", "Command and Control")  # malware download


class HoneypotMonitor:
    def __init__(self, poll_interval: float = 3.0):
        self.redis_client = redis.Redis(
            host=app_settings.redis_host,
            port=app_settings.redis_port,
            db=app_settings.redis_db,
            password=app_settings.redis_password,
            decode_responses=True,
        )
        self.registry = DeviceRegistry(app_settings.db_url)
        self.poll_interval = poll_interval

        self.threat_channel = "sentinel:threat"
        self.action_channel = "sentinel:actions"

        # Sessions already turned into a threat, so re-reading the log (it is
        # append-only and re-scanned each tick) never double-reports.
        self._seen_sessions: set[str] = set()
        # IPs already blocked this run, to avoid a duplicate rule per session.
        self._blocked_ips: set[str] = set()

        self._network = None
        self._network_checked = 0.0

    # ── helpers ──────────────────────────────────────────────────

    def _auto_block_enabled(self) -> bool:
        """Read the live UI setting so the dashboard toggle takes effect."""
        try:
            if UI_SETTINGS_FILE.exists():
                return bool(json.loads(UI_SETTINGS_FILE.read_text()).get("auto_block_honeypot", True))
        except Exception:
            pass
        return True

    def _current_network(self):
        now = time.monotonic()
        if self._network is None or (now - self._network_checked) > 30:
            self._network = detect_current_network()
            self._network_checked = now
        return self._network

    def _parse_sessions(self) -> dict[str, dict]:
        """Rebuild session state from the Cowrie JSON log."""
        sessions: dict[str, dict] = {}
        if not COWRIE_LOG.exists():
            return sessions

        try:
            with open(COWRIE_LOG) as f:
                for line in f:
                    line = line.strip()
                    if not line:
                        continue
                    try:
                        evt = json.loads(line)
                    except json.JSONDecodeError:
                        continue

                    sid = evt.get("session")
                    if not sid:
                        continue

                    s = sessions.setdefault(sid, {
                        "session_id": sid,
                        "src_ip": evt.get("src_ip", ""),
                        "login_attempts": [],
                        "commands": [],
                        "success": False,
                        "closed": False,
                        "start_time": evt.get("timestamp", ""),
                    })

                    eid = evt.get("eventid", "")
                    if evt.get("src_ip"):
                        s["src_ip"] = evt["src_ip"]
                    if eid in ("cowrie.login.failed", "cowrie.login.success"):
                        s["login_attempts"].append({
                            "username": evt.get("username", ""),
                            "password": evt.get("password", ""),
                            "success": eid == "cowrie.login.success",
                        })
                        if eid == "cowrie.login.success":
                            s["success"] = True
                    elif eid == "cowrie.command.input":
                        s["commands"].append(evt.get("input", ""))
                    elif eid == "cowrie.session.closed":
                        s["closed"] = True
        except Exception as e:
            logger.error("cowrie_log_read_failed", error=str(e))

        return sessions

    def _classify(self, session: dict) -> dict:
        """Derive severity + ATT&CK mapping from what the attacker did."""
        attempts = session["login_attempts"]
        commands = session["commands"]
        success = session["success"]
        downloaded_malware = any(
            kw in " ".join(commands).lower()
            for kw in ("wget", "curl", "tftp", "busybox", "mirai", ".sh", "chmod +x")
        )

        if success and downloaded_malware:
            technique, tactic = TECHNIQUE_INGRESS
            severity = 10
            summary = ("Attacker breached SSH/Telnet honeypot and attempted malware "
                       "download / execution")
        elif success and commands:
            technique, tactic = TECHNIQUE_EXECUTION
            severity = 9
            summary = "Attacker logged into honeypot and executed commands"
        elif success:
            technique, tactic = TECHNIQUE_VALID_ACCOUNTS
            severity = 8
            summary = "Attacker successfully logged into SSH/Telnet honeypot"
        else:
            technique, tactic = TECHNIQUE_BRUTE_FORCE
            severity = max(5, min(7, 4 + len(attempts) // 3))
            summary = f"Credential brute-force against honeypot ({len(attempts)} attempts)"

        # Confidence is 1.0 — a honeypot has no legitimate users, so any
        # interaction is unambiguously hostile.
        return {
            "technique_id": technique,
            "tactic": tactic,
            "severity": severity,
            "summary": summary,
            "confidence": 1.0,
        }

    # ── core ─────────────────────────────────────────────────────

    def _handle_session(self, session: dict) -> None:
        sid = session["session_id"]
        src_ip = session["src_ip"]
        if not src_ip:
            return

        classification = self._classify(session)
        event_id = f"HP-{uuid.uuid4().hex[:8]}"
        network = self._current_network()
        network_id = network.network_id if network else None

        indicators = [src_ip]
        top_creds = [f"{a['username']}:{a['password']}" for a in session["login_attempts"][:5]]

        # 1. Persist to the registry (shows in Threats tab, network-scoped)
        self.registry.add_threat_event(
            event_id=event_id,
            device_id=f"honeypot:{src_ip}",
            tactic=classification["tactic"],
            technique_id=classification["technique_id"],
            confidence=classification["confidence"],
            severity=classification["severity"],
            summary=classification["summary"],
            indicators=indicators,
            action_taken="honeypot_captured",
            network_id=network_id,
        )

        # 2. Publish to the live feed + responder
        threat_event = {
            "event_id": event_id,
            "device_id": f"honeypot:{src_ip}",
            "src_ip": src_ip,
            "tactic": classification["tactic"],
            "technique_id": classification["technique_id"],
            "severity": classification["severity"],
            "confidence": classification["confidence"],
            "summary": classification["summary"],
            "indicators": indicators,
            "source": "honeypot",
            "captured_credentials": top_creds,
            "commands": session["commands"][:10],
            "timestamp": session.get("start_time", ""),
        }
        self.redis_client.publish(self.threat_channel, json.dumps(threat_event))

        logger.warning(
            "honeypot_threat",
            event_id=event_id,
            src_ip=src_ip,
            severity=classification["severity"],
            technique=classification["technique_id"],
        )

        # 3. Auto-block the attacker
        if self._auto_block_enabled() and src_ip not in self._blocked_ips:
            self._block_attacker(src_ip, event_id, classification["severity"])
            self._blocked_ips.add(src_ip)

    def _block_attacker(self, src_ip: str, event_id: str, severity: int) -> None:
        network = self._current_network()
        network_id = network.network_id if network else None
        try:
            rule = self.registry.add_firewall_rule(
                protocol="ANY",
                target=src_ip,
                action="DROP",
                description=f"Auto-blocked honeypot attacker (event {event_id}, sev {severity})",
                network_id=network_id,
            )
            # Tell the responder / dashboard an action was taken.
            self.redis_client.publish(self.action_channel, json.dumps({
                "event_id": event_id,
                "action": "block_ip",
                "target": src_ip,
                "rule_id": rule.rule_id,
                "source": "honeypot",
            }))
            logger.warning("honeypot_attacker_blocked", src_ip=src_ip, rule_id=rule.rule_id)
        except Exception as e:
            logger.error("honeypot_block_failed", src_ip=src_ip, error=str(e))

    def run(self) -> None:
        logger.info("honeypot_monitor_started", log=str(COWRIE_LOG), poll=self.poll_interval)

        # Seed already-present sessions so a restart doesn't re-fire threats
        # for sessions captured before this run.
        for sid in self._parse_sessions():
            self._seen_sessions.add(sid)
        logger.info("honeypot_monitor_baselined", existing_sessions=len(self._seen_sessions))

        while True:
            try:
                sessions = self._parse_sessions()
                for sid, session in sessions.items():
                    # Report once the session has a definite outcome: a
                    # successful login, some commands, several attempts, or a
                    # closed session. Avoids firing on a half-open connection.
                    ready = (
                        session["success"]
                        or session["commands"]
                        or len(session["login_attempts"]) >= 3
                        or session["closed"]
                    )
                    if sid not in self._seen_sessions and ready:
                        self._seen_sessions.add(sid)
                        self._handle_session(session)
            except Exception as e:
                logger.error("honeypot_monitor_error", error=str(e))

            time.sleep(self.poll_interval)


if __name__ == "__main__":
    HoneypotMonitor().run()
