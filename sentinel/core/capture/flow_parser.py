"""
SENTINEL Layer 1 — Flow Parser

Maintains an in-memory flow table indexed by bidirectional 5-tuple.
Aggregates per-packet metadata into FlowRecord objects, extracts
per-flow features, tracks flow lifecycle, and emits events.
"""

from __future__ import annotations

import asyncio
import time
from typing import Callable, Optional

import structlog

from sentinel.core.capture.config import CaptureConfig
from sentinel.core.capture.models import (
    FlowEvent, FlowEventType, FlowRecord, FlowStatus,
    L4Protocol, PacketMeta, TCPFlags,
)
from sentinel.core.capture.utils import (
    canonicalize_flow_tuple, generate_flow_id, mac_to_vendor,
)

logger = structlog.get_logger(__name__)


class FlowTracker:
    """
    Tracks network flows by aggregating packets into FlowRecord objects.

    Each flow is identified by a bidirectional 5-tuple hash. Packets
    from A→B and B→A belong to the same flow. The tracker emits events
    on flow creation, periodic updates, and flow termination.

    Usage:
        tracker = FlowTracker(config)
        tracker.on_flow_event(my_event_handler)
        # ... in packet handler ...
        flow = tracker.process_packet(packet_meta)
    """

    def __init__(self, config: CaptureConfig):
        self.config = config
        self._flows: dict[str, FlowRecord] = {}
        self._flow_event_handlers: list[Callable[[FlowEvent], None]] = []
        self._total_flows: int = 0
        self._timed_out_flows: int = 0
        self._cleanup_task: Optional[asyncio.Task] = None

    def on_flow_event(self, handler: Callable[[FlowEvent], None]) -> None:
        """Register a callback to receive FlowEvent notifications."""
        self._flow_event_handlers.append(handler)

    def process_packet(self, meta: PacketMeta) -> Optional[FlowRecord]:
        """
        Process a packet and update/create the corresponding flow.

        Args:
            meta: PacketMeta extracted by the sniffer.

        Returns:
            The updated FlowRecord, or None if the packet can't be tracked
            (e.g., ARP-only with no IP layer).
        """
        # Skip non-IP packets (ARP-only, etc.)
        if meta.src_ip == "0.0.0.0" and meta.dst_ip == "0.0.0.0":
            return None

        # Canonicalize the 5-tuple direction
        c_src_ip, c_dst_ip, c_src_port, c_dst_port, is_reversed = (
            canonicalize_flow_tuple(meta.src_ip, meta.dst_ip,
                                     meta.src_port, meta.dst_port)
        )

        # Generate bidirectional flow ID
        flow_id = generate_flow_id(
            c_src_ip, c_dst_ip, c_src_port, c_dst_port,
            meta.protocol.value
        )

        if flow_id in self._flows:
            # Update existing flow
            flow = self._flows[flow_id]
            self._update_flow(flow, meta, is_reversed)
        else:
            # Create new flow
            flow = self._create_flow(
                flow_id, c_src_ip, c_dst_ip, c_src_port, c_dst_port,
                meta
            )
            self._flows[flow_id] = flow
            self._total_flows += 1
            self._emit_event(FlowEventType.NEW_FLOW, flow)

        return flow

    def _create_flow(
        self, flow_id: str,
        src_ip: str, dst_ip: str,
        src_port: Optional[int], dst_port: Optional[int],
        meta: PacketMeta,
    ) -> FlowRecord:
        """Create a new FlowRecord from the first packet."""
        now = meta.timestamp

        flow = FlowRecord(
            flow_id=flow_id,
            src_ip=src_ip,
            dst_ip=dst_ip,
            src_port=src_port,
            dst_port=dst_port,
            protocol=meta.protocol,
            src_mac=meta.src_mac,
            dst_mac=meta.dst_mac,
            vendor_src=mac_to_vendor(meta.src_mac),
            vendor_dst=mac_to_vendor(meta.dst_mac),
            packet_count=1,
            byte_count=meta.length,
            packet_count_fwd=1,
            byte_count_fwd=meta.length,
            start_time=now,
            end_time=now,
            last_activity=now,
        )

        # TCP flags
        if meta.tcp_flags is not None:
            flags = TCPFlags.to_list(meta.tcp_flags)
            flow.tcp_flags_seen = flags.copy()
            flow.tcp_flags_fwd = flags.copy()

        # Application-layer metadata from first packet
        self._apply_metadata(flow, meta)

        logger.debug("flow_created",
                      flow_id=flow_id[:8],
                      src=f"{src_ip}:{src_port}",
                      dst=f"{dst_ip}:{dst_port}",
                      proto=meta.protocol.value)

        return flow

    def _update_flow(
        self, flow: FlowRecord, meta: PacketMeta, is_reversed: bool
    ) -> None:
        """Update an existing flow with a new packet."""
        flow.packet_count += 1
        flow.byte_count += meta.length
        flow.end_time = meta.timestamp
        flow.last_activity = meta.timestamp

        # Update direction-specific counters
        if is_reversed:
            flow.packet_count_bwd += 1
            flow.byte_count_bwd += meta.length
        else:
            flow.packet_count_fwd += 1
            flow.byte_count_fwd += meta.length

        # Update MAC addresses (use most recent)
        if not is_reversed:
            flow.src_mac = meta.src_mac
            flow.dst_mac = meta.dst_mac
        else:
            flow.src_mac = meta.dst_mac
            flow.dst_mac = meta.src_mac
        flow.vendor_src = mac_to_vendor(flow.src_mac)
        flow.vendor_dst = mac_to_vendor(flow.dst_mac)

        # TCP flags
        if meta.tcp_flags is not None:
            new_flags = TCPFlags.to_list(meta.tcp_flags)
            for flag in new_flags:
                if flag not in flow.tcp_flags_seen:
                    flow.tcp_flags_seen.append(flag)
            target = flow.tcp_flags_bwd if is_reversed else flow.tcp_flags_fwd
            for flag in new_flags:
                if flag not in target:
                    target.append(flag)

            # Check for flow termination (FIN or RST)
            if meta.tcp_flags & (TCPFlags.FIN | TCPFlags.RST):
                flow.status = FlowStatus.FINISHED
                self._emit_event(FlowEventType.FLOW_END, flow)

        # Apply application-layer metadata
        self._apply_metadata(flow, meta)

    def _apply_metadata(self, flow: FlowRecord, meta: PacketMeta) -> None:
        """Apply extracted metadata fields from a packet to a flow."""
        if meta.dns_query and meta.dns_query not in flow.dns_queries:
            flow.dns_queries.append(meta.dns_query)

        if meta.dns_answers:
            for answer in meta.dns_answers:
                if answer not in flow.dns_answers:
                    flow.dns_answers.append(answer)

        if meta.tls_sni:
            flow.tls_sni = meta.tls_sni

        if meta.http_user_agent and meta.http_user_agent not in flow.http_user_agents:
            flow.http_user_agents.append(meta.http_user_agent)

        if meta.http_host and meta.http_host not in flow.http_hosts:
            flow.http_hosts.append(meta.http_host)

        # Infer app protocol from metadata if not set by DPI
        if flow.app_protocol == "Unknown":
            if meta.dns_query:
                flow.app_protocol = "DNS"
            elif meta.http_method:
                flow.app_protocol = "HTTP"
            elif meta.tls_sni:
                flow.app_protocol = "TLS"

    def _emit_event(self, event_type: FlowEventType, flow: FlowRecord) -> None:
        """Emit a flow event to all registered handlers."""
        event = FlowEvent(
            event_type=event_type,
            flow=flow,
            timestamp=time.time(),
        )
        for handler in self._flow_event_handlers:
            try:
                handler(event)
            except Exception as e:
                logger.error("flow_event_handler_error",
                              handler=handler.__name__, error=str(e))

    # ── Flow Lifecycle Management ────────────────────────────────

    def cleanup_stale_flows(self) -> int:
        """
        Remove timed-out and finished flows from the flow table.
        Emits FLOW_END events for timed-out flows.

        Returns the number of flows cleaned up.
        """
        now = time.time()
        to_remove = []

        for flow_id, flow in self._flows.items():
            # Already finished (FIN/RST seen)
            if flow.status == FlowStatus.FINISHED:
                to_remove.append(flow_id)
                continue

            # Idle timeout
            idle_time = now - flow.last_activity
            if idle_time > self.config.flow_timeout_idle:
                flow.status = FlowStatus.TIMED_OUT
                self._emit_event(FlowEventType.FLOW_END, flow)
                to_remove.append(flow_id)
                continue

            # Active timeout (very long-lived flow)
            active_time = now - flow.start_time
            if active_time > self.config.flow_timeout_active:
                flow.status = FlowStatus.TIMED_OUT
                self._emit_event(FlowEventType.FLOW_END, flow)
                to_remove.append(flow_id)

        for flow_id in to_remove:
            del self._flows[flow_id]

        self._timed_out_flows += len(to_remove)

        if to_remove:
            logger.debug("flows_cleaned",
                          removed=len(to_remove),
                          active=len(self._flows))

        return len(to_remove)

    async def start_cleanup_loop(self) -> None:
        """Start the periodic flow cleanup loop (runs as asyncio task)."""
        logger.info("flow_cleanup_loop_started",
                      interval=self.config.flow_cleanup_interval)
        while True:
            await asyncio.sleep(self.config.flow_cleanup_interval)
            self.cleanup_stale_flows()

    # ── Accessors ────────────────────────────────────────────────

    def get_active_flows(self) -> list[FlowRecord]:
        """Return all currently active flows."""
        return [f for f in self._flows.values()
                if f.status == FlowStatus.ACTIVE]

    def get_flow(self, flow_id: str) -> Optional[FlowRecord]:
        """Look up a flow by its ID."""
        return self._flows.get(flow_id)

    @property
    def active_count(self) -> int:
        return len(self._flows)

    @property
    def total_count(self) -> int:
        return self._total_flows

    @property
    def timed_out_count(self) -> int:
        return self._timed_out_flows
