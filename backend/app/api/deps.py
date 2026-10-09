from fastapi import Depends, HTTPException, Query
from ..core.config import settings
from ..core.facilities import list_facility_ids
from ..core.security import current_user


def facility_id(facility: str = Query(default=None)) -> str:
    fid = facility or settings.default_facility
    if fid not in list_facility_ids():
        raise HTTPException(404, f"Unknown facility '{fid}'")
    return fid


User = Depends(current_user)
