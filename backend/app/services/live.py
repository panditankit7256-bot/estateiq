"""Live demo support: append a few new simulated hours (optionally with an injected incident)."""
from __future__ import annotations
import numpy as np
import pandas as pd
from sqlalchemy import insert
from ..db.models import Reading
from ..db.session import SessionLocal
from . import data as D
from .cache import bump
from . import analytics as A

SPIKES = {"leak": "leak", "pollution": "pollution_episode", "energy": "energy_spike", "bins": "bin_overflow", "outage": ""}


def append_hours(fid: str, spike: str | None = None, hours: int = 3, seed: int | None = None) -> dict:
    cfg = A.cfg_of(fid)
    rng = np.random.default_rng(seed)
    last = D.last_ts(fid)
    frames = [D.load(fid, m, days=14) for m in ("air", "energy", "water", "waste", "traffic", "assets", "weather")]
    base = pd.concat([f.assign(module=m) for f, m in zip(frames, ("air", "energy", "water", "waste", "traffic", "assets", "weather"))])
    base = base[base["metric"] != "days_since_service"]
    base["hour"] = base["ts"].dt.hour
    typical = base.groupby(["module", "zone", "entity", "metric", "hour"])["value"].median()
    lastval = base.sort_values("ts").groupby(["module", "zone", "entity", "metric"])["value"].last()
    keys = lastval.index.tolist()
    zm = D.zone_map(cfg)
    wet = [z for z in cfg["zones"] if z["type"] != "parking"]
    big_water = max(wet, key=lambda z: z["water_kld"])["id"]
    big_energy = max(wet, key=lambda z: z["load_kw"])["id"]
    pm_zone = next((z["id"] for z in cfg["zones"] if z["type"] in ("utility", "industrial")), cfg["zones"][0]["id"])
    rows = []
    site_kwh = {}
    for k in range(1, hours + 1):
        ts = last + pd.Timedelta(hours=k)
        for (module, zone, entity, metric) in keys:
            t = typical.get((module, zone, entity, metric, ts.hour), lastval[(module, zone, entity, metric)])
            v = float(t) * (1 + rng.normal(0, 0.03))
            label = ""
            if module == "waste":
                v = min(100.0, float(lastval[(module, zone, entity, metric)]) + 2.4 * k)
            if spike == "leak" and module == "water" and zone == big_water and metric == "flow_kl":
                v += 0.8 * float(base[(base.module == "water") & (base.zone == zone)].groupby("ts")["value"].sum().mean()); label = "leak"
            if spike == "pollution" and module == "air" and zone == pm_zone and metric in ("pm25", "pm10"):
                v *= 4.5 if metric == "pm25" else 3.5; label = "pollution_episode"
            if spike == "energy" and module == "energy" and zone == big_energy and metric == "kwh":
                v *= 2.3; label = "energy_spike"
            if spike == "bins" and module == "waste" and zone in [z["id"] for z in cfg["zones"] if z["type"] == "canteen"]:
                v = 100.0; label = "bin_overflow"
            if module == "energy" and metric == "kwh":
                site_kwh[ts] = site_kwh.get(ts, 0) + v
            rows.append({"facility_id": fid, "ts": ts.to_pydatetime(), "module": module, "zone": zone, "entity": entity, "metric": metric, "value": round(v, 3), "label": label})
        if spike == "outage":
            for r in rows:
                if r["ts"] == ts.to_pydatetime() and r["metric"] == "dg_kwh":
                    r["value"] = round(0.85 * site_kwh.get(ts, 0), 3)
    with SessionLocal() as s:
        s.execute(insert(Reading.__table__), rows)
        s.commit()
    bump(fid)
    msg = {"leak": f"Simulated leak in {zm[big_water]['name']}", "pollution": f"Simulated pollution episode near {zm[pm_zone]['name']}",
           "energy": f"Simulated energy spike in {zm[big_energy]['name']}", "bins": "Simulated missed collection: canteen bins overflowing",
           "outage": "Simulated grid outage: DG running", None: "Advanced simulated clock"}[spike]
    return {"added_hours": hours, "from": (last + pd.Timedelta(hours=1)).isoformat(), "to": (last + pd.Timedelta(hours=hours)).isoformat(), "spike": spike, "message": msg}
