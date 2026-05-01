"""
SENTINEL Layer 1 — Configuration

Centralized configuration management using Pydantic Settings.
All values can be overridden via environment variables or a .env file.
"""

from __future__ import annotations

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class CaptureConfig(BaseSettings):
    """
    Configuration for the Network Capture & Packet Engine.

    Priority (highest → lowest):
        1. Environment variables
        2. .env file
        3. Default values below
    """

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # ── Network Capture ──────────────────────────────────────────
    capture_interface: str = Field(
        default="wlan0",
        description="Network interface to capture packets on. "
        "Use 'auto' to detect automatically.",
    )
    bpf_filter: str = Field(
        default="",
        description="Berkeley Packet Filter expression. "
        "Empty string captures all traffic.",
    )
    pcap_snaplen: int = Field(
        default=65535,
        description="Maximum bytes to capture per packet.",
    )

    # ── Flow Tracking ────────────────────────────────────────────
    flow_timeout_active: int = Field(
        default=120,
        description="Max seconds a flow can be active before forced expiry.",
    )
    flow_timeout_idle: int = Field(
        default=30,
        description="Seconds of inactivity before a flow is marked finished.",
    )
    flow_cleanup_interval: int = Field(
        default=10,
        description="Seconds between flow table cleanup sweeps.",
    )

    # ── Redis ────────────────────────────────────────────────────
    redis_host: str = Field(default="127.0.0.1")
    redis_port: int = Field(default=6379)
    redis_db: int = Field(default=0)
    redis_password: str = Field(default="")
    redis_channel_flows: str = Field(
        default="capture:flows",
        description="Redis pub/sub channel for flow events.",
    )
    redis_channel_packets: str = Field(
        default="capture:packets",
        description="Redis pub/sub channel for raw packet events.",
    )
    redis_channel_discovery: str = Field(
        default="capture:discovery",
        description="Redis pub/sub channel for device discovery events "
        "(ARP, mDNS, SSDP, DHCP).",
    )
    redis_channel_stats: str = Field(
        default="capture:stats",
        description="Redis pub/sub channel for capture statistics.",
    )

    # ── DPI ──────────────────────────────────────────────────────
    enable_dpi: bool = Field(
        default=True,
        description="Enable NFStream-based Deep Packet Inspection.",
    )

    # ── Logging ──────────────────────────────────────────────────
    log_level: str = Field(
        default="INFO",
        description="Logging level: DEBUG, INFO, WARNING, ERROR, CRITICAL.",
    )
    log_format: str = Field(
        default="json",
        description="Log output format: 'json' or 'console'.",
    )

    # ── Stats ────────────────────────────────────────────────────
    stats_interval: int = Field(
        default=10,
        description="Seconds between publishing capture stats to Redis.",
    )
