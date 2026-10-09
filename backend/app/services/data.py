"""Data access helpers (SQL -> pandas)."""
from __future__ import annotations
import pandas as pd
from sqlalchemy import select, func
from ..db.models import Reading, Incident
from ..db.session import engine, SessionLocal
from ..db.seed import has_data, seed_facility
from fastapi import HTTPException


def ensure_data(fid: str) -> None:
    if not has_data(fid):
        seed_facility(fid)


def last_ts(fid: str) -> pd.Timestamp:
    ensure_data(fid)
    with SessionLocal() as s:
        t = s.scalar(select(func.max(Reading.ts)).where(Reading.facility_id == fid))
    return pd.Timestamp(t)


def load(fid: str, module: str, metric: str | None = None, days: int | None = None, zone: str | None = None) -> pd.DataFrame:
    ensure_data(fid)
    q = select(Reading.ts, Reading.zone, Reading.entity, Reading.metric, Reading.value, Reading.label).where(
        Reading.facility_id == fid, Reading.module == module)
    if metric:
        q = q.where(Reading.metric == metric)
    if zone:
        q = q.where(Reading.zone == zone)
    if days:
        q = q.where(Reading.ts > (last_ts(fid) - pd.Timedelta(days=days)).to_pydatetime())
    df = pd.read_sql(q, engine)
    df["ts"] = pd.to_datetime(df["ts"])
    return df.sort_values("ts").reset_index(drop=True)


def incidents(fid: str) -> pd.DataFrame:
    ensure_data(fid)
    df = pd.read_sql(select(Incident.id, Incident.ts, Incident.zone, Incident.kind, Incident.severity, Incident.status).where(Incident.facility_id == fid), engine)
    df["ts"] = pd.to_datetime(df["ts"])
    return df


def bins_meta(cfg: dict) -> dict[str, dict]:
    """Deterministic bin positions: small offsets around the zone centre."""
    cycle = ["biomedical", "wet", "dry", "e-waste"] if cfg["type"] == "hospital" else ["wet", "dry", "e-waste"]
    out = {}
    for z in cfg["zones"]:
        for i in range(z["bins"]):
            ang = (i + 1) * 2.1 + sum(map(ord, z["id"]))
            out[f"bin-{z['id']}-{i + 1}"] = {"id": f"bin-{z['id']}-{i + 1}", "zone": z["id"], "type": cycle[i % len(cycle)],
                                              "lat": z["lat"] + 0.00022 * (1 + i % 3) * float(__import__("math").cos(ang)),
                                              "lon": z["lon"] + 0.00022 * (1 + i % 3) * float(__import__("math").sin(ang))}
    return out


def zone_map(cfg: dict) -> dict[str, dict]:
    return {z["id"]: z for z in cfg["zones"]}


def validate_reading(r: dict, cfg: dict) -> str | None:
    """Range / schema validation for ingested readings. Returns an error string or None."""
    ranges = {"pm25": (0, 1000), "pm10": (0, 2000), "no2": (0, 1000), "kwh": (0, 1e6), "flow_kl": (0, 1e4), "fill_pct": (0, 100),
              "occupancy_pct": (0, 100), "vehicles_in": (0, 1e5), "util_pct": (0, 100), "vibration_mm_s": (0, 100), "temp_c": (-20, 120)}
    for k in ("ts", "zone", "entity", "metric", "value"):
        if k not in r:
            return f"missing field '{k}'"
    if r["zone"] not in zone_map(cfg) and r["zone"] != "_site":
        return f"unknown zone '{r['zone']}'"
    try:
        v = float(r["value"])
    except (TypeError, ValueError):
        return "value is not numeric"
    if v != v:
        return "value is NaN"
    lo, hi = ranges.get(r["metric"], (-1e9, 1e9))
    if not lo <= v <= hi:
        return f"{r['metric']}={v} outside plausible range [{lo}, {hi}]"
    return None
