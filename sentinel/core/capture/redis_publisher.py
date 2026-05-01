"""
SENTINEL Layer 1 — Redis Publisher

Publishes structured events to Redis pub/sub channels for consumption
by upstream layers (Device Discovery, AI Engine, Dashboard).

Channels:
  sentinel:flows      — Flow lifecycle events (new, update, end)
  sentinel:packets    — Raw packet events (for real-time dashboard)
  sentinel:discovery  — Device discovery events (ARP, mDNS, SSDP, DHCP)
  sentinel:stats      — Capture engine statistics
"""

from __future__ import annotations

import json
import time
from typing import Optional

import structlog

from sentinel.core.capture.config import CaptureConfig
from sentinel.core.capture.models import (
    CaptureStats, DiscoveryEvent, FlowEvent, PacketMeta,
)

logger = structlog.get_logger(__name__)


class RedisPublisher:
    """
    Publishes SENTINEL events to Redis pub/sub channels.

    Features:
    - Automatic connection with retry logic
    - Graceful degradation when Redis is unavailable
    - JSON serialization of Pydantic models
    - Connection health monitoring
    """

    def __init__(self, config: CaptureConfig):
        self.config = config
        self._client = None
        self._connected = False
        self._last_connect_attempt: float = 0.0
        self._connect_retry_interval: float = 5.0  # seconds
        self._publish_count: int = 0
        self._publish_errors: int = 0

    def connect(self) -> bool:
        """
        Establish connection to Redis.
        Returns True if connected successfully.
        """
        try:
            import redis

            self._client = redis.Redis(
                host=self.config.redis_host,
                port=self.config.redis_port,
                db=self.config.redis_db,
                password=self.config.redis_password or None,
                socket_connect_timeout=3,
                socket_timeout=3,
                retry_on_timeout=True,
                decode_responses=False,
            )

            # Test connection
            self._client.ping()
            self._connected = True
            logger.info("redis_connected",
                         host=self.config.redis_host,
                         port=self.config.redis_port)
            return True

        except ImportError:
            logger.error("redis_not_installed",
                          msg="Install with: pip install redis")
            return False
        except Exception as e:
            logger.warning("redis_connect_failed", error=str(e))
            self._connected = False
            self._last_connect_attempt = time.time()
            return False

    def disconnect(self) -> None:
        """Close the Redis connection."""
        if self._client:
            try:
                self._client.close()
            except Exception:
                pass
        self._connected = False
        logger.info("redis_disconnected",
                      published=self._publish_count,
                      errors=self._publish_errors)

    @property
    def is_connected(self) -> bool:
        return self._connected

    def _ensure_connected(self) -> bool:
        """
        Check connection and attempt reconnection if needed.
        Rate-limits reconnection attempts.
        """
        if self._connected:
            return True

        now = time.time()
        if now - self._last_connect_attempt < self._connect_retry_interval:
            return False

        self._last_connect_attempt = now
        return self.connect()

    def _publish(self, channel: str, data: str) -> bool:
        """
        Internal publish with error handling and reconnection.

        Args:
            channel: Redis pub/sub channel name
            data: JSON-serialized string

        Returns:
            True if published successfully.
        """
        if not self._ensure_connected():
            return False

        try:
            self._client.publish(channel, data.encode("utf-8"))
            self._publish_count += 1
            return True
        except Exception as e:
            self._publish_errors += 1
            self._connected = False
            logger.warning("redis_publish_error",
                            channel=channel, error=str(e))
            return False

    # ── Public Publishing Methods ────────────────────────────────

    def publish_flow_event(self, event: FlowEvent) -> bool:
        """Publish a flow lifecycle event to sentinel:flows channel."""
        data = event.model_dump_json()
        return self._publish(self.config.redis_channel_flows, data)

    def publish_discovery_event(self, event: DiscoveryEvent) -> bool:
        """Publish a device discovery event to sentinel:discovery channel."""
        data = event.model_dump_json()
        return self._publish(self.config.redis_channel_discovery, data)

    def publish_stats(self, stats: CaptureStats) -> bool:
        """Publish capture statistics to sentinel:stats channel."""
        data = stats.model_dump_json()
        return self._publish(self.config.redis_channel_stats, data)

    def publish_raw_packet(self, meta: PacketMeta) -> bool:
        """
        Publish a raw packet event to sentinel:packets channel.

        Note: This is high-frequency. Only enable for dashboard
        real-time view or debugging. In production, prefer flow events.
        """
        # Only publish a compact subset to avoid flooding Redis
        compact = json.dumps({
            "ts": round(meta.timestamp, 3),
            "src": meta.src_ip,
            "dst": meta.dst_ip,
            "sport": meta.src_port,
            "dport": meta.dst_port,
            "proto": meta.protocol.value,
            "len": meta.length,
            "mac_src": meta.src_mac,
            "dns": meta.dns_query,
            "sni": meta.tls_sni,
            "http_host": meta.http_host,
        })
        return self._publish(self.config.redis_channel_packets, compact)
