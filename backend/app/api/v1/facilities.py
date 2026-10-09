import json
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from ...core.facilities import get_facility, list_facility_ids, load_with_overrides
from ...core.security import current_user, require_roles
from ...db.models import FacilityOverride, AuditLog
from ...db.session import SessionLocal
from ...services.cache import bump

router = APIRouter(prefix="/facilities", tags=["facilities"])


@router.get("")
def list_facilities(user: dict = Depends(current_user)):
    out = []
    for fid in list_facility_ids():
        c = get_facility(fid)
        out.append({"id": fid, "name": c["name"], "type": c["type"], "city": c["city"], "state": c["state"], "zones": len(c["zones"])})
    return out


@router.get("/{fid}")
def get_one(fid: str, user: dict = Depends(current_user)):
    return load_with_overrides(fid)


class ConfigPatch(BaseModel):
    thresholds: dict[str, float] | None = None
    tariff: dict[str, float] | None = None
    emission: dict[str, float] | None = None
    score_weights: dict[str, float] | None = None


@router.put("/{fid}/config")
def update_config(fid: str, patch: ConfigPatch, user: dict = Depends(require_roles("administrator"))):
    current = load_with_overrides(fid)
    for section in ("thresholds", "tariff", "emission", "score_weights"):
        vals = getattr(patch, section)
        if vals:
            bad = [k for k in vals if k not in current[section]]
            if bad:
                raise HTTPException(422, f"Unknown {section} keys: {bad}")
    with SessionLocal() as s:
        row = s.get(FacilityOverride, fid)
        data = json.loads(row.payload) if row else {}
        for section in ("thresholds", "tariff", "emission", "score_weights"):
            vals = getattr(patch, section)
            if vals:
                data.setdefault(section, {}).update(vals)
        if "score_weights" in data and abs(sum({**current["score_weights"], **data["score_weights"]}.values()) - 1) > 0.01:
            raise HTTPException(422, "score_weights must sum to 1.0")
        if row:
            row.payload = json.dumps(data)
        else:
            s.add(FacilityOverride(facility_id=fid, payload=json.dumps(data)))
        s.add(AuditLog(facility_id=fid, actor=user["sub"], event="config_update", detail=json.dumps(patch.model_dump(exclude_none=True))))
        s.commit()
    bump(fid)
    return load_with_overrides(fid)
