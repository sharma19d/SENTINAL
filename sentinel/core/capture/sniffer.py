"""
SENTINEL Layer 1 — Packet Sniffer

Raw packet capture engine using Scapy AsyncSniffer.
Captures packets from a network interface or PCAP file,
extracts per-packet metadata, and dispatches to registered handlers.
"""

from __future__ import annotations

import time
from typing import Callable, Optional

import structlog

from sentinel.core.capture.config import CaptureConfig
from sentinel.core.capture.models import PacketMeta, L4Protocol, CaptureStats
from sentinel.core.capture.metadata_extractor import enrich_packet
from sentinel.core.capture.utils import mac_to_vendor, get_default_interface

logger = structlog.get_logger(__name__)


class PacketSniffer:
    """
    Async packet capture engine.

    Captures raw packets from a network interface using Scapy's AsyncSniffer,
    extracts PacketMeta from each packet, and dispatches to registered handlers.

    Usage:
        sniffer = PacketSniffer(config)
        sniffer.on_packet(my_handler_function)
        sniffer.start()
        # ... later ...
        sniffer.stop()
    """

    def __init__(self, config: CaptureConfig):
        self.config = config
        self._sniffer = None
        self._running = False
        self._handlers: list[Callable[[PacketMeta], None]] = []
        self._stats = CaptureStats()
        self._start_time: float = 0.0

        # Resolve interface
        iface = config.capture_interface
        if iface == "auto":
            iface = get_default_interface()
            logger.info("interface_auto_detected", interface=iface)
        self._interface = iface

    def on_packet(self, handler: Callable[[PacketMeta], None]) -> None:
        """Register a callback to receive PacketMeta for each captured packet."""
        self._handlers.append(handler)
        logger.debug("handler_registered", handler=handler.__name__,
                      total_handlers=len(self._handlers))

    def start(self, pcap_file: Optional[str] = None) -> None:
        """
        Start capturing packets.

        Args:
            pcap_file: If provided, replay packets from this PCAP file
                       instead of live capture. Useful for testing.
        """
        from scapy.all import AsyncSniffer

        if self._running:
            logger.warning("sniffer_already_running")
            return

        self._start_time = time.time()
        self._stats = CaptureStats(
            capture_interface=pcap_file or self._interface,
            capture_started=self._start_time,
        )

        sniffer_kwargs = {
            "prn": self._packet_callback,
            "store": False,  # Don't store packets in memory
        }

        if pcap_file:
            # Offline mode: replay PCAP file
            sniffer_kwargs["offline"] = pcap_file
            logger.info("sniffer_starting_pcap", file=pcap_file)
        else:
            # Live capture mode
            sniffer_kwargs["iface"] = self._interface
            if self.config.bpf_filter:
                sniffer_kwargs["filter"] = self.config.bpf_filter
            logger.info("sniffer_starting_live",
                         interface=self._interface,
                         bpf_filter=self.config.bpf_filter or "(none)")

        self._sniffer = AsyncSniffer(**sniffer_kwargs)
        self._sniffer.start()
        self._running = True
        logger.info("sniffer_started")

    def stop(self) -> CaptureStats:
        """Stop the capture and return final statistics."""
        if not self._running:
            logger.warning("sniffer_not_running")
            return self._stats

        logger.info("sniffer_stopping")
        try:
            self._sniffer.stop()
        except Exception as e:
            logger.warning("sniffer_stop_error", error=str(e))

        self._running = False
        self._stats.uptime_seconds = round(time.time() - self._start_time, 2)

        logger.info("sniffer_stopped",
                      packets=self._stats.packets_captured,
                      bytes=self._stats.bytes_captured,
                      uptime=self._stats.uptime_seconds)
        return self._stats

    @property
    def is_running(self) -> bool:
        return self._running

    @property
    def stats(self) -> CaptureStats:
        if self._running:
            elapsed = time.time() - self._start_time
            self._stats.uptime_seconds = round(elapsed, 2)
            if elapsed > 0:
                self._stats.packets_per_second = round(
                    self._stats.packets_captured / elapsed, 2
                )
                self._stats.bytes_per_second = round(
                    self._stats.bytes_captured / elapsed, 2
                )
        return self._stats

    def _packet_callback(self, packet) -> None:
        """
        Internal callback invoked by Scapy for each captured packet.
        Extracts PacketMeta and dispatches to all registered handlers.
        """
        try:
            meta = self._extract_meta(packet)
            if meta is None:
                return

            # Update stats
            self._stats.packets_captured += 1
            self._stats.bytes_captured += meta.length

            # Dispatch to handlers
            for handler in self._handlers:
                try:
                    handler(meta)
                except Exception as e:
                    logger.error("handler_error",
                                  handler=handler.__name__, error=str(e))

        except Exception as e:
            logger.error("packet_callback_error", error=str(e))

    def _extract_meta(self, packet) -> Optional[PacketMeta]:
        """Extract PacketMeta from a raw Scapy packet."""
        from scapy.layers.l2 import Ether, ARP
        from scapy.layers.inet import IP, TCP, UDP, ICMP
        from scapy.layers.inet6 import IPv6

        now = time.time()

        # Get MAC addresses from Ethernet frame
        src_mac = "00:00:00:00:00:00"
        dst_mac = "00:00:00:00:00:00"
        if packet.haslayer(Ether):
            src_mac = packet[Ether].src
            dst_mac = packet[Ether].dst

        # Handle ARP packets (no IP layer)
        if packet.haslayer(ARP) and not packet.haslayer(IP):
            arp = packet[ARP]
            enrichment = enrich_packet(packet)
            return PacketMeta(
                timestamp=now,
                src_mac=src_mac,
                dst_mac=dst_mac,
                src_ip=arp.psrc or "0.0.0.0",
                dst_ip=arp.pdst or "0.0.0.0",
                protocol=L4Protocol.OTHER,
                length=len(packet),
                is_discovery_relevant=True,
                arp_operation=enrichment.get("arp_operation"),
                arp_sender_mac=enrichment.get("arp_sender_mac"),
                arp_sender_ip=enrichment.get("arp_sender_ip"),
                arp_target_ip=enrichment.get("arp_target_ip"),
                mdns_info=enrichment.get("_mdns"),
                ssdp_info=enrichment.get("_ssdp"),
                dhcp_info=enrichment.get("_dhcp"),
            )

        # Must have IP layer for flow tracking
        if not packet.haslayer(IP) and not packet.haslayer(IPv6):
            return None

        # Extract IP fields
        if packet.haslayer(IP):
            ip = packet[IP]
            src_ip = ip.src
            dst_ip = ip.dst
            ip_version = 4
            ttl = ip.ttl
            proto_num = ip.proto
        else:
            ip = packet[IPv6]
            src_ip = ip.src
            dst_ip = ip.dst
            ip_version = 6
            ttl = ip.hlim
            proto_num = ip.nh

        protocol = L4Protocol.from_ip_proto(proto_num)

        # Extract port info
        src_port = None
        dst_port = None
        tcp_flags = None
        payload_size = 0

        if packet.haslayer(TCP):
            tcp = packet[TCP]
            src_port = tcp.sport
            dst_port = tcp.dport
            tcp_flags = int(tcp.flags)
            payload_size = len(bytes(tcp.payload))
        elif packet.haslayer(UDP):
            udp = packet[UDP]
            src_port = udp.sport
            dst_port = udp.dport
            payload_size = len(bytes(udp.payload))

        # Run metadata enrichment (DNS, TLS, HTTP, ARP, mDNS, SSDP, DHCP)
        enrichment = enrich_packet(packet)

        return PacketMeta(
            timestamp=now,
            src_mac=src_mac,
            dst_mac=dst_mac,
            src_ip=src_ip,
            dst_ip=dst_ip,
            ip_version=ip_version,
            ttl=ttl,
            protocol=protocol,
            src_port=src_port,
            dst_port=dst_port,
            tcp_flags=tcp_flags,
            length=len(packet),
            payload_size=payload_size,
            # Enriched fields
            dns_query=enrichment.get("dns_query"),
            dns_answers=enrichment.get("dns_answers"),
            http_host=enrichment.get("http_host"),
            http_user_agent=enrichment.get("http_user_agent"),
            http_method=enrichment.get("http_method"),
            http_uri=enrichment.get("http_uri"),
            tls_sni=enrichment.get("tls_sni"),
            tls_version=enrichment.get("tls_version"),
            arp_operation=enrichment.get("arp_operation"),
            arp_sender_mac=enrichment.get("arp_sender_mac"),
            arp_sender_ip=enrichment.get("arp_sender_ip"),
            arp_target_ip=enrichment.get("arp_target_ip"),
            mdns_info=enrichment.get("_mdns"),
            ssdp_info=enrichment.get("_ssdp"),
            dhcp_info=enrichment.get("_dhcp"),
            is_discovery_relevant=enrichment.get("is_discovery_relevant", False),
        )
