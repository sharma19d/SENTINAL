#!/usr/bin/env python3
"""
SENTINEL Layer 1 — Main Entry Point

Orchestrates all capture engine components:
  Sniffer → Flow Tracker → Protocol Analyzer → Redis Publisher

Usage:
  # Live capture on wlan0
  sudo python -m sentinel.core.capture.main --interface wlan0

  # Replay a PCAP file (no sudo needed)
  python -m sentinel.core.capture.main --pcap test.pcap

  # Capture with BPF filter
  sudo python -m sentinel.core.capture.main --interface eth0 --filter "tcp port 80"

  # Without Redis (local-only mode)
  python -m sentinel.core.capture.main --pcap test.pcap --no-redis
"""

from __future__ import annotations

import argparse
import asyncio
import logging
import signal
import sys
import time

import structlog

from sentinel.core.capture.config import CaptureConfig
from sentinel.core.capture.flow_parser import FlowTracker
from sentinel.core.capture.models import (
    CaptureStats, DiscoveryEvent, FlowEvent, FlowEventType, PacketMeta,
)
from sentinel.core.capture.protocol_analyzer import ProtocolAnalyzer
from sentinel.core.capture.redis_publisher import RedisPublisher
from sentinel.core.capture.sniffer import PacketSniffer
from sentinel.core.capture.utils import (
    mac_to_vendor, get_available_interfaces, epoch_to_iso, format_duration,
)


def configure_logging(level: str = "INFO", fmt: str = "console") -> None:
    """Configure structlog for the capture engine."""
    processors = [
        structlog.contextvars.merge_contextvars,
        structlog.processors.add_log_level,
        structlog.processors.TimeStamper(fmt="iso"),
    ]

    if fmt == "json":
        processors.append(structlog.processors.JSONRenderer())
    else:
        processors.extend([
            structlog.dev.set_exc_info,
            structlog.dev.ConsoleRenderer(colors=True),
        ])

    structlog.configure(
        processors=processors,
        wrapper_class=structlog.make_filtering_bound_logger(
            getattr(logging, level.upper(), logging.INFO)
        ),
        context_class=dict,
        logger_factory=structlog.PrintLoggerFactory(),
        cache_logger_on_first_use=True,
    )


class CaptureEngine:
    """
    Main orchestrator for the SENTINEL Network Capture & Packet Engine.

    Wires together all components:
      PacketSniffer → FlowTracker → ProtocolAnalyzer → RedisPublisher

    Handles signal-based graceful shutdown (SIGINT, SIGTERM).
    """

    def __init__(self, config: CaptureConfig, use_redis: bool = True,
                 publish_packets: bool = False):
        self.config = config
        self.use_redis = use_redis
        self.publish_packets = publish_packets

        self.logger = structlog.get_logger("sentinel.capture.engine")

        # Initialize components
        self.sniffer = PacketSniffer(config)
        self.flow_tracker = FlowTracker(config)
        self.protocol_analyzer = ProtocolAnalyzer(config, self.flow_tracker)
        self.redis_publisher = RedisPublisher(config)

        # Wire up the pipeline
        self.sniffer.on_packet(self._on_packet)
        self.flow_tracker.on_flow_event(self._on_flow_event)

        self._shutdown_event = asyncio.Event()
        self._stats_task = None

    def _on_packet(self, meta: PacketMeta) -> None:
        """
        Packet handler: processes each packet through the pipeline.
        Called by the sniffer for every captured packet.
        """
        # 1. Track the flow
        flow = self.flow_tracker.process_packet(meta)

        # 2. Apply DPI fallback if NFStream isn't running
        if flow and not self.protocol_analyzer.is_running:
            self.protocol_analyzer.enrich_flow_fallback(flow)

        # 3. Publish discovery events for ARP/mDNS/SSDP/DHCP
        if meta.is_discovery_relevant and self.use_redis:
            self._publish_discovery(meta)

        # 4. Optionally publish raw packet events
        if self.publish_packets and self.use_redis:
            self.redis_publisher.publish_raw_packet(meta)

    def _on_flow_event(self, event: FlowEvent) -> None:
        """
        Flow event handler: publishes flow events to Redis.
        """
        if self.use_redis:
            self.redis_publisher.publish_flow_event(event)

        # Console output for visibility
        flow = event.flow
        if event.event_type == FlowEventType.NEW_FLOW:
            self.logger.info(
                "new_flow",
                flow_id=flow.flow_id[:8],
                src=f"{flow.src_ip}:{flow.src_port}",
                dst=f"{flow.dst_ip}:{flow.dst_port}",
                proto=flow.protocol.value,
                app=flow.app_protocol,
            )
        elif event.event_type == FlowEventType.FLOW_END:
            self.logger.info(
                "flow_end",
                flow_id=flow.flow_id[:8],
                packets=flow.packet_count,
                bytes=flow.byte_count,
                duration=format_duration(flow.duration),
                app=flow.app_protocol,
                status=flow.status.value,
            )

    def _publish_discovery(self, meta: PacketMeta) -> None:
        """Build and publish a discovery event from packet metadata."""
        # 1. ARP
        if meta.arp_operation:
            event = DiscoveryEvent(
                event_type="arp",
                timestamp=meta.timestamp,
                mac_address=meta.arp_sender_mac or meta.src_mac,
                ip_address=meta.arp_sender_ip or meta.src_ip,
                vendor=mac_to_vendor(meta.arp_sender_mac or meta.src_mac),
                arp_operation=meta.arp_operation,
            )
            self.redis_publisher.publish_discovery_event(event)

        # 2. mDNS
        if meta.mdns_info:
            info = meta.mdns_info
            event = DiscoveryEvent(
                event_type="mdns",
                timestamp=meta.timestamp,
                mac_address=meta.src_mac,
                ip_address=meta.src_ip,
                vendor=mac_to_vendor(meta.src_mac),
                mdns_hostname=info.get("hostname"),
                mdns_service_type=info.get("service_type"),
                mdns_service_name=info.get("service_name"),
            )
            self.redis_publisher.publish_discovery_event(event)

        # 3. SSDP
        if meta.ssdp_info:
            info = meta.ssdp_info
            event = DiscoveryEvent(
                event_type="ssdp",
                timestamp=meta.timestamp,
                mac_address=meta.src_mac,
                ip_address=meta.src_ip,
                vendor=mac_to_vendor(meta.src_mac),
                ssdp_location=info.get("location"),
                ssdp_server=info.get("server"),
                ssdp_usn=info.get("usn"),
                ssdp_service_type=info.get("service_type"),
            )
            self.redis_publisher.publish_discovery_event(event)

        # 4. DHCP
        if meta.dhcp_info:
            info = meta.dhcp_info
            event = DiscoveryEvent(
                event_type="dhcp",
                timestamp=meta.timestamp,
                mac_address=info.get("client_mac") or meta.src_mac,
                ip_address=info.get("requested_ip") or meta.src_ip,
                vendor=mac_to_vendor(info.get("client_mac") or meta.src_mac),
                dhcp_hostname=info.get("hostname"),
                dhcp_vendor_class=info.get("vendor_class"),
                dhcp_requested_ip=info.get("requested_ip"),
            )
            self.redis_publisher.publish_discovery_event(event)

    async def _arp_sweep_loop(self) -> None:
        """
        Periodically ARP-sweep the local /24 subnet to actively discover
        devices that are connected but stay silent on broadcast/multicast
        traffic between events (e.g. phones, which typically only send
        ARP/DHCP broadcasts once at join time and otherwise communicate
        with the router over unicast frames a normal Wi-Fi station can't
        see). Passive capture alone can miss devices entirely or lose
        track of them the moment they go quiet; this loop actively
        confirms who is really on the network right now.

        Also re-publishes a discovery event for every device that answers,
        so `last_seen` in the registry stays fresh for genuinely-connected
        devices — this is what lets the dashboard reliably distinguish a
        device that disconnected from one that is just idle.
        """
        if not self.config.arp_sweep_enabled:
            return

        from scapy.layers.l2 import ARP, Ether
        from scapy.sendrecv import srp
        from scapy.arch import get_if_addr

        try:
            local_ip = get_if_addr(self.config.capture_interface)
        except Exception:
            local_ip = None

        if not local_ip or local_ip == "0.0.0.0":
            self.logger.warning(
                "arp_sweep_disabled",
                reason="could_not_determine_local_ip",
                interface=self.config.capture_interface,
            )
            return

        subnet = ".".join(local_ip.split(".")[:3]) + ".0/24"
        self.logger.info("arp_sweep_starting", subnet=subnet, interval=self.config.arp_sweep_interval)

        while not self._shutdown_event.is_set():
            try:
                loop = asyncio.get_event_loop()
                answered, _ = await loop.run_in_executor(
                    None,
                    lambda: srp(
                        Ether(dst="ff:ff:ff:ff:ff:ff") / ARP(pdst=subnet),
                        timeout=3,
                        iface=self.config.capture_interface,
                        verbose=False,
                    ),
                )

                for _, reply in answered:
                    mac = reply.hwsrc
                    ip = reply.psrc
                    event = DiscoveryEvent(
                        event_type="arp_sweep",
                        timestamp=time.time(),
                        mac_address=mac,
                        ip_address=ip,
                        vendor=mac_to_vendor(mac),
                        arp_operation="reply",
                    )
                    if self.use_redis:
                        self.redis_publisher.publish_discovery_event(event)

                self.logger.info("arp_sweep_complete", devices_found=len(answered))
            except Exception as e:
                self.logger.error("arp_sweep_failed", error=str(e))

            try:
                await asyncio.wait_for(self._shutdown_event.wait(), timeout=self.config.arp_sweep_interval)
            except asyncio.TimeoutError:
                pass

    async def _stats_loop(self) -> None:
        """Periodically publish capture statistics."""
        while not self._shutdown_event.is_set():
            await asyncio.sleep(self.config.stats_interval)

            stats = self.sniffer.stats
            stats.flows_active = self.flow_tracker.active_count
            stats.flows_total = self.flow_tracker.total_count
            stats.flows_timed_out = self.flow_tracker.timed_out_count
            stats.dpi_enabled = self.protocol_analyzer.is_running
            stats.redis_connected = self.redis_publisher.is_connected

            if self.use_redis:
                self.redis_publisher.publish_stats(stats)

            self.logger.info(
                "capture_stats",
                packets=stats.packets_captured,
                pps=stats.packets_per_second,
                flows_active=stats.flows_active,
                flows_total=stats.flows_total,
                uptime=format_duration(stats.uptime_seconds),
            )

    async def run(self, pcap_file: str = None) -> None:
        """
        Main run loop. Start all components and wait for shutdown.

        Args:
            pcap_file: Optional PCAP file to replay instead of live capture.
        """
        self.logger.info("engine_starting", interface=self.config.capture_interface)

        # Connect to Redis
        if self.use_redis:
            if not self.redis_publisher.connect():
                self.logger.warning(
                    "redis_unavailable",
                    msg="Continuing without Redis. Events will be logged only."
                )
                self.use_redis = False

        # Start DPI
        self.protocol_analyzer.start()

        # Start sniffer
        self.sniffer.start(pcap_file=pcap_file)

        # Start async tasks
        cleanup_task = asyncio.create_task(
            self.flow_tracker.start_cleanup_loop()
        )
        self._stats_task = asyncio.create_task(self._stats_loop())

        # Active ARP sweep only makes sense against a live interface
        arp_sweep_task = None
        if pcap_file is None:
            arp_sweep_task = asyncio.create_task(self._arp_sweep_loop())

        self.logger.info(
            "engine_running",
            interface=self.config.capture_interface,
            redis=self.use_redis,
            dpi=self.protocol_analyzer.is_running,
        )

        # Wait for shutdown signal
        await self._shutdown_event.wait()

        # Graceful shutdown
        self.logger.info("engine_shutting_down")

        cleanup_task.cancel()
        self._stats_task.cancel()
        if arp_sweep_task:
            arp_sweep_task.cancel()

        stats = self.sniffer.stop()
        self.protocol_analyzer.stop()

        if self.use_redis:
            self.redis_publisher.disconnect()

        self.logger.info(
            "engine_stopped",
            total_packets=stats.packets_captured,
            total_bytes=stats.bytes_captured,
            total_flows=self.flow_tracker.total_count,
            uptime=format_duration(stats.uptime_seconds),
        )

    def shutdown(self) -> None:
        """Signal the engine to shut down."""
        self._shutdown_event.set()


def parse_args() -> argparse.Namespace:
    """Parse command-line arguments."""
    parser = argparse.ArgumentParser(
        prog="sentinel-capture",
        description="SENTINEL Layer 1 — Network Capture & Packet Engine",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Live capture on wlan0 (requires root/sudo)
  sudo python -m sentinel.core.capture.main --interface wlan0

  # Replay a PCAP file
  python -m sentinel.core.capture.main --pcap traffic.pcap

  # Capture with BPF filter, verbose logging
  sudo python -m sentinel.core.capture.main -i eth0 -f "not port 22" -v

  # List available interfaces
  python -m sentinel.core.capture.main --list-interfaces
        """,
    )

    parser.add_argument(
        "-i", "--interface",
        help="Network interface to capture on (default: from config or auto-detect)",
    )
    parser.add_argument(
        "-f", "--filter",
        help="BPF filter expression (e.g., 'tcp port 80')",
    )
    parser.add_argument(
        "--pcap",
        help="Replay packets from a PCAP file instead of live capture",
    )
    parser.add_argument(
        "--no-redis",
        action="store_true",
        help="Run without Redis (events logged to console only)",
    )
    parser.add_argument(
        "--no-dpi",
        action="store_true",
        help="Disable NFStream DPI (use port-based inference only)",
    )
    parser.add_argument(
        "--publish-packets",
        action="store_true",
        help="Publish raw packet events to Redis (high frequency — for debugging)",
    )
    parser.add_argument(
        "-v", "--verbose",
        action="store_true",
        help="Enable debug logging",
    )
    parser.add_argument(
        "--list-interfaces",
        action="store_true",
        help="List available network interfaces and exit",
    )

    return parser.parse_args()


def main() -> None:
    """Main entry point."""
    args = parse_args()

    # List interfaces and exit
    if args.list_interfaces:
        print("\n  SENTINEL — Available Network Interfaces\n")
        interfaces = get_available_interfaces()
        if not interfaces:
            print("  No interfaces found. Is Scapy installed?")
        else:
            for iface in interfaces:
                print(f"  • {iface['name']:<20} MAC: {iface['mac']}")
        print()
        sys.exit(0)

    # Load config
    config = CaptureConfig()

    # Override config with CLI arguments
    if args.interface:
        config.capture_interface = args.interface
    if args.filter:
        config.bpf_filter = args.filter
    if args.no_dpi:
        config.enable_dpi = False
    if args.verbose:
        config.log_level = "DEBUG"

    # Configure logging
    configure_logging(
        level=config.log_level,
        fmt="console",  # Always console for CLI
    )

    logger = structlog.get_logger("sentinel.capture")

    # Banner
    logger.info("sentinel_layer1_starting",
                 version="0.1.0",
                 interface=config.capture_interface,
                 dpi=config.enable_dpi)

    # Create and run the engine
    engine = CaptureEngine(
        config=config,
        use_redis=not args.no_redis,
        publish_packets=args.publish_packets,
    )

    # Setup signal handlers for graceful shutdown
    loop = asyncio.new_event_loop()

    def handle_signal(signum, frame):
        logger.info("signal_received", signal=signum)
        engine.shutdown()

    signal.signal(signal.SIGINT, handle_signal)
    signal.signal(signal.SIGTERM, handle_signal)

    try:
        loop.run_until_complete(engine.run(pcap_file=args.pcap))
    except KeyboardInterrupt:
        engine.shutdown()
        loop.run_until_complete(asyncio.sleep(0.5))
    finally:
        loop.close()


if __name__ == "__main__":
    main()
