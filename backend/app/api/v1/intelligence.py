import csv, io, json
from datetime import datetime
from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field
from sqlalchemy import select
from ...core.security import current_user, require_roles
from ...db.models import ActionItem, AuditLog
from ...db.session import SessionLocal
from ...engine import recommendations as R, insights as I, llm
from ...services import analytics as A
from ..deps import facility_id

router = APIRouter(tags=["intelligence"])
STATUSES = ("Pending", "In progress", "Done")


@router.get("/recommendations")
def recommendations(polish: bool = False, fid: str = Depends(facility_id), user: dict = Depends(current_user)):
    recs = R.for_role(fid, user["role"], polish)
    with SessionLocal() as s:
        known = {a.key: a for a in s.scalars(select(ActionItem).where(ActionItem.facility_id == fid))}
        for r in recs:
            a = known.get(r["key"])
            if a is None:
                a = ActionItem(key=r["key"], facility_id=fid, title=r["title"], owner=r["owner"])
                s.add(a)
                s.add(AuditLog(facility_id=fid, actor="engine", event="recommendation", detail=json.dumps({k: r[k] for k in ("key", "title", "detected", "impact", "confidence", "basis")}, default=str)))
            r["status"] = a.status
        s.commit()
    return {"role": user["role"], "llm_enabled": llm.enabled(), "recommendations": recs}


class ActionPatch(BaseModel):
    status: str


@router.patch("/actions/{key}")
def update_action(key: str, body: ActionPatch, user: dict = Depends(current_user)):
    if body.status not in STATUSES:
        raise HTTPException(422, f"status must be one of {STATUSES}")
    with SessionLocal() as s:
        a = s.get(ActionItem, key)
        if a is None:
            raise HTTPException(404, "Unknown action")
        if user["role"] != "administrator" and a.owner != user["role"]:
            raise HTTPException(403, "Only the owner role or an administrator can update this action")
        a.status, a.updated_by, a.updated_at = body.status, user["sub"], datetime.utcnow()
        s.add(AuditLog(facility_id=a.facility_id, actor=user["sub"], event="action_status", detail=f"{a.title} -> {body.status}"))
        s.commit()
        return {"key": key, "status": a.status, "updated_by": a.updated_by}


class Scenario(BaseModel):
    add_solar_kw: float = Field(0, ge=0, le=5000)
    ac_setpoint_delta_c: float = Field(0, ge=0, le=5)
    shift_peak_pct: float = Field(0, ge=0, le=100)
    extra_collections_per_week: float = Field(0, ge=0, le=14)
    fix_leak: bool = False
    occupancy_change_pct: float = Field(0, ge=-50, le=100)


@router.post("/scenarios/simulate")
def simulate(body: Scenario, fid: str = Depends(facility_id), user: dict = Depends(require_roles("administrator", "operations", "sustainability"))):
    return A.simulate(fid, body.model_dump())


class Chat(BaseModel):
    question: str = Field(min_length=3, max_length=400)


@router.post("/insights/chat")
def chat(body: Chat, fid: str = Depends(facility_id), user: dict = Depends(current_user)):
    return I.ask(fid, body.question)


class Advisory(BaseModel):
    kind: str = Field("air", pattern="^(air|heat|water|waste|general)$")
    channel: str = Field("email", pattern="^(email|sms)$")


@router.post("/advisories/generate")
def advisory(body: Advisory, fid: str = Depends(facility_id), user: dict = Depends(require_roles("administrator", "operations"))):
    return I.advisory(fid, body.kind, body.channel)


@router.get("/audit")
def audit(limit: int = 50, fid: str = Depends(facility_id), user: dict = Depends(require_roles("administrator"))):
    with SessionLocal() as s:
        rows = s.scalars(select(AuditLog).where(AuditLog.facility_id == fid).order_by(AuditLog.id.desc()).limit(limit)).all()
    return [{"ts": r.ts.isoformat(), "actor": r.actor, "event": r.event, "detail": r.detail} for r in rows]


@router.get("/reports/export")
def export(kind: str = "scorecard", fid: str = Depends(facility_id), user: dict = Depends(current_user)):
    buf = io.StringIO(); w = csv.writer(buf)
    if kind == "scorecard":
        sc = A.scorecard(fid)
        w.writerow(["window", "overall", "grade"] + list(sc["current"]["sub"]) + list(sc["current"]["raw"]))
        for h in sc["history"]:
            w.writerow([h["label"], h["overall"], h["grade"]] + list(h["sub"].values()) + list(h["raw"].values()))
    elif kind == "recommendations":
        w.writerow(["urgency", "owner", "module", "title", "detected", "action", "confidence"])
        for r in R.for_role(fid, user["role"]):
            w.writerow([r["urgency"], r["owner"], r["module"], r["title"], r["detected"], r["action"], r["confidence"]])
    elif kind == "energy_daily":
        d = A.energy_view(fid)["daily"]
        w.writerow(list(d)); [w.writerow(row) for row in zip(*d.values())]
    else:
        raise HTTPException(404, "kind must be scorecard, recommendations or energy_daily")
    buf.seek(0)
    return StreamingResponse(iter([buf.getvalue()]), media_type="text/csv", headers={"Content-Disposition": f'attachment; filename="{fid}_{kind}.csv"'})
