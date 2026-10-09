"""Database models. Sensor data lives in one long-format `readings` table (time-series friendly:
index on facility/module/ts, can be converted to a TimescaleDB hypertable via db/timescale.sql)."""
from __future__ import annotations
from datetime import datetime
from sqlalchemy import String, Float, Integer, DateTime, Text, Index
from sqlalchemy.orm import Mapped, mapped_column
from .session import Base


class Reading(Base):
    __tablename__ = "readings"
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    facility_id: Mapped[str] = mapped_column(String(40))
    ts: Mapped[datetime] = mapped_column(DateTime)
    module: Mapped[str] = mapped_column(String(20))
    zone: Mapped[str] = mapped_column(String(40))
    entity: Mapped[str] = mapped_column(String(60))
    metric: Mapped[str] = mapped_column(String(40))
    value: Mapped[float] = mapped_column(Float)
    label: Mapped[str] = mapped_column(String(30), default="")  # injected ground-truth anomaly label (simulator only)
    __table_args__ = (Index("ix_readings_main", "facility_id", "module", "ts"),
                      Index("ix_readings_entity", "facility_id", "entity", "metric", "ts"))


class Incident(Base):
    __tablename__ = "incidents"
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    facility_id: Mapped[str] = mapped_column(String(40), index=True)
    ts: Mapped[datetime] = mapped_column(DateTime)
    zone: Mapped[str] = mapped_column(String(40))
    kind: Mapped[str] = mapped_column(String(40))
    severity: Mapped[int] = mapped_column(Integer)  # 1 minor .. 4 critical
    status: Mapped[str] = mapped_column(String(20), default="open")


class User(Base):
    __tablename__ = "users"
    username: Mapped[str] = mapped_column(String(40), primary_key=True)
    name: Mapped[str] = mapped_column(String(80))
    role: Mapped[str] = mapped_column(String(20))
    password_hash: Mapped[str] = mapped_column(String(200))


class ActionItem(Base):
    """Status of a recommendation (keyed by a stable hash) as it moves through Pending, In progress, Done."""
    __tablename__ = "actions"
    key: Mapped[str] = mapped_column(String(40), primary_key=True)
    facility_id: Mapped[str] = mapped_column(String(40), index=True)
    title: Mapped[str] = mapped_column(String(200))
    owner: Mapped[str] = mapped_column(String(20))
    status: Mapped[str] = mapped_column(String(20), default="Pending")
    updated_by: Mapped[str] = mapped_column(String(40), default="")
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


class AuditLog(Base):
    """Audit trail: every generated recommendation is logged with the inputs behind it."""
    __tablename__ = "audit_log"
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    ts: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    facility_id: Mapped[str] = mapped_column(String(40), index=True)
    actor: Mapped[str] = mapped_column(String(40))
    event: Mapped[str] = mapped_column(String(40))
    detail: Mapped[str] = mapped_column(Text)


class FacilityOverride(Base):
    __tablename__ = "facility_overrides"
    facility_id: Mapped[str] = mapped_column(String(40), primary_key=True)
    payload: Mapped[str] = mapped_column(Text)
