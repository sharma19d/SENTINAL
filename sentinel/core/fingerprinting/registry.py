"""
SENTINEL Layer 2 — Device Registry

SQLAlchemy-based registry for persistent storage of discovered devices
and threat events. Manages the SQLite database schema and provides
CRUD operations for device profiles and security alerts.
"""

from __future__ import annotations

import json
import uuid
from datetime import datetime
from typing import Any, Optional

from sqlalchemy import (
    Boolean, Column, DateTime, Float, Integer, String, Text, create_engine,
)
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker, Session

Base = declarative_base()


class DeviceModel(Base):
    """
    SQLAlchemy model for the 'devices' table.
    Stores complete fingerprinting and risk data for each network device.
    """
    __tablename__ = "devices"

    device_id = Column(String, primary_key=True)
    mac = Column(String, nullable=False, index=True)
    ip = Column(String, index=True)
    vendor = Column(String)
    os_guess = Column(String)
    firmware_ver = Column(String)
    open_ports = Column(Text, default="[]")  # Stored as JSON array
    cve_list = Column(Text, default="[]")    # Stored as JSON array of {cve_id, score, desc}
    risk_score = Column(Float, default=0.0)
    last_seen = Column(DateTime, default=datetime.utcnow)
    baseline_path = Column(String)
    is_quarantined = Column(Integer, default=0)
    # Gateway MAC of the network this device was observed on. A device is
    # only meaningful on its own network — without this the registry mixes
    # hardware from every network the appliance has ever been attached to.
    network_id = Column(String, index=True)

    def to_dict(self) -> dict[str, Any]:
        """Convert model to dictionary, parsing JSON fields."""
        data = {c.name: getattr(self, c.name) for c in self.__table__.columns}
        data["open_ports"] = json.loads(self.open_ports or "[]")
        data["cve_list"] = json.loads(self.cve_list or "[]")
        if isinstance(data["last_seen"], datetime):
            data["last_seen"] = data["last_seen"].isoformat()
        return data


class ThreatEventModel(Base):
    """
    SQLAlchemy model for the 'threat_events' table.
    Records every security event classified by the AI Engine.
    """
    __tablename__ = "threat_events"

    event_id = Column(String, primary_key=True)
    device_id = Column(String, index=True)
    tactic = Column(String)
    technique_id = Column(String)
    confidence = Column(Float)
    severity = Column(Integer)
    summary = Column(Text)
    indicators = Column(Text, default="[]")  # Stored as JSON array
    action_taken = Column(String)
    timestamp = Column(DateTime, default=datetime.utcnow)
    resolved = Column(Integer, default=0)
    network_id = Column(String, index=True)

    def to_dict(self) -> dict[str, Any]:
        """Convert model to dictionary."""
        data = {c.name: getattr(self, c.name) for c in self.__table__.columns}
        data["indicators"] = json.loads(self.indicators or "[]")
        if isinstance(data["timestamp"], datetime):
            data["timestamp"] = data["timestamp"].isoformat()
        return data


class FirewallRuleModel(Base):
    __tablename__ = "firewall_rules"

    rule_id = Column(String, primary_key=True)
    protocol = Column(String, nullable=False)
    target = Column(String, nullable=False)
    action = Column(String, nullable=False)
    enabled = Column(Integer, default=1)
    description = Column(String, default="")
    created_at = Column(DateTime, default=datetime.utcnow)
    # NULL means the rule is network-agnostic (e.g. target 0.0.0.0/0) and
    # applies everywhere; a value scopes it to one network's address space.
    network_id = Column(String, index=True)


class NetworkModel(Base):
    """Every network the appliance has been attached to, keyed by gateway MAC."""

    __tablename__ = "networks"

    network_id = Column(String, primary_key=True)   # gateway MAC
    label = Column(String, default="")
    gateway_ip = Column(String)
    subnet = Column(String)
    interface = Column(String)
    first_seen = Column(DateTime, default=datetime.utcnow)
    last_seen = Column(DateTime, default=datetime.utcnow)

    def to_dict(self) -> dict[str, Any]:
        data = {c.name: getattr(self, c.name) for c in self.__table__.columns}
        for key in ("first_seen", "last_seen"):
            if isinstance(data[key], datetime):
                data[key] = data[key].isoformat()
        return data


class DeviceRegistry:
    """
    Manager class for SENTINEL device and threat records.
    Handles database connection, session management, and CRUD operations.
    """

    def __init__(self, db_url: str = "sqlite:///data/sentinel.db"):
        self.engine = create_engine(db_url, connect_args={"check_same_thread": False})
        Base.metadata.create_all(self.engine)
        self._migrate_network_columns()
        self.SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=self.engine)

    def _migrate_network_columns(self) -> None:
        """
        Add `network_id` to pre-existing tables.

        `create_all` only creates missing *tables*; it never alters an
        existing one, so databases created before network scoping was
        introduced would keep silently dropping the column on write.
        Existing rows are intentionally left with network_id = NULL,
        meaning "recorded before networks were tracked" — they are
        excluded from current-network views rather than being guessed
        into the wrong network.
        """
        from sqlalchemy import inspect, text

        inspector = inspect(self.engine)
        targets = {
            "devices": "network_id",
            "threat_events": "network_id",
            "firewall_rules": "network_id",
        }

        with self.engine.begin() as conn:
            for table, column in targets.items():
                if not inspector.has_table(table):
                    continue
                existing = {c["name"] for c in inspector.get_columns(table)}
                if column in existing:
                    continue
                conn.execute(text(f"ALTER TABLE {table} ADD COLUMN {column} VARCHAR"))
                conn.execute(
                    text(f"CREATE INDEX IF NOT EXISTS ix_{table}_{column} ON {table} ({column})")
                )

    def get_session(self) -> Session:
        """Create a new database session."""
        return self.SessionLocal()

    # ── Network Operations ───────────────────────────────────────

    def record_network(self, identity) -> None:
        """Upsert the network the appliance is currently attached to."""
        session = self.get_session()
        try:
            network = session.query(NetworkModel).filter(
                NetworkModel.network_id == identity.network_id
            ).first()

            if not network:
                network = NetworkModel(
                    network_id=identity.network_id,
                    label=f"{identity.subnet} via {identity.gateway_ip}",
                )
                session.add(network)

            network.gateway_ip = identity.gateway_ip
            network.subnet = identity.subnet
            network.interface = identity.interface
            network.last_seen = datetime.utcnow()
            session.commit()
        finally:
            session.close()

    def list_networks(self) -> list[NetworkModel]:
        session = self.get_session()
        try:
            return session.query(NetworkModel).order_by(NetworkModel.last_seen.desc()).all()
        finally:
            session.close()

    def get_devices_for_network(self, network_id: Optional[str]) -> list[DeviceModel]:
        """Devices belonging to one network. None returns every device."""
        session = self.get_session()
        try:
            query = session.query(DeviceModel)
            if network_id is not None:
                query = query.filter(DeviceModel.network_id == network_id)
            return query.all()
        finally:
            session.close()

    # ── Device Operations ────────────────────────────────────────

    def upsert_device(self, mac: str, **kwargs) -> DeviceModel:
        """
        Create or update a device record by MAC address.
        """
        session = self.get_session()
        try:
            # Use MAC as the primary device identifier if device_id not provided
            # Standardized MAC as ID: 'dev_aabbccddeeff'
            device_id = kwargs.get("device_id") or f"dev_{mac.lower().replace(':', '')}"
            
            device = session.query(DeviceModel).filter(DeviceModel.device_id == device_id).first()
            
            if not device:
                device = DeviceModel(device_id=device_id, mac=mac)
                session.add(device)
            
            # Update fields
            for key, value in kwargs.items():
                if hasattr(device, key):
                    if key in ("open_ports", "cve_list") and not isinstance(value, str):
                        setattr(device, key, json.dumps(value))
                    else:
                        setattr(device, key, value)
            
            device.last_seen = datetime.utcnow()
            session.commit()
            session.refresh(device)
            return device
        finally:
            session.close()

    def get_device(self, device_id: str) -> Optional[DeviceModel]:
        """Fetch a single device by ID."""
        session = self.get_session()
        try:
            return session.query(DeviceModel).filter(DeviceModel.device_id == device_id).first()
        finally:
            session.close()

    def list_devices(self) -> list[DeviceModel]:
        """List all discovered devices."""
        session = self.get_session()
        try:
            return session.query(DeviceModel).all()
        finally:
            session.close()

    def get_all_devices(self) -> list[DeviceModel]:
        """Alias for list_devices for API clarity."""
        return self.list_devices()

    # ── Threat Event Operations ──────────────────────────────────

    def add_threat_event(self, event_id: str, device_id: str, **kwargs) -> ThreatEventModel:
        """Record a new security threat event."""
        session = self.get_session()
        try:
            event = ThreatEventModel(event_id=event_id, device_id=device_id)
            for key, value in kwargs.items():
                if hasattr(event, key):
                    if key == "indicators" and not isinstance(value, str):
                        setattr(event, key, json.dumps(value))
                    else:
                        setattr(event, key, value)
            
            session.add(event)
            session.commit()
            session.refresh(event)
            return event
        finally:
            session.close()

    def get_device_threats(self, device_id: str) -> list[ThreatEventModel]:
        """List all threat events for a specific device."""
        session = self.get_session()
        try:
            return session.query(ThreatEventModel).filter(
                ThreatEventModel.device_id == device_id
            ).order_by(ThreatEventModel.timestamp.desc()).all()
        finally:
            session.close()

    def get_threat(self, event_id: str) -> Optional[ThreatEventModel]:
        """Fetch a single threat event by id, or None if it does not exist."""
        session = self.get_session()
        try:
            return session.query(ThreatEventModel).filter(
                ThreatEventModel.event_id == event_id
            ).first()
        finally:
            session.close()

    def set_threat_resolved(self, event_id: str, resolved: bool = True) -> bool:
        """
        Mark a threat acknowledged/resolved. Returns True if the event existed.
        Acknowledging is an analyst confirming they have triaged the event; it
        does not undo any automated action (e.g. an auto-block stays in place).
        """
        session = self.get_session()
        try:
            event = session.query(ThreatEventModel).filter(
                ThreatEventModel.event_id == event_id
            ).first()
            if event is None:
                return False
            event.resolved = 1 if resolved else 0
            session.commit()
            return True
        finally:
            session.close()

    def get_recent_threats(self, limit: int = 50,
                           network_id: Optional[str] = None) -> list[ThreatEventModel]:
        """
        Most recent threat events. When `network_id` is given, only events
        recorded on that network are returned — a threat seen on a previous
        network says nothing about the one currently attached.
        """
        session = self.get_session()
        try:
            query = session.query(ThreatEventModel)
            if network_id is not None:
                query = query.filter(ThreatEventModel.network_id == network_id)
            return query.order_by(
                ThreatEventModel.timestamp.desc()
            ).limit(limit).all()
        finally:
            session.close()

    # ── Firewall Rule Operations ──────────────────────────────────

    def get_firewall_rules(self, network_id: Optional[str] = None) -> list[FirewallRuleModel]:
        """
        Firewall rules. When `network_id` is given, returns rules scoped to
        that network plus network-agnostic ones (network_id IS NULL), since
        a rule targeting 0.0.0.0/0 applies wherever the appliance is.
        """
        session = self.get_session()
        try:
            query = session.query(FirewallRuleModel)
            if network_id is not None:
                query = query.filter(
                    (FirewallRuleModel.network_id == network_id)
                    | (FirewallRuleModel.network_id.is_(None))
                )
            return query.order_by(FirewallRuleModel.created_at).all()
        finally:
            session.close()

    def add_firewall_rule(self, protocol: str, target: str, action: str,
                          description: str = "",
                          network_id: Optional[str] = None) -> FirewallRuleModel:
        session = self.get_session()
        try:
            rule_id = f"FW-{uuid.uuid4().hex[:4].upper()}"
            rule = FirewallRuleModel(
                rule_id=rule_id, protocol=protocol, target=target,
                action=action, description=description, enabled=1,
                network_id=network_id,
            )
            session.add(rule)
            session.commit()
            session.refresh(rule)
            return rule
        finally:
            session.close()

    def get_firewall_rule(self, rule_id: str) -> Optional[FirewallRuleModel]:
        """Fetch a single firewall rule by id, or None if it does not exist."""
        session = self.get_session()
        try:
            return session.query(FirewallRuleModel).filter(
                FirewallRuleModel.rule_id == rule_id
            ).first()
        finally:
            session.close()

    def toggle_firewall_rule(self, rule_id: str) -> Optional[FirewallRuleModel]:
        session = self.get_session()
        try:
            rule = session.query(FirewallRuleModel).filter(FirewallRuleModel.rule_id == rule_id).first()
            if rule:
                rule.enabled = 0 if rule.enabled else 1
                session.commit()
                session.refresh(rule)
            return rule
        finally:
            session.close()

    def delete_firewall_rule(self, rule_id: str) -> bool:
        session = self.get_session()
        try:
            rule = session.query(FirewallRuleModel).filter(FirewallRuleModel.rule_id == rule_id).first()
            if rule:
                session.delete(rule)
                session.commit()
                return True
            return False
        finally:
            session.close()
