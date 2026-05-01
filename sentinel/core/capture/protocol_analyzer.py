"""
SENTINEL Layer 1 — Protocol Analyzer

Two-tier protocol classification:
  1. NFStream (nDPI) — high-performance DPI for 300+ protocols
  2. Scapy-based fallback — basic protocol inference from packet metadata

NFStream runs in a background thread on the same interface and its
flow classifications are correlated with our FlowTracker via 5-tuple.
"""

from __future__ import annotations

import threading
import time
from typing import Optional

import structlog

from sentinel.core.capture.config import CaptureConfig
from sentinel.core.capture.flow_parser import FlowTracker
from sentinel.core.capture.utils import generate_flow_id

logger = structlog.get_logger(__name__)


class ProtocolAnalyzer:
    """
    Deep Packet Inspection engine using NFStream (nDPI wrapper).

    Runs NFStream in a separate thread capturing from the same interface.
    Periodically correlates NFStream's flow classifications with the
    FlowTracker's flow table to enrich flows with L7 protocol names.

    If NFStream is unavailable (not installed or wrong platform),
    falls back gracefully to Scapy-based protocol inference.
    """

    def __init__(self, config: CaptureConfig, flow_tracker: FlowTracker):
        self.config = config
        self.flow_tracker = flow_tracker
        self._thread: Optional[threading.Thread] = None
        self._running = False
        self._nfstream_available = False

        # Check NFStream availability
        if config.enable_dpi:
            try:
                import nfstream
                self._nfstream_available = True
                logger.info("nfstream_available", version=nfstream.__version__)
            except ImportError:
                logger.warning("nfstream_not_available",
                                msg="NFStream not installed. Using Scapy-based "
                                "protocol inference only. Install with: "
                                "pip install nfstream")

    def start(self) -> None:
        """Start the DPI analysis thread."""
        if not self.config.enable_dpi:
            logger.info("dpi_disabled")
            return

        if not self._nfstream_available:
            logger.info("dpi_fallback_mode",
                         msg="Using Scapy-based protocol inference only")
            return

        if self._running:
            logger.warning("dpi_already_running")
            return

        self._running = True
        self._thread = threading.Thread(
            target=self._nfstream_worker,
            name="sentinel-dpi",
            daemon=True,
        )
        self._thread.start()
        logger.info("dpi_started", interface=self.config.capture_interface)

    def stop(self) -> None:
        """Stop the DPI analysis thread."""
        self._running = False
        if self._thread and self._thread.is_alive():
            self._thread.join(timeout=5.0)
            logger.info("dpi_stopped")

    @property
    def is_running(self) -> bool:
        return self._running and (
            self._thread is not None and self._thread.is_alive()
        )

    def _nfstream_worker(self) -> None:
        """
        Background thread running NFStream on the capture interface.
        Processes completed flows and enriches the flow tracker.
        """
        try:
            from nfstream import NFStreamer

            interface = self.config.capture_interface
            if interface == "auto":
                from sentinel.core.capture.utils import get_default_interface
                interface = get_default_interface()

            logger.info("nfstream_worker_starting", interface=interface)

            streamer = NFStreamer(
                source=interface,
                statistical_analysis=True,
                idle_timeout=self.config.flow_timeout_idle,
                active_timeout=self.config.flow_timeout_active,
            )

            for nf_flow in streamer:
                if not self._running:
                    break

                self._correlate_nfstream_flow(nf_flow)

        except Exception as e:
            logger.error("nfstream_worker_error", error=str(e))
            self._running = False

    def _correlate_nfstream_flow(self, nf_flow) -> None:
        """
        Correlate an NFStream flow with our FlowTracker and enrich
        the FlowRecord with L7 protocol classification.
        """
        try:
            # Build the 5-tuple from NFStream flow
            src_ip = nf_flow.src_ip
            dst_ip = nf_flow.dst_ip
            src_port = nf_flow.src_port
            dst_port = nf_flow.dst_port

            # Determine L4 protocol string
            proto_map = {6: "TCP", 17: "UDP", 1: "ICMP"}
            proto_str = proto_map.get(nf_flow.protocol, "OTHER")

            # Generate the same flow ID our tracker uses
            flow_id = generate_flow_id(
                src_ip, dst_ip, src_port, dst_port, proto_str
            )

            # Look up in our flow table
            flow = self.flow_tracker.get_flow(flow_id)
            if flow is None:
                return

            # Enrich with nDPI classification
            app_name = getattr(nf_flow, "application_name", "Unknown")
            if app_name and app_name != "Unknown":
                flow.app_protocol = app_name
                logger.debug("flow_dpi_enriched",
                              flow_id=flow_id[:8],
                              app_protocol=app_name)

            # Extract additional metadata from NFStream
            # Client/server info
            client_info = getattr(nf_flow, "client_info", None)
            server_info = getattr(nf_flow, "server_info", None)

            if client_info and client_info not in flow.http_user_agents:
                flow.http_user_agents.append(client_info)

            if server_info and not flow.tls_sni:
                flow.tls_sni = server_info

        except Exception as e:
            logger.debug("nfstream_correlation_error", error=str(e))

    # ── Port-Based Protocol Inference (Fallback) ─────────────────

    @staticmethod
    def infer_protocol_from_port(port: Optional[int]) -> str:
        """
        Basic protocol inference based on well-known port numbers.
        Used as a fallback when NFStream DPI is not available.
        """
        if port is None:
            return "Unknown"

        port_map = {
            20: "FTP-DATA", 21: "FTP", 22: "SSH", 23: "Telnet",
            25: "SMTP", 53: "DNS", 67: "DHCP", 68: "DHCP",
            80: "HTTP", 110: "POP3", 123: "NTP", 143: "IMAP",
            161: "SNMP", 162: "SNMP-TRAP",
            443: "HTTPS", 445: "SMB",
            465: "SMTPS", 587: "SMTP", 993: "IMAPS", 995: "POP3S",
            1883: "MQTT", 1900: "SSDP", 3306: "MySQL",
            5353: "mDNS", 5683: "CoAP",
            6379: "Redis", 8080: "HTTP-ALT", 8443: "HTTPS-ALT",
            8883: "MQTTS", 27017: "MongoDB",
        }
        return port_map.get(port, "Unknown")

    def enrich_flow_fallback(self, flow) -> None:
        """
        Apply port-based protocol inference to a flow if
        the app_protocol is still 'Unknown'.
        """
        if flow.app_protocol != "Unknown":
            return

        # Try destination port first (more likely to be the server)
        proto = self.infer_protocol_from_port(flow.dst_port)
        if proto == "Unknown":
            proto = self.infer_protocol_from_port(flow.src_port)

        if proto != "Unknown":
            flow.app_protocol = proto
