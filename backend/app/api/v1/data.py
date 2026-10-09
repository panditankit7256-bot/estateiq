import io
import pandas as pd
from fastapi import APIRouter, Depends, HTTPException, Query, UploadFile, File
from pydantic import BaseModel
from sqlalchemy import insert, select
from ...core.security import current_user, require_roles
from ...db.models import Reading, AuditLog
from ...db.session import SessionLocal
from ...services import analytics as A, data as D
from ...services.cache import bump
from ..deps import facility_id

router = APIRouter(tags=["data"])
MODULES = {"air": "pm25", "energy": "kwh", "water": "flow_kl", "waste": "fill_pct", "traffic": "vehicles_in", "assets": "util_pct", "weather": "temp_c"}


@router.get("/overview")
def overview(fid: str = Depends(facility_id), user: dict = Depends(current_user)):
    return A.overview(fid)


@router.get("/metrics/{module}")
def metrics(module: str, metric: str | None = None, days: int = Query(14, ge=1, le=90), granularity: str = Query("h", pattern="^(h|d)$"),
            fid: str = Depends(facility_id), user: dict = Depends(current_user)):
    if module not in MODULES:
        raise HTTPException(404, f"Unknown module '{module}'")
    return A.metric_series(fid, module, metric or MODULES[module], days, granularity)


@router.get("/forecast/{module}")
def forecast(module: str, metric: str | None = None, horizon: int = Query(24, ge=1, le=168), fid: str = Depends(facility_id), user: dict = Depends(current_user)):
    if module not in MODULES or module in ("assets", "weather"):
        raise HTTPException(404, f"Forecasting is available for air, energy, water, waste and traffic, not '{module}'")
    return A.forecast_view(fid, module, metric or MODULES[module], horizon)


@router.get("/anomalies")
def anomalies(days: int = Query(14, ge=1, le=90), module: str | None = None, fid: str = Depends(facility_id), user: dict = Depends(current_user)):
    res = A.anomalies_view(fid, days)
    if module:
        res = {**res, "events": [e for e in res["events"] if e["module"] == module]}
    return res


@router.get("/views/air")
def air(fid: str = Depends(facility_id), user: dict = Depends(current_user)): return A.air_view(fid)
@router.get("/views/energy")
def energy(days: int = 30, fid: str = Depends(facility_id), user: dict = Depends(current_user)): return A.energy_view(fid, days)
@router.get("/views/water")
def water(fid: str = Depends(facility_id), user: dict = Depends(current_user)): return A.water_view(fid)
@router.get("/views/waste")
def waste(fid: str = Depends(facility_id), user: dict = Depends(current_user)): return A.waste_view(fid)
@router.get("/waste/routes")
def waste_routes(fid: str = Depends(facility_id), user: dict = Depends(current_user)): return A.waste_view(fid)["route"]
@router.get("/views/traffic")
def traffic(fid: str = Depends(facility_id), user: dict = Depends(current_user)): return A.traffic_view(fid)
@router.get("/views/assets")
def assets(fid: str = Depends(facility_id), user: dict = Depends(current_user)): return A.assets_view(fid)
@router.get("/views/safety")
def safety(fid: str = Depends(facility_id), user: dict = Depends(current_user)): return A.safety_view(fid)
@router.get("/views/emissions")
def emissions(fid: str = Depends(facility_id), user: dict = Depends(current_user)): return A.emissions_view(fid)
@router.get("/scorecard")
def scorecard(fid: str = Depends(facility_id), user: dict = Depends(current_user)): return A.scorecard(fid)


@router.get("/data-quality")
def data_quality(fid: str = Depends(facility_id), user: dict = Depends(current_user)):
    now = D.last_ts(fid)
    anomalies = A.anomalies_view(fid)["events"]
    faults = {}
    for e in anomalies:
        if e["kind"] == "flatline":
            faults[e["entity"]] = faults.get(e["entity"], 0) + 1
    rows = []
    for m in ("air", "energy", "water", "waste", "traffic", "assets"):
        df = D.load(fid, m, days=14)
        df = df[df["metric"] != "days_since_service"]
        for (ent, met), g in df.groupby(["entity", "metric"]):
            rows.append({"module": m, "entity": ent, "metric": met, "completeness_pct": round(min(len(g) / (14 * 24), 1) * 100, 1),
                         "last_update": g["ts"].max().isoformat(), "stale_hours": int((now - g["ts"].max()).total_seconds() // 3600), "sensor_faults_14d": faults.get(ent, 0)})
    return {"as_of": now.isoformat(), "sensors": rows, "summary": {"sensors": len(rows), "avg_completeness_pct": round(sum(r["completeness_pct"] for r in rows) / max(len(rows), 1), 1),
                                                                    "faulty": sum(1 for r in rows if r["sensor_faults_14d"])}}


class ReadingIn(BaseModel):
    ts: str
    zone: str
    entity: str
    metric: str
    value: float


class IngestBody(BaseModel):
    readings: list[ReadingIn]


def _ingest(fid: str, module: str, recs: list[dict], actor: str) -> dict:
    cfg = A.cfg_of(fid)
    ok, rejected, seen = [], [], set()
    for i, r in enumerate(recs):
        err = D.validate_reading(r, cfg)
        if not err:
            try:
                r["ts"] = pd.Timestamp(r["ts"]).to_pydatetime()
            except Exception:
                err = "unparseable timestamp"
        key = (r.get("ts"), r.get("entity"), r.get("metric"))
        if not err and key in seen:
            err = "duplicate in batch"
        if err:
            rejected.append({"row": i, "reason": err}); continue
        seen.add(key)
        ok.append({"facility_id": fid, "module": module, "label": "", "ts": r["ts"], "zone": r["zone"], "entity": r["entity"], "metric": r["metric"], "value": float(r["value"])})
    if ok:
        with SessionLocal() as s:
            existing = {(t, e, m) for t, e, m in s.execute(select(Reading.ts, Reading.entity, Reading.metric).where(
                Reading.facility_id == fid, Reading.module == module, Reading.ts >= min(r["ts"] for r in ok), Reading.ts <= max(r["ts"] for r in ok)))}
            fresh = [r for r in ok if (r["ts"], r["entity"], r["metric"]) not in existing]
            rejected += [{"row": -1, "reason": "duplicate of stored reading"}] * (len(ok) - len(fresh))
            if fresh:
                s.execute(insert(Reading.__table__), fresh)
            s.add(AuditLog(facility_id=fid, actor=actor, event="ingest", detail=f"{module}: {len(fresh)} accepted, {len(rejected)} rejected"))
            s.commit()
        bump(fid)
        ok = fresh
    return {"accepted": len(ok), "rejected": len(rejected), "errors": rejected[:20]}


@router.post("/ingest/upload")
async def ingest_upload(file: UploadFile = File(...), fid: str = Depends(facility_id), user: dict = Depends(require_roles("administrator", "operations"))):
    """CSV columns: ts,module,zone,entity,metric,value"""
    df = pd.read_csv(io.BytesIO(await file.read()))
    need = {"ts", "module", "zone", "entity", "metric", "value"}
    if not need <= set(df.columns):
        raise HTTPException(422, f"CSV must contain columns {sorted(need)}")
    out = {"accepted": 0, "rejected": 0, "errors": []}
    for module, g in df.groupby("module"):
        if module not in MODULES:
            out["rejected"] += len(g); out["errors"].append({"row": -1, "reason": f"unknown module {module}"}); continue
        res = _ingest(fid, module, g[["ts", "zone", "entity", "metric", "value"]].to_dict("records"), user["sub"])
        out["accepted"] += res["accepted"]; out["rejected"] += res["rejected"]; out["errors"] += res["errors"]
    return out


@router.post("/ingest/{module}")
def ingest(module: str, body: IngestBody, fid: str = Depends(facility_id), user: dict = Depends(require_roles("administrator", "operations"))):
    if module not in MODULES:
        raise HTTPException(404, f"Unknown module '{module}'")
    return _ingest(fid, module, [r.model_dump() for r in body.readings], user["sub"])
