"""
SENTINEL — Host Firewall (real nftables enforcement)

The dashboard's block / unblock / toggle controls used to change only the
database row, so a "block" was purely cosmetic and an "unblock" removed a rule
that was never really applied. This module closes that gap: it maintains an
`inet sentinel` nftables table and adds/removes an actual DROP rule per target
IP, so the firewall tab reflects the real state of the host.

Design choices:

  * **Single-host targets only.** Only a bare IP or a /32 is enforced. Broad
    targets (CIDRs, 0.0.0.0/0) are left logical — a wide DROP is exactly how you
    take yourself offline by accident, so those stay DB-only and are reported
    as not enforced.

  * **Hard safety guard.** It refuses to drop the appliance's own addresses,
    the default gateway, loopback, and unspecified/broadcast addresses. On a
    laptop this is what stops an auto-block (whose "attacker" is often the host
    itself in bridge mode) from cutting your own connectivity.

  * **Precise unblock.** Removal looks up the exact rule handles for that IP
    and deletes only those, rather than flushing the whole table — so unblocking
    one device never disturbs another device's block.

  * **Works with or without root.** nft needs root; if the API is not root it
    retries via `sudo -n`. If neither works the call fails cleanly and the
    caller records the rule as logical rather than crashing.

Scope note: on the Pi 5 inline/gateway deployment the forward-chain drops cut a
device off the internet. On the laptop (not inline) only host-directed traffic
in the input chain is truly affected; the forward rules are still installed so
behaviour is identical when the appliance is later placed inline.
"""

from __future__ import annotations

import ipaddress
import os
import re
import subprocess
from dataclasses import dataclass
from typing import Optional

import structlog

from sentinel.core.network_identity import detect_current_network

logger = structlog.get_logger(__name__)

NFT = "/usr/sbin/nft"
TABLE = ("inet", "sentinel")
CHAINS = ("input", "forward")


@dataclass
class EnforcementResult:
    enforced: bool           # did a real nft rule change happen?
    note: str                # human-readable reason / status


class HostFirewall:
    def __init__(self) -> None:
        self._table_ready = False

    # ── command plumbing ─────────────────────────────────────────

    def _nft(self, args: list[str], check: bool = True) -> subprocess.CompletedProcess:
        """Run an nft command, escalating with sudo -n when not already root."""
        base = [NFT] if os.geteuid() == 0 else ["sudo", "-n", NFT]
        return subprocess.run(
            base + args,
            check=check,
            capture_output=True,
            text=True,
            timeout=5,
        )

    def _ensure_table(self) -> None:
        """Create the table + accept-policy filter chains once, idempotently."""
        if self._table_ready:
            return
        fam, name = TABLE
        # `add` is idempotent for tables/chains in nftables, so this is safe to
        # repeat. Policy is accept: only our explicit drops take effect.
        self._nft(["add", "table", fam, name], check=False)
        for chain in CHAINS:
            self._nft([
                "add", "chain", fam, name, chain,
                "{", "type", "filter", "hook", chain,
                "priority", "0", ";", "policy", "accept", ";", "}",
            ], check=False)
        self._table_ready = True

    # ── safety guard ─────────────────────────────────────────────

    def _protected_ips(self) -> set[str]:
        """Addresses that must never be blocked: own IPs + gateway."""
        protected: set[str] = set()
        net = None
        try:
            net = detect_current_network()
        except Exception:
            net = None
        if net:
            if net.local_ip:
                protected.add(net.local_ip)
            if net.gateway_ip:
                protected.add(net.gateway_ip)
        # Every local interface address, in case detection missed one.
        try:
            out = subprocess.run(
                ["ip", "-4", "-o", "addr", "show"],
                capture_output=True, text=True, timeout=3,
            ).stdout
            for m in re.finditer(r"inet (\d+\.\d+\.\d+\.\d+)", out):
                protected.add(m.group(1))
        except Exception:
            pass
        return protected

    def check_target(self, target: str) -> tuple[Optional[str], EnforcementResult]:
        """
        Validate a block target. Returns (enforceable_ip, result).

        enforceable_ip is a single host IP string when the target is safe to
        enforce, else None (the rule stays logical). result.note explains why.
        """
        raw = (target or "").strip()

        # Only single hosts are enforced. Accept "1.2.3.4" or "1.2.3.4/32".
        ip_str = raw
        if "/" in raw:
            try:
                net = ipaddress.ip_network(raw, strict=False)
            except ValueError:
                return None, EnforcementResult(False, f"{raw!r} is not a valid target")
            if net.num_addresses != 1:
                return None, EnforcementResult(
                    False, "range/CIDR targets are kept logical (not enforced) for safety")
            ip_str = str(net.network_address)

        try:
            ip = ipaddress.ip_address(ip_str)
        except ValueError:
            return None, EnforcementResult(False, f"{raw!r} is not a single IP — kept logical")

        if ip.version != 4:
            return None, EnforcementResult(False, "only IPv4 targets are enforced")
        if ip.is_loopback or ip.is_unspecified or ip.is_multicast or str(ip).endswith(".255"):
            return None, EnforcementResult(False, "refused to block a loopback/broadcast/unspecified address")
        if ip_str in self._protected_ips():
            return None, EnforcementResult(
                False, f"refused to block {ip_str}: it is this host or the gateway (self-lockout guard)")

        return ip_str, EnforcementResult(True, "eligible for enforcement")

    # ── operations ───────────────────────────────────────────────

    def block(self, target: str) -> EnforcementResult:
        """Install a real DROP for a single-host target, if safe."""
        ip, verdict = self.check_target(target)
        if ip is None:
            return verdict  # not enforceable; caller keeps it logical
        try:
            self._ensure_table()
            fam, name = TABLE
            if not self._rule_handles(ip):  # avoid duplicates
                self._nft(["add", "rule", fam, name, "input", "ip", "saddr", ip, "drop"])
                self._nft(["add", "rule", fam, name, "forward", "ip", "saddr", ip, "drop"])
                self._nft(["add", "rule", fam, name, "forward", "ip", "daddr", ip, "drop"])
            logger.info("host_firewall_blocked", ip=ip)
            return EnforcementResult(True, f"nftables DROP active for {ip}")
        except subprocess.CalledProcessError as e:
            msg = (e.stderr or "").strip() or str(e)
            logger.error("host_firewall_block_failed", ip=ip, error=msg)
            return EnforcementResult(False, f"could not apply nftables rule (need root?): {msg}")
        except Exception as e:
            logger.error("host_firewall_block_failed", ip=ip, error=str(e))
            return EnforcementResult(False, f"could not apply nftables rule: {e}")

    def unblock(self, target: str) -> EnforcementResult:
        """Remove exactly the rules for this target IP, leaving others intact."""
        ip, verdict = self.check_target(target)
        if ip is None:
            # Never enforced in the first place — nothing to remove.
            return EnforcementResult(False, "no enforced rule for this target (was logical)")
        try:
            handles = self._rule_handles(ip)
            if not handles:
                return EnforcementResult(False, f"no active nftables rule found for {ip}")
            fam, name = TABLE
            for chain, handle in handles:
                self._nft(["delete", "rule", fam, name, chain, "handle", handle], check=False)
            logger.info("host_firewall_unblocked", ip=ip, rules=len(handles))
            return EnforcementResult(True, f"removed {len(handles)} nftables rule(s) for {ip}")
        except Exception as e:
            logger.error("host_firewall_unblock_failed", ip=ip, error=str(e))
            return EnforcementResult(False, f"could not remove nftables rule: {e}")

    # ── introspection ────────────────────────────────────────────

    def _rule_handles(self, ip: str) -> list[tuple[str, str]]:
        """Return [(chain, handle), …] for every rule that targets this IP."""
        fam, name = TABLE
        try:
            out = self._nft(["-a", "list", "table", fam, name], check=False).stdout
        except Exception:
            return []
        handles: list[tuple[str, str]] = []
        chain = None
        esc = re.escape(ip)
        for line in out.splitlines():
            cm = re.match(r"\s*chain (\w+) \{", line)
            if cm:
                chain = cm.group(1)
                continue
            if chain and re.search(rf"ip (?:saddr|daddr) {esc} drop", line):
                hm = re.search(r"# handle (\d+)", line)
                if hm:
                    handles.append((chain, hm.group(1)))
        return handles

    def is_enforced(self, target: str) -> bool:
        ip, verdict = self.check_target(target)
        if ip is None:
            return False
        return bool(self._rule_handles(ip))

    def blocked_ips(self) -> set[str]:
        """All IPs with at least one active DROP rule (one nft call)."""
        fam, name = TABLE
        try:
            out = self._nft(["list", "table", fam, name], check=False).stdout
        except Exception:
            return set()
        return set(re.findall(r"ip (?:saddr|daddr) (\d+\.\d+\.\d+\.\d+) drop", out))
