"""Create tables, seed demo users and generate synthetic facility data on demand."""
from __future__ import annotations
import threading
from datetime import datetime
import pandas as pd
from sqlalchemy import select, func, insert
from ..core.config import settings
from ..core.facilities import get_facility
from ..core.security import hash_password
from ..simulator.generator import generate
from ..services.cache import bump
from .models import Reading, Incident, User
from .session import Base, engine, SessionLocal

DEMO_USERS = [("admin", "Dr. A. Mohanty (Registrar)", "administrator", "admin123"),
              ("ops", "S. Behera (Estate Operations)", "operations", "ops123"),
              ("green", "P. Nayak (Sustainability Officer)", "sustainability", "green123")]
_locks: dict[str, threading.Lock] = {}


def init_db() -> None:
    Base.metadata.create_all(engine)
    with SessionLocal() as s:
        for u, name, role, pw in DEMO_USERS:
            if s.get(User, u) is None:
                s.add(User(username=u, name=name, role=role, password_hash=hash_password(pw)))
        s.commit()


def has_data(fid: str) -> bool:
    with SessionLocal() as s:
        return (s.scalar(select(func.count()).select_from(Reading).where(Reading.facility_id == fid)) or 0) > 0


def seed_facility(fid: str, days: int | None = None, end: datetime | None = None, force: bool = False) -> int:
    """Generate synthetic data for a facility (idempotent unless force=True). Returns number of readings."""
    lock = _locks.setdefault(fid, threading.Lock())
    with lock:
        if has_data(fid) and not force:
            return 0
        cfg = get_facility(fid)
        end = end or (datetime.fromisoformat(settings.fixed_now) if settings.fixed_now else datetime.now().replace(minute=0, second=0, microsecond=0))
        readings, incidents = generate(cfg, end, days or settings.seed_days)
        with SessionLocal() as s:
            if force:
                s.execute(Reading.__table__.delete().where(Reading.facility_id == fid))
                s.execute(Incident.__table__.delete().where(Incident.facility_id == fid))
            readings = readings.assign(facility_id=fid)
            readings["ts"] = pd.to_datetime(readings["ts"]).dt.to_pydatetime()
            recs = readings.to_dict("records")
            for i in range(0, len(recs), 20000):
                s.execute(insert(Reading.__table__), recs[i:i + 20000])
            irecs = [{**r, "facility_id": fid, "ts": r["ts"].to_pydatetime()} for r in incidents.to_dict("records")]
            if irecs:
                s.execute(insert(Incident.__table__), irecs)
            s.commit()
        bump(fid)
        return len(recs)
