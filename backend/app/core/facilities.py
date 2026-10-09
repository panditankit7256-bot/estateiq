"""Facility configuration loader (YAML files + admin overrides stored in the database)."""
from __future__ import annotations
import copy, json
from functools import lru_cache
import yaml
from fastapi import HTTPException
from .config import settings


@lru_cache(maxsize=1)
def _base_configs() -> dict[str, dict]:
    out = {}
    for path in sorted((settings.config_dir / "facilities").glob("*.yaml")):
        cfg = yaml.safe_load(path.read_text(encoding="utf-8"))
        out[cfg["id"]] = cfg
    return out


def _deep_merge(a: dict, b: dict) -> dict:
    for k, v in b.items():
        if isinstance(v, dict) and isinstance(a.get(k), dict):
            _deep_merge(a[k], v)
        else:
            a[k] = v
    return a


def list_facility_ids() -> list[str]:
    return list(_base_configs())


def get_facility(fid: str, overrides: dict | None = None) -> dict:
    base = _base_configs().get(fid)
    if base is None:
        raise HTTPException(404, f"Unknown facility '{fid}'")
    cfg = copy.deepcopy(base)
    if overrides:
        _deep_merge(cfg, overrides)
    return cfg


def load_with_overrides(fid: str) -> dict:
    """Facility config merged with admin overrides from the DB."""
    from ..db.session import SessionLocal
    from ..db.models import FacilityOverride
    with SessionLocal() as s:
        row = s.get(FacilityOverride, fid)
        return get_facility(fid, json.loads(row.payload) if row else None)
