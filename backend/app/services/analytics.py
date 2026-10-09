"""Analytics views used by the API: metrics, forecasts, anomalies, per-module dashboards, scorecard, scenarios."""
from __future__ import annotations
import math
import numpy as np
import pandas as pd
from ..core.facilities import load_with_overrides
from ..ml import forecasting, anomaly, waste as waste_ml, maintenance, risk as risk_ml
from . import data as D
from .cache import cached

UNITS = {"kwh": "kWh", "solar_kwh": "kWh", "dg_kwh": "kWh", "flow_kl": "kL/h", "pm25": "µg/m³", "pm10": "µg/m³", "no2": "µg/m³",
         "fill_pct": "%", "occupancy_pct": "%", "vehicles_in": "vehicles/h", "queue_min": "min", "util_pct": "%",
         "vibration_mm_s": "mm/s", "temp_c": "°C", "tank_level_pct": "%", "humidity_pct": "%", "rainfall_mm": "mm"}
SUM_METRICS = {"kwh", "solar_kwh", "dg_kwh", "flow_kl", "vehicles_in", "rainfall_mm"}
AQI_BANDS = [(30, "Good", "#2e7d32"), (60, "Satisfactory", "#7cb342"), (90, "Moderate", "#f9a825"),
             (120, "Poor", "#ef6c00"), (250, "Very poor", "#c62828"), (1e9, "Severe", "#6a1b1a")]
HVAC_TYPES = {"academic", "office", "clinical", "canteen"}
GRID_ASSUMPTIONS = {"solar_kwh_per_kw_day": 4.2, "cooling_share_hvac_zones": 0.45, "saving_per_degC": 0.06, "water_cost_inr_per_kl": 18.0,
                    "annual_rain_mm": 1450, "roof_share_of_area": 0.3, "runoff_coeff": 0.8, "trip_km": 9, "kg_co2_per_km": 0.14}


def aqi_category(pm25: float) -> dict:
    for hi, name, color in AQI_BANDS:
        if pm25 <= hi:
            return {"label": name, "color": color}
    return {"label": "Severe", "color": "#6a1b1a"}


def cfg_of(fid: str) -> dict:
    return load_with_overrides(fid)


def _agg(metric: str) -> str:
    return "sum" if metric in SUM_METRICS else "mean"


def site_series(fid: str, module: str, metric: str, days: int | None = None) -> pd.Series:
    df = D.load(fid, module, metric, days)
    g = df.groupby(["ts", "entity"])["value"].first().unstack()
    s = g.sum(axis=1) if _agg(metric) == "sum" else g.mean(axis=1)
    s.index = pd.DatetimeIndex(s.index, freq="h") if s.index.inferred_freq == "h" else s.index
    return s


@cached
def metric_series(fid: str, module: str, metric: str, days: int = 14, gran: str = "h") -> dict:
    df = D.load(fid, module, metric, days)
    if df.empty:
        return {"module": module, "metric": metric, "unit": UNITS.get(metric, ""), "ts": [], "series": {}, "total": []}
    agg = _agg(metric)
    z = df.groupby(["ts", "zone"])["value"].agg(agg).unstack()
    if gran == "d":
        z = z.groupby(z.index.normalize()).agg(agg)
    total = z.sum(axis=1) if agg == "sum" else z.mean(axis=1)
    return {"module": module, "metric": metric, "unit": UNITS.get(metric, ""), "agg": agg, "ts": [t.isoformat() for t in z.index],
            "series": {c: [None if pd.isna(v) else round(float(v), 3) for v in z[c]] for c in z.columns},
            "total": [round(float(v), 3) for v in total]}


@cached
def forecast_view(fid: str, module: str, metric: str, horizon: int = 24) -> dict:
    s = site_series(fid, module, metric, 90)
    out = forecasting.forecast(s, horizon=horizon, unit=UNITS.get(metric, ""))
    out.update({"module": module, "metric": metric, "unit": UNITS.get(metric, "")})
    return out


# ------------------------------------------------------------------------------------------------
# Anomalies
# ------------------------------------------------------------------------------------------------
ANOM_SPECS = [("energy", "kwh", "profile"), ("water", "flow_kl", "profile"), ("air", "pm25", "local"),
              ("air", "pm10", "local")]  # slow equipment drift is handled by the maintenance risk model, not this detector


def _explain(module: str, metric: str, ev: dict, zone_name: str) -> str:
    ratio = ev["peak"] / ev["typical"] if ev["typical"] else float("nan")
    if ev["reason"] == "flatline":
        return (f"{ev['entity']} reported an identical value for {ev['hours']} h. The sensor may be stuck or offline; "
                "check the device before relying on data from this zone.")
    if module == "water":
        night = ev["night_share"] >= 0.5
        extra = " Continuous excess flow overnight is the typical signature of a leak." if night else ""
        return f"Water use in {zone_name} ran about {ratio:.1f}x its normal level for those hours (peak {ev['peak']:.2f} kL/h vs typical {ev['typical']:.2f}).{extra}"
    if module == "energy":
        return (f"{zone_name} drew up to {ev['peak']:.0f} kWh in an hour, {ratio:.1f}x its typical {ev['typical']:.0f} kWh for that hour "
                "after adjusting for temperature. Possible causes: equipment left running, a fault, or an unscheduled load.")
    if module == "air":
        return (f"{metric.upper()} in {zone_name} reached {ev['peak']:.0f} µg/m³, {ratio:.1f}x its recent level. This looks like a localized pollution "
                "episode (for example diesel exhaust, burning or dust). Indicative only, not an official measurement.")
    return f"{ev['entity']} {metric.replace('_', ' ')} reached {ev['peak']:.2f}, {ratio:.1f}x its recent level, which may indicate wear or an equipment fault."


@cached
def anomalies_view(fid: str, days: int = 14) -> dict:
    cfg = cfg_of(fid)
    zones = D.zone_map(cfg)
    now = D.last_ts(fid)
    temp = D.load(fid, "weather", "temp_c").set_index("ts")["value"]
    events, evaluation = [], {}
    for module, metric, baseline in ANOM_SPECS:
        df = D.load(fid, module, metric)
        if module == "assets":
            df = df[df["entity"].isin([a["id"] for a in cfg["assets"] if a["type"] != "dg"])]
        scored = anomaly.detect(df, temp if module == "energy" else None, baseline)
        evaluation[f"{module}:{metric}"] = anomaly.evaluate(scored)
        recent = scored[scored["flag"] & (scored["ts"] > now - pd.Timedelta(days=days))]
        for (ent, _), g in recent.groupby(["entity", "metric"]):
            g = g.sort_values("ts")
            gid = (g["ts"].diff() > pd.Timedelta(hours=3)).cumsum()
            for _, e in g.groupby(gid):
                peak_row = e.loc[e["z"].abs().idxmax()]
                zone = e["zone"].iloc[0]
                ev = {"entity": ent, "reason": "flatline" if e["flat"].any() and not (e["z"].abs() > 5).any() else peak_row["reason"],
                      "hours": int(len(e)), "peak": float(peak_row["value"]), "typical": float(peak_row["typical"]),
                      "night_share": float(e["ts"].dt.hour.between(0, 5).mean())}
                events.append({"module": module, "metric": metric, "entity": ent, "zone": zone, "zone_name": zones.get(zone, {}).get("name", zone),
                               "start": e["ts"].min().isoformat(), "end": e["ts"].max().isoformat(), "hours": ev["hours"],
                               "active": bool(e["ts"].max() >= now - pd.Timedelta(hours=3)), "peak_value": round(ev["peak"], 3),
                               "typical_value": round(ev["typical"], 3), "score": round(float(e["z"].abs().max()), 1), "kind": ev["reason"],
                               "explanation": _explain(module, metric, ev, zones.get(zone, {}).get("name", zone))})
    events.sort(key=lambda e: (not e["active"], -e["score"]))
    return {"events": events, "evaluation": evaluation,
            "method": "Robust deviation from each sensor's typical level (same hour, weekday/weekend; temperature-adjusted for energy) + IsolationForest + flatline rule. Precision/recall are event-level against injected synthetic faults."}


# ------------------------------------------------------------------------------------------------
# Energy
# ------------------------------------------------------------------------------------------------
def _grid_cost(total: pd.Series, solar: pd.Series, dg: pd.Series, tariff: dict) -> pd.DataFrame:
    df = pd.DataFrame({"total": total, "solar": solar.reindex(total.index).fillna(0), "dg": dg.reindex(total.index).fillna(0)})
    df["grid"] = (df["total"] - df["solar"] - df["dg"]).clip(lower=0)
    h = df.index.hour
    df["peak"] = (h >= tariff["peak_start"]) & (h < tariff["peak_end"])
    df["price"] = np.where(df["peak"], tariff["peak"], tariff["offpeak"])
    df["cost"] = df["grid"] * df["price"]
    return df


def _energy_frame(fid: str, days: int) -> pd.DataFrame:
    cfg = cfg_of(fid)
    return _grid_cost(site_series(fid, "energy", "kwh", days), site_series(fid, "energy", "solar_kwh", days),
                      site_series(fid, "energy", "dg_kwh", days), cfg["tariff"])


@cached
def energy_view(fid: str, days: int = 30) -> dict:
    cfg = cfg_of(fid)
    f = _energy_frame(fid, days)
    daily = f.groupby(f.index.normalize()).agg(total=("total", "sum"), grid=("grid", "sum"), solar=("solar", "sum"), dg=("dg", "sum"), cost=("cost", "sum"))
    peak_share = float(f.loc[f["peak"], "grid"].sum() / max(f["grid"].sum(), 1e-9))
    hourly = f.groupby(f.index.hour)["total"].mean()
    full = site_series(fid, "energy", "kwh", 90)
    base = full.iloc[: -24 * 7]
    key = base.groupby([base.index.hour, base.index.dayofweek >= 5]).median()
    last7 = full.iloc[-24 * 7:]
    expected = float(sum(key.get((t.hour, t.dayofweek >= 5), np.nan) for t in last7.index))
    shiftable = 0.12 * float(f.loc[f["peak"], "total"].sum()) / days
    saving = shiftable * (cfg["tariff"]["peak"] - cfg["tariff"]["offpeak"]) * 30
    zone_kwh = D.load(fid, "energy", "kwh", days).groupby("zone")["value"].sum().sort_values(ascending=False)
    return {"days": days, "daily": {"ts": [t.date().isoformat() for t in daily.index], **{k: [round(float(v), 1) for v in daily[k]] for k in daily.columns}},
            "hourly_profile": [round(float(hourly.get(h, 0)), 1) for h in range(24)],
            "peak_demand_kw": round(float(f["total"].max()), 1), "avg_kw": round(float(f["total"].mean()), 1),
            "solar_share_pct": round(float(f["solar"].sum() / f["total"].sum() * 100), 1), "dg_share_pct": round(float(f["dg"].sum() / f["total"].sum() * 100), 2),
            "dg_hours": int((f["dg"] > 0).sum()), "peak_window_share_pct": round(peak_share * 100, 1),
            "total_kwh": round(float(f["total"].sum()), 0), "cost_inr": round(float(f["cost"].sum()), 0),
            "intensity_kwh_per_sqm_month": round(float(f["total"].sum() / cfg["area_sqm"] * 30 / days), 2),
            "last7_vs_baseline_pct": round((float(last7.sum()) / expected - 1) * 100, 1) if expected else None,
            "zones": [{"zone": z, "name": D.zone_map(cfg)[z]["name"], "kwh": round(float(v), 0)} for z, v in zone_kwh.items() if z in D.zone_map(cfg)],
            "shift": {"shiftable_kwh_per_day": round(shiftable, 1), "saving_inr_per_month": round(saving, 0),
                      "assumption": "12% of peak-window demand (HVAC pre-cooling, pumps, charging) can move to off-peak."}}


# ------------------------------------------------------------------------------------------------
# Air, water, waste, traffic
# ------------------------------------------------------------------------------------------------
@cached
def air_view(fid: str) -> dict:
    cfg = cfg_of(fid)
    zm = D.zone_map(cfg)
    df = D.load(fid, "air", "pm25", 3)
    last24 = df[df["ts"] > df["ts"].max() - pd.Timedelta(hours=24)].groupby("zone")["value"].mean()
    now = df.groupby("zone")["value"].last()
    zones = []
    for z, zc in zm.items():
        v24 = float(last24.get(z, 0))
        zones.append({"zone": z, "name": zc["name"], "lat": zc["lat"], "lon": zc["lon"], "pm25_now": round(float(now.get(z, 0)), 1),
                      "pm25_24h": round(v24, 1), "category": aqi_category(v24)})
    grid = risk_ml.idw_grid([(z["lat"], z["lon"], z["pm25_24h"]) for z in zones])
    worst = max(zones, key=lambda z: z["pm25_24h"])
    mean24 = float(np.mean([z["pm25_24h"] for z in zones]))
    cat = aqi_category(mean24)
    adv = {"Good": "Normal outdoor activity is fine.", "Satisfactory": "Sensitive people may notice mild discomfort; no action needed for most.",
           "Moderate": "People with breathing or heart conditions may want to limit prolonged outdoor exertion.",
           "Poor": "Consider moving outdoor sports indoors and advising sensitive groups to limit time outside.",
           "Very poor": "Advise sensitive groups to stay indoors; consider pausing outdoor activities.", "Severe": "Pause outdoor activities and follow local health guidance."}[cat["label"]]
    return {"zones": zones, "campus_pm25_24h": round(mean24, 1), "category": cat, "hotspot": worst, "heat_grid": grid,
            "advisory": adv + " Indicative guidance from synthetic sensor data, not an official AQI or medical advice.",
            "pm25_alert": cfg["thresholds"]["pm25_alert"]}


@cached
def water_view(fid: str) -> dict:
    cfg = cfg_of(fid)
    zm = D.zone_map(cfg)
    pop = sum(cfg["population"].values())
    df = D.load(fid, "water", "flow_kl", 30)
    daily_total = df.groupby(df["ts"].dt.normalize())["value"].sum()
    lpcd = float(daily_total.iloc[:-1].mean() * 1000 / pop) if len(daily_total) > 1 else 0.0
    zones = []
    for z, g in df.groupby("zone"):
        g = g.groupby("ts")["value"].sum()
        night = g[g.index.hour.isin([1, 2, 3, 4])]
        ratio_recent = float(night.iloc[-72:].mean() / max(g.iloc[-72:].mean(), 1e-9))
        ratio_prev = float(night.iloc[:-72].mean() / max(g.iloc[:-72].mean(), 1e-9))
        night_recent, night_prev = float(night.iloc[-12:].mean()), float(night.iloc[:-12].mean())
        night_excess = night_recent - night_prev  # kL/h still flowing in the small hours compared with the zone's normal
        avg_h = float(g.mean())
        zones.append({"zone": z, "name": zm[z]["name"], "kl_per_day": round(avg_h * 24, 1), "night_ratio_recent": round(ratio_recent, 2),
                      "night_ratio_prev": round(ratio_prev, 2), "night_change_pct": round((night_recent / max(night_prev, 1e-9) - 1) * 100, 1),
                      "leak_suspect": bool(night_recent > 1.15 * night_prev and night_excess > 0.1 * avg_h),
                      "excess_kl_per_day": round(max(night_excess, 0) * 24, 1)})
    tank = site_series(fid, "water", "tank_level_pct", 30)
    tf = forecasting.forecast(tank, 24, unit="%")
    roof = sum(z["area_sqm"] for z in cfg["zones"]) * GRID_ASSUMPTIONS["roof_share_of_area"]
    rwh = roof * GRID_ASSUMPTIONS["annual_rain_mm"] * GRID_ASSUMPTIONS["runoff_coeff"] / 1000
    return {"lpcd": round(lpcd, 1), "benchmark_lpcd": cfg["thresholds"]["water_lpcd"], "kl_per_day": round(float(daily_total.iloc[:-1].mean()), 1) if len(daily_total) > 1 else 0,
            "budget_kl_per_day": round(cfg["thresholds"]["water_lpcd"] * pop / 1000, 1), "zones": sorted(zones, key=lambda z: -z["excess_kl_per_day"]),
            "tank_forecast": {"ts": tf["ts"], "yhat": tf["yhat"], "lo": tf["lo"], "hi": tf["hi"]},
            "rainwater_harvest_kl_per_year": round(rwh), "rwh_assumption": f"Roof ≈ {GRID_ASSUMPTIONS['roof_share_of_area']*100:.0f}% of built area, {GRID_ASSUMPTIONS['annual_rain_mm']} mm/yr rainfall, {GRID_ASSUMPTIONS['runoff_coeff']} runoff coefficient (editable)."}


@cached
def waste_view(fid: str) -> dict:
    cfg = cfg_of(fid)
    meta = D.bins_meta(cfg)
    df = D.load(fid, "waste", "fill_pct")
    st = waste_ml.train_and_score(df[["ts", "entity", "value"]])
    thr = cfg["thresholds"]["bin_alert_pct"]
    bins = []
    for _, r in st.iterrows():
        m = meta[r["entity"]]
        bins.append({**m, "fill_pct": round(float(r["value"]), 1), "hours_to_90": round(float(r["hours_to_90"]), 1),
                     "p_overflow_6h": round(float(r["p_overflow_6h"]), 2), "alert": bool(r["value"] >= thr or r["p_overflow_6h"] >= 0.5)})
    depot = (cfg["lat"] - 0.0008, cfg["lon"] + 0.0009)
    current = [b for b in bins]
    targets = [b for b in bins if b["alert"]]
    opt = waste_ml.optimise_route(depot, targets)
    cur_km, opt_km = waste_ml.route_length(depot, current), waste_ml.route_length(depot, opt)
    over_hours = int((df["value"] >= 90).sum())
    seg = {t: round(float(np.mean([b["fill_pct"] for b in bins if b["type"] == t])), 1) for t in sorted({b["type"] for b in bins})}
    return {"bins": bins, "threshold": thr, "depot": {"lat": depot[0], "lon": depot[1]},
            "route": {"current_order": [b["id"] for b in current], "current_km": round(cur_km, 2), "optimized_order": [b["id"] for b in opt],
                      "optimized_km": round(opt_km, 2), "saved_km": round(max(cur_km - opt_km, 0), 2),
                      "optimized_points": [{"id": b["id"], "lat": b["lat"], "lon": b["lon"]} for b in opt],
                      "note": "Current = visit every bin in fixed round order; optimized = only bins at/over the alert level or likely to overflow within 6 h, nearest-neighbour + 2-opt."},
            "overflow_bin_hours_90d": over_hours, "avg_fill_by_type": seg,
            "model_note": "Overflow probability: gradient boosting on fill level, 6 h fill rate, hours since collection and hour of day."}


@cached
def traffic_view(fid: str) -> dict:
    cfg = cfg_of(fid)
    veh = site_series(fid, "traffic", "vehicles_in", 28)
    wk = veh[veh.index.dayofweek < 5]
    prof = wk.groupby(wk.index.hour).mean()
    park = D.load(fid, "traffic", "occupancy_pct", 14)
    zm = D.zone_map(cfg)
    parking = []
    for z, g in park.groupby("zone"):
        s = g.groupby("ts")["value"].mean()
        full_hours = s[s >= 90]
        busiest = full_hours.groupby(full_hours.index.hour).size().sort_values(ascending=False)
        parking.append({"zone": z, "name": zm[z]["name"], "capacity": zm[z].get("parking_capacity"), "now_pct": round(float(s.iloc[-1]), 1),
                        "hours_over_90_14d": int(len(full_hours)), "peak_hour": int(busiest.index[0]) if len(busiest) else int(s.groupby(s.index.hour).mean().idxmax()),
                        "profile": [round(float(s.groupby(s.index.hour).mean().get(h, 0)), 1) for h in range(24)]})
    q = site_series(fid, "traffic", "queue_min", 28)
    qp = q[q.index.dayofweek < 5].groupby(q[q.index.dayofweek < 5].index.hour).mean()
    return {"gate_profile": [round(float(prof.get(h, 0)), 1) for h in range(24)], "peak_hour": int(prof.idxmax()), "peak_vehicles": round(float(prof.max()), 0),
            "queue_profile_min": [round(float(qp.get(h, 0)), 1) for h in range(24)], "parking": parking}


@cached
def assets_view(fid: str) -> dict:
    cfg = cfg_of(fid)
    am = {a["id"]: a for a in cfg["assets"]}
    df = D.load(fid, "assets")
    wide = df.pivot_table(index=["ts", "entity"], columns="metric", values="value").reset_index()
    lab = df[df["metric"] == "vibration_mm_s"][["ts", "entity", "label"]]
    wide = wide.merge(lab, on=["ts", "entity"], how="left")
    sc = maintenance.score(wide)
    util7 = wide[wide["ts"] > wide["ts"].max() - pd.Timedelta(days=7)].groupby("entity")["util_pct"].mean()
    out = []
    for _, r in sc.iterrows():
        a = am[r["entity"]]
        band = "Critical" if r["risk"] >= 0.6 else "High" if r["risk"] >= 0.35 else "Medium" if r["risk"] >= 0.2 else "Normal"
        reasons = []
        if r["vib_excess"] > 0.8: reasons.append(f"vibration +{r['vib_excess']:.1f} mm/s above its own baseline")
        if r["temp_excess"] > 4: reasons.append(f"running {r['temp_excess']:.0f} °C hotter than baseline")
        if r["days_since_service"] > 150: reasons.append(f"{int(r['days_since_service'])} days since last service")
        u = float(util7.get(r["entity"], 0))
        out.append({"id": r["entity"], "name": a["name"], "type": a["type"], "zone": a["zone"], "util_7d_pct": round(u, 1),
                    "idle": bool(u < 15 and a["type"] != "dg"), "risk": round(float(r["risk"]), 2), "risk_band": band, "reasons": reasons,
                    "vibration_now": round(float(r["vibration_mm_s"]), 2), "days_since_service": int(r["days_since_service"]), "rated_kw": a["rated_kw"]})
    return {"assets": out, "feature_importance": sc.attrs.get("importance", {}),
            "model_note": "Risk = 0.6 × RandomForest probability (trained on synthetic degradation labels) + 0.4 × transparent rule score (vibration, temperature, service age)."}


@cached
def safety_view(fid: str) -> dict:
    cfg = cfg_of(fid)
    inc = D.incidents(fid)
    now = D.last_ts(fid)
    zm = D.zone_map(cfg)
    wk = inc.groupby(inc["ts"].dt.to_period("W").dt.start_time).size()
    zr = risk_ml.zone_risk(inc, now, list(zm))
    return {"weekly": {"ts": [t.date().isoformat() for t in wk.index], "count": [int(v) for v in wk.values]},
            "severity": {str(k): int(v) for k, v in inc["severity"].value_counts().sort_index().items()},
            "kinds": {k: int(v) for k, v in inc["kind"].value_counts().items()},
            "zone_risk": [{**r, "name": zm[r["zone"]]["name"]} for r in zr.to_dict("records")],
            "open": int((inc["status"] == "open").sum()),
            "open_list": [{"id": int(r.id), "ts": r.ts.isoformat(), "zone": zm[r.zone]["name"], "kind": r.kind, "severity": int(r.severity)}
                          for r in inc[inc["status"] == "open"].sort_values(["severity", "ts"], ascending=[False, False]).head(10).itertuples()],
            "method": "Zone risk = severity weight (1, 2.5, 6, 12) × recency decay (21-day half-life style) summed over incidents; index is relative to the highest zone."}


@cached
def emissions_view(fid: str, days: int = 30) -> dict:
    cfg = cfg_of(fid)
    f = _energy_frame(fid, days)
    e = cfg["emission"]
    s2 = float(f["grid"].sum() * e["grid_kg_per_kwh"]); s1 = float(f["dg"].sum() * e["dg_kg_per_kwh"])
    veh = float(site_series(fid, "traffic", "vehicles_in", days).sum())
    s3 = veh * 2 * GRID_ASSUMPTIONS["trip_km"] * GRID_ASSUMPTIONS["kg_co2_per_km"]
    avoided = float(f["solar"].sum() * e["grid_kg_per_kwh"])
    temp = D.load(fid, "weather", "temp_c", days).set_index("ts")["value"]
    rain = D.load(fid, "weather", "rainfall_mm", days).set_index("ts")["value"]
    heat_days = int((temp.groupby(temp.index.normalize()).max() >= 35).sum())
    rain24 = float(rain.rolling(24).sum().max())
    zones = []
    for z in cfg["zones"]:
        heat = "High" if heat_days >= 3 and z["type"] in ("hostel", "clinical", "industrial") else "Medium" if heat_days >= 1 else "Low"
        wl = "High" if rain24 >= 60 and z["type"] in ("parking", "utility") else "Medium" if rain24 >= 30 else "Low"
        zones.append({"zone": z["id"], "name": z["name"], "heat_stress": heat, "waterlogging": wl})
    checklist = [{"item": "Heat action plan and drinking-water points ready", "flag": heat_days >= 1},
                 {"item": "Drain and sump cleaning completed before monsoon", "flag": rain24 >= 30},
                 {"item": "DG fuel stock and changeover test done", "flag": int((f["dg"] > 0).sum()) > 0},
                 {"item": "Solar panel cleaning scheduled", "flag": True}]
    return {"days": days, "scope1_kg": round(s1), "scope2_kg": round(s2), "scope3_indicative_kg": round(s3), "total_kg": round(s1 + s2 + s3),
            "solar_avoided_kg": round(avoided), "intensity_kg_per_sqm": round((s1 + s2) / cfg["area_sqm"], 2),
            "heat_days": heat_days, "max_rain_24h_mm": round(rain24, 1), "zones": zones, "checklist": checklist,
            "factors": e, "note": "Scope 3 is a rough commute estimate (vehicle trips × assumed distance × assumed emission factor). Indicative only."}


# ------------------------------------------------------------------------------------------------
# Overview and scorecard
# ------------------------------------------------------------------------------------------------
@cached
def overview(fid: str) -> dict:
    cfg = cfg_of(fid)
    f = _energy_frame(fid, 2)
    last24, prev24 = f.iloc[-24:], f.iloc[-48:-24]
    air = air_view(fid)
    water = site_series(fid, "water", "flow_kl", 2)
    budget = cfg["thresholds"]["water_lpcd"] * sum(cfg["population"].values()) / 1000
    wv = waste_view(fid)
    sv = safety_view(fid)
    e = cfg["emission"]
    co2 = float(last24["grid"].sum() * e["grid_kg_per_kwh"] + last24["dg"].sum() * e["dg_kg_per_kwh"])
    an = anomalies_view(fid)
    zones = []
    wz: dict[str, float] = {}
    for b in wv["bins"]:
        wz[b["zone"]] = max(wz.get(b["zone"], 0), b["fill_pct"])
    az = {z["zone"]: z for z in air["zones"]}
    ez = D.load(fid, "energy", "kwh", 1).groupby("zone")["value"].sum()
    active = {a["zone"] for a in an["events"] if a["active"]}
    for z in cfg["zones"]:
        status = "alert" if (az[z["id"]]["pm25_24h"] > cfg["thresholds"]["pm25_alert"] or wz.get(z["id"], 0) >= 95 or z["id"] in active) else \
            "watch" if (az[z["id"]]["pm25_24h"] > 0.8 * cfg["thresholds"]["pm25_alert"] or wz.get(z["id"], 0) >= cfg["thresholds"]["bin_alert_pct"]) else "ok"
        zones.append({"zone": z["id"], "name": z["name"], "lat": z["lat"], "lon": z["lon"], "type": z["type"], "status": status,
                      "pm25_24h": az[z["id"]]["pm25_24h"], "kwh_24h": round(float(ez.get(z["id"], 0))), "max_bin_fill": round(wz.get(z["id"], 0))})
    return {"as_of": D.last_ts(fid).isoformat(), "facility": {"id": fid, "name": cfg["name"], "city": cfg["city"], "state": cfg["state"], "lat": cfg["lat"], "lon": cfg["lon"]},
            "kpis": {"aqi": {"pm25_24h": air["campus_pm25_24h"], **air["category"]},
                     "energy_kwh_24h": round(float(last24["total"].sum())), "energy_change_pct": round((float(last24["total"].sum()) / max(float(prev24["total"].sum()), 1) - 1) * 100, 1),
                     "cost_inr_24h": round(float(last24["cost"].sum())), "water_kl_24h": round(float(water.iloc[-24:].sum()), 1), "water_budget_kl": round(budget, 1),
                     "bins_over_threshold": int(sum(b["fill_pct"] >= wv["threshold"] for b in wv["bins"])), "bins_total": len(wv["bins"]),
                     "open_incidents": sv["open"], "co2_kg_24h": round(co2), "active_alerts": int(sum(a["active"] for a in an["events"]))},
            "zones": zones}


def _score_lin(ratio: float) -> float:
    return float(np.clip(100 - max(0.0, ratio - 0.9) * 166, 0, 100))


def _window_scores(fid: str, cfg: dict, start: pd.Timestamp, end: pd.Timestamp) -> dict:
    t = cfg["thresholds"]
    en = _grid_cost(site_series(fid, "energy", "kwh"), site_series(fid, "energy", "solar_kwh"), site_series(fid, "energy", "dg_kwh"), cfg["tariff"])
    en = en[(en.index > start) & (en.index <= end)]
    days = max(len(en) / 24, 1)
    intensity = float(en["total"].sum() / cfg["area_sqm"] * 30 / days)
    co2 = float(en["grid"].sum() * cfg["emission"]["grid_kg_per_kwh"] + en["dg"].sum() * cfg["emission"]["dg_kg_per_kwh"]) / cfg["area_sqm"] * 30 / days
    pop = sum(cfg["population"].values())
    w = site_series(fid, "water", "flow_kl")
    w = w[(w.index > start) & (w.index <= end)]
    lpcd = float(w.sum() / days * 1000 / pop)
    wf = D.load(fid, "waste", "fill_pct"); wf = wf[(wf["ts"] > start) & (wf["ts"] <= end)]
    waste_s = float((wf["value"] < t["bin_alert_pct"]).mean() * 100)
    pm = site_series(fid, "air", "pm25"); pm = pm[(pm.index > start) & (pm.index <= end)]
    air_s = float((pm <= t["pm25_alert"]).mean() * 100)
    inc = D.incidents(fid); inc = inc[(inc["ts"] > start) & (inc["ts"] <= end)]
    weighted = float(sum(risk_ml.SEV_W[int(s)] for s in inc["severity"]))
    subs = {"energy": _score_lin(intensity / t["energy_kwh_per_sqm_month"]), "water": _score_lin(lpcd / t["water_lpcd"]),
            "waste": waste_s, "air": air_s,
            "emissions": _score_lin(co2 / (t["energy_kwh_per_sqm_month"] * cfg["emission"]["grid_kg_per_kwh"])),
            "safety": float(np.clip(100 - weighted * 0.8, 0, 100))}
    overall = sum(cfg["score_weights"][k] * v for k, v in subs.items())
    grade = "A" if overall >= 85 else "B" if overall >= 70 else "C" if overall >= 55 else "D" if overall >= 40 else "E"
    return {"overall": round(overall, 1), "grade": grade, "sub": {k: round(v, 1) for k, v in subs.items()},
            "raw": {"energy_kwh_per_sqm_month": round(intensity, 2), "water_lpcd": round(lpcd, 1), "bin_service_level_pct": round(waste_s, 1),
                    "air_hours_within_limit_pct": round(air_s, 1), "co2_kg_per_sqm_month": round(co2, 2), "weighted_incident_load": round(weighted, 1)}}


@cached
def scorecard(fid: str) -> dict:
    cfg = cfg_of(fid)
    now = D.last_ts(fid)
    labels = ["Last 30 days", "Previous 30 days", "60-90 days ago"]
    wins = []
    for i, lab in enumerate(labels):
        end = now - pd.Timedelta(days=30 * i); start = end - pd.Timedelta(days=30)
        wins.append({"label": lab, **_window_scores(fid, cfg, start, end)})
    return {"current": wins[0], "history": wins, "weights": cfg["score_weights"], "targets": cfg["thresholds"],
            "method": "Each sub-score is 0-100 vs the facility's configured target (energy/water/emissions: 100 until 10% above target, then falling linearly; waste/air: share of hours within limit; safety: 100 minus weighted incident load). Overall = weighted average."}


# ------------------------------------------------------------------------------------------------
# Scenario simulation
# ------------------------------------------------------------------------------------------------
def simulate(fid: str, p: dict) -> dict:
    """Closed-form what-if on a 30-day baseline. Every lever and constant is listed in `assumptions`."""
    cfg = cfg_of(fid)
    ev, wv, wsv = energy_view(fid, 30), water_view(fid), waste_view(fid)
    A = GRID_ASSUMPTIONS
    kwh = ev["total_kwh"] / 30
    grid_kwh = sum(ev["daily"]["grid"]) / 30
    price = (ev["cost_inr"] / 30) / max(grid_kwh, 1e-9)
    cost = ev["cost_inr"] / 30
    ef = cfg["emission"]["grid_kg_per_kwh"]
    co2 = grid_kwh * ef + sum(ev["daily"]["dg"]) / 30 * cfg["emission"]["dg_kg_per_kwh"]
    water = wv["kl_per_day"]
    over_h = wsv["overflow_bin_hours_90d"] / 90 * 7
    b = {"kwh_day": kwh, "grid_kwh_day": grid_kwh, "cost_inr_day": cost, "co2_kg_day": co2, "water_kl_day": water, "overflow_bin_hours_week": over_h}
    a = dict(b)
    notes = []
    solar = float(p.get("add_solar_kw", 0))
    if solar:
        gen = min(solar * A["solar_kwh_per_kw_day"], a["grid_kwh_day"])
        a["grid_kwh_day"] -= gen; a["cost_inr_day"] -= gen * price; a["co2_kg_day"] -= gen * ef
        notes.append(f"Solar: {solar:.0f} kW × {A['solar_kwh_per_kw_day']} kWh/kW/day, offsetting grid power only.")
    dt = float(p.get("ac_setpoint_delta_c", 0))
    if dt:
        hv = sum(e["kwh"] for e in ev["zones"] if D.zone_map(cfg)[e["zone"]]["type"] in HVAC_TYPES) / max(sum(e["kwh"] for e in ev["zones"]), 1)
        sv = a["kwh_day"] * hv * A["cooling_share_hvac_zones"] * min(A["saving_per_degC"] * dt, 0.3)
        a["kwh_day"] -= sv; a["grid_kwh_day"] -= sv; a["cost_inr_day"] -= sv * price; a["co2_kg_day"] -= sv * ef
        notes.append(f"AC setpoint +{dt:g} °C: {hv*100:.0f}% of load is in HVAC zones, {A['cooling_share_hvac_zones']*100:.0f}% of that is cooling, ~{A['saving_per_degC']*100:.0f}% saving per °C.")
    shift = float(p.get("shift_peak_pct", 0))
    if shift:
        pk = ev["peak_window_share_pct"] / 100 * grid_kwh
        sv_inr = pk * shift / 100 * (cfg["tariff"]["peak"] - cfg["tariff"]["offpeak"])
        a["cost_inr_day"] -= sv_inr
        notes.append(f"Load shift: {shift:g}% of peak-window grid energy moves off-peak; kWh unchanged, saves the tariff difference (₹{cfg['tariff']['peak'] - cfg['tariff']['offpeak']:.1f}/kWh).")
    occ = float(p.get("occupancy_change_pct", 0))
    if occ:
        dk = a["kwh_day"] * 0.6 * occ / 100
        a["kwh_day"] += dk; a["grid_kwh_day"] += dk; a["cost_inr_day"] += dk * price; a["co2_kg_day"] += dk * ef
        a["water_kl_day"] *= 1 + 0.8 * occ / 100
        notes.append("Occupancy: energy elasticity 0.6, water elasticity 0.8.")
    if p.get("fix_leak"):
        saved = sum(z["excess_kl_per_day"] for z in wv["zones"] if z["leak_suspect"])
        a["water_kl_day"] -= saved; a["cost_inr_day"] -= saved * A["water_cost_inr_per_kl"] * 0
        notes.append(f"Leak fix: recovers the {saved:.1f} kL/day excess flow detected in suspect zones; water valued at ₹{A['water_cost_inr_per_kl']:.0f}/kL.")
    extra = float(p.get("extra_collections_per_week", 0))
    if extra:
        a["overflow_bin_hours_week"] *= 1 - min(0.8, 0.22 * extra)
        notes.append("Collections: each extra weekly trip assumed to cut overflow bin-hours by ~22% (cap 80%).")
    water_value = (b["water_kl_day"] - a["water_kl_day"]) * A["water_cost_inr_per_kl"]
    delta = {k: round(a[k] - b[k], 2) for k in b}
    return {"baseline": {k: round(v, 1) for k, v in b.items()}, "scenario": {k: round(v, 1) for k, v in a.items()}, "delta": delta,
            "monthly": {"cost_saving_inr": round(-delta["cost_inr_day"] * 30 + water_value * 30), "kwh_saving": round(-delta["kwh_day"] * 30 - 0),
                        "co2_saving_kg": round(-delta["co2_kg_day"] * 30), "water_saving_kl": round(-delta["water_kl_day"] * 30)},
            "assumptions": notes + ["Baseline = last 30 days of (synthetic) data. Results are estimates for planning, not guarantees."]}
