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


class DeviceRegistry:
    """
    Manager class for SENTINEL device and threat records.
    Handles database connection, session management, and CRUD operations.
    """

    def __init__(self, db_url: str = "sqlite:///data/sentinel.db"):
        self.engine = create_engine(db_url, connect_args={"check_same_thread": False})
        Base.metadata.create_all(self.engine)
        self.SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=self.engine)

    def get_session(self) -> Session:
        """Create a new database session."""
        return self.SessionLocal()

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

    def get_recent_threats(self, limit: int = 50) -> list[ThreatEventModel]:
        """List the most recent threat events across all devices."""
        session = self.get_session()
        try:
            return session.query(ThreatEventModel).order_by(
                ThreatEventModel.timestamp.desc()
            ).limit(limit).all()
        finally:
            session.close()

    # ── Firewall Rule Operations ──────────────────────────────────

    def get_firewall_rules(self) -> list[FirewallRuleModel]:
        session = self.get_session()
        try:
            return session.query(FirewallRuleModel).order_by(FirewallRuleModel.created_at).all()
        finally:
            session.close()

    def add_firewall_rule(self, protocol: str, target: str, action: str, description: str = "") -> FirewallRuleModel:
        session = self.get_session()
        try:
            rule_id = f"FW-{uuid.uuid4().hex[:4].upper()}"
            rule = FirewallRuleModel(
                rule_id=rule_id, protocol=protocol, target=target,
                action=action, description=description, enabled=1,
            )
            session.add(rule)
            session.commit()
            session.refresh(rule)
            return rule
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
