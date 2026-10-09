"""Synthetic IoT simulator with Indian-context patterns.

Produces hourly long-format readings for every module (air, energy, water, waste, traffic, assets, weather)
plus safety incidents. Realistic seasonality (summer heat, monsoon, post-monsoon AQI), weekday/weekend and
holiday cycles, DG usage during power cuts, solar generation, and *labelled injected anomalies* so that the
detection models can be evaluated objectively. All data is SYNTHETIC; see docs/ASSUMPTIONS.md.
"""
from __future__ import annotations
from datetime import datetime
import numpy as np
import pandas as pd

MONTH_PM25 = {1: 90, 2: 70, 3: 55, 4: 55, 5: 55, 6: 38, 7: 25, 8: 22, 9: 25, 10: 48, 11: 90, 12: 105}
RAIN_PROB = {6: .55, 7: .7, 8: .7, 9: .6, 10: .25}
PM_ZONE_FACTOR = {"parking": 1.35, "industrial": 1.5, "utility": 1.25, "canteen": 1.2}
HVAC_SENSITIVE = {"academic", "office", "clinical", "canteen"}
INCIDENT_KINDS = ["slip_fall", "electrical", "fire_alarm", "equipment_fault", "vehicle_collision", "chemical_spill", "medical"]
FAULT_TYPES = {"sensor_fault", "energy_spike", "leak", "pollution_episode", "bin_overflow", "degradation"}


def _gauss(h, mu, sigma):
    return np.exp(-((h - mu) ** 2) / (2 * sigma ** 2))


def occupancy(ztype: str, h: np.ndarray, dow: np.ndarray, hol: np.ndarray, sched: dict) -> np.ndarray:
    """Zone activity factor in [0.05, 1.2] for each hour, given the facility schedule."""
    ws, we, wf = sched["work_start"], sched["work_end"], sched["weekend_factor"]
    day_f = np.where(hol | (dow >= 5), wf, 1.0)
    mid, half = (ws + we) / 2, (we - ws) / 2 + 1
    bell = np.clip(1 - ((h - mid) / half) ** 2, 0, 1)
    always = sched.get("always_on", False)
    if ztype in ("academic", "office"):
        occ = (0.4 + 0.6 * bell) * (0.6 + 0.4 * day_f) if always else 0.15 + 0.85 * bell * day_f
    elif ztype == "hostel":
        occ = 0.55 + 0.45 * np.cos(2 * np.pi * (h - 22) / 24) + np.where(dow >= 5, 0.1, 0)
    elif ztype == "canteen":
        occ = 0.08 + (_gauss(h, 8.5, 1) + _gauss(h, 13.5, 1.2) + _gauss(h, 20, 1.3)) * (0.5 + 0.5 * day_f)
    elif ztype == "clinical":
        occ = 0.72 + 0.28 * bell * (0.8 + 0.2 * day_f)
    elif ztype == "industrial":
        dip = np.isin(h, [ws - 1, 13, 14, we - 1]) * 0.12
        occ = (0.78 + 0.17 * bell - dip) * (0.7 + 0.3 * day_f)
    elif ztype == "parking":
        occ = 0.1 + 0.85 * np.clip(1 - ((h - (mid + 0.5)) / (half + 1)) ** 2, 0, 1) * day_f
    else:  # utility
        occ = 0.75 + 0.1 * bell
    return np.clip(occ, 0.05, 1.2)


def generate(cfg: dict, end: datetime, days: int = 90, seed: int = 7) -> tuple[pd.DataFrame, pd.DataFrame]:
    rng = np.random.default_rng(seed + sum(map(ord, cfg["id"])))
    end = pd.Timestamp(end).floor("h")
    ts = pd.date_range(end=end, periods=days * 24, freq="h")
    n = len(ts)
    h, dow, doy, month = ts.hour.values, ts.dayofweek.values, ts.dayofyear.values, ts.month.values
    sched = cfg["schedule"]
    hol = np.isin(ts.strftime("%Y-%m-%d"), sched.get("holidays", []))
    codes, uniques = pd.factorize(ts.normalize())
    month_day = pd.Series(month).groupby(codes).first().values
    parts: list[pd.DataFrame] = []
    label_none = lambda: np.full(n, "", dtype=object)

    def emit(module, zone, entity, metric, values, labels=None):
        parts.append(pd.DataFrame({"ts": ts, "module": module, "zone": zone, "entity": entity, "metric": metric,
                                   "value": np.round(np.asarray(values, float), 3),
                                   "label": labels if labels is not None else label_none()}))

    def flatline(vals, labels, length=5):
        s = int(rng.integers(48, n - length - 1))
        vals[s:s + length] = vals[s - 1]
        labels[s:s + length] = "sensor_fault"

    # ---- weather -------------------------------------------------------------------------------
    wet_day = rng.random(len(uniques)) < np.vectorize(lambda m: RAIN_PROB.get(int(m), 0.03))(month_day)
    wet = wet_day[codes]
    heat_event = ((ts >= end - pd.Timedelta(days=6)) & (ts < end - pd.Timedelta(days=3))).astype(float)
    temp = (29 + 6 * np.sin(2 * np.pi * (doy - 46) / 365) + 5 * np.sin(2 * np.pi * (h - 9) / 24)
            - 2.5 * wet + 5 * heat_event + rng.normal(0, 0.6, n))
    rain = wet * (rng.random(n) < 0.3) * rng.exponential(3, n)
    humidity = np.clip(55 + 20 * wet + np.where((month >= 6) & (month <= 9), 12, 0) - 1.5 * (temp - 29) + rng.normal(0, 3, n), 25, 98)
    emit("weather", "_site", "weather", "temp_c", temp)
    emit("weather", "_site", "weather", "humidity_pct", humidity)
    emit("weather", "_site", "weather", "rainfall_mm", rain)
    cool = 1 + 0.035 * np.clip(temp - 26, 0, None)

    zones = cfg["zones"]
    occ_z = {z["id"]: occupancy(z["type"], h, dow, hol, sched) for z in zones}
    non_parking = [z for z in zones if z["type"] != "parking"]

    # ---- energy --------------------------------------------------------------------------------
    outage = np.zeros(n, bool)
    for s in rng.choice(n - 6, 5, replace=False):
        outage[s:s + int(rng.integers(2, 5))] = True
    spike_zones = rng.choice(len(non_parking), 3, replace=False)
    spike_starts = rng.choice(np.arange(72, n - 5), 3, replace=False)
    site_kwh = np.zeros(n)
    fault_zone = non_parking[int(rng.integers(len(non_parking)))]["id"]
    for z in zones:
        sens = cool if z["type"] in HVAC_SENSITIVE else 1 + (cool - 1) * 0.3
        kwh = z["load_kw"] * (0.35 + 0.65 * occ_z[z["id"]]) * sens * (1 + rng.normal(0, 0.04, n))
        lab = label_none()
        for zi, st in zip(spike_zones, spike_starts):
            if non_parking[zi]["id"] == z["id"]:
                d = int(rng.integers(2, 4))
                kwh[st:st + d] *= 1.9; lab[st:st + d] = "energy_spike"
        site_kwh += kwh
        if z["id"] == fault_zone:
            flatline(kwh, lab)
        emit("energy", z["id"], f"meter-{z['id']}", "kwh", kwh, lab)
    clear = np.where((h >= 6) & (h <= 18), np.clip(np.sin(np.pi * (h - 6) / 12), 0, None) ** 1.3, 0)
    cloud = np.where(wet_day[codes], 0.8, rng.beta(1.5, 5, len(uniques))[codes])
    solar = cfg["solar_kw"] * clear * (1 - 0.65 * cloud) * (1 + rng.normal(0, 0.03, n))
    emit("energy", "_site", "solar", "solar_kwh", np.clip(solar, 0, None))
    emit("energy", "_site", "dg", "dg_kwh", np.where(outage, 0.85 * site_kwh, 0))

    # ---- water ---------------------------------------------------------------------------------
    wet_zones = [z for z in zones if z["water_kld"] >= 30]
    leak_zone = max(wet_zones, key=lambda z: z["water_kld"])["id"]
    leak_start = n - 72
    total_flow = np.zeros(n)
    for z in zones:
        flow = z["water_kld"] / 24 * occ_z[z["id"]] / 0.55 * (1 + rng.normal(0, 0.06, n))
        lab = label_none()
        if z["id"] == leak_zone:
            flow[leak_start:] += max(0.35 * z["water_kld"] / 24, 0.05)
            lab[leak_start:] = "leak"
        elif z["water_kld"] >= 30 and rng.random() < 0.5:
            flatline(flow, lab)
        total_flow += flow
        emit("water", z["id"], f"wmeter-{z['id']}", "flow_kl", np.clip(flow, 0, None), lab)
    emit("water", "_site", "tank", "tank_level_pct",
         np.clip(68 + 18 * np.sin(2 * np.pi * (h - 3) / 24) - 0.4 * (total_flow - total_flow.mean()) + rng.normal(0, 1.5, n), 5, 100))

    # ---- air quality ---------------------------------------------------------------------------
    base = np.vectorize(MONTH_PM25.get)(month).astype(float)
    day_noise = np.exp(rng.normal(0, 0.22, len(uniques)))[codes]
    diurnal = 1 + 0.25 * _gauss(h, 8.5, 2) + 0.3 * _gauss(h, 20, 2.5)
    ep_cand = [z for z in zones if z["type"] in ("utility", "industrial")] or [z for z in zones if z["type"] == "parking"]
    ep_zone = ep_cand[0]["id"]
    ep_start = n - 5 * 24 + 18
    for z in zones:
        f = PM_ZONE_FACTOR.get(z["type"], 1.0)
        pm25 = base * f * diurnal * day_noise * np.exp(rng.normal(0, 0.1, n)) * np.where(rain > 1, 0.6, 1.0)
        lab = label_none()
        if z["id"] == ep_zone:
            k = np.arange(14)
            bump = 150 * np.sin(np.pi * (k + 0.5) / 14)
            pm25[ep_start:ep_start + 14] += bump
            lab[ep_start:ep_start + 14] = "pollution_episode"
        pm25f = pm25.copy(); lab25 = lab.copy()
        if z["type"] == "parking":
            flatline(pm25f, lab25)
        pm10 = pm25 * 1.75 * np.exp(rng.normal(0, 0.08, n))
        no2 = 18 + 0.3 * pm25 + rng.normal(0, 2, n)
        emit("air", z["id"], f"aq-{z['id']}", "pm25", pm25f, lab25)
        emit("air", z["id"], f"aq-{z['id']}", "pm10", pm10, lab)
        emit("air", z["id"], f"aq-{z['id']}", "no2", no2)

    # ---- waste bins ----------------------------------------------------------------------------
    clin_cycle = ["biomedical", "wet", "dry", "e-waste"]
    std_cycle = ["wet", "dry", "e-waste"]
    cycle = clin_cycle if cfg["type"] == "hospital" else std_cycle
    canteen_ids = {z["id"] for z in zones if z["type"] == "canteen"}
    for z in zones:
        coll_hours = [7, 14] if z["type"] == "canteen" else ([7, 19] if z["type"] == "clinical" else [7])
        for i in range(z["bins"]):
            daily = rng.uniform(95, 125) if z["type"] == "canteen" else rng.uniform(45, 85)
            rate = daily / 24 * occ_z[z["id"]] / occ_z[z["id"]].mean()
            fill, vals, lab = rng.uniform(5, 20), np.zeros(n), label_none()
            skip_from = n - 48 if (z["id"] in canteen_ids and i < 2) else n + 1
            for t in range(n):
                fill = min(100.0, fill + rate[t] * (1 + rng.normal(0, 0.1)))
                if h[t] in coll_hours and t < skip_from:
                    fill = rng.uniform(3, 9)
                vals[t] = fill
                if t >= skip_from and fill >= 98:
                    lab[t] = "bin_overflow"
            emit("waste", z["id"], f"bin-{z['id']}-{i + 1}", "fill_pct", vals, lab)

    # ---- traffic and parking -------------------------------------------------------------------
    pop = sum(cfg["population"].values())
    mid_ = (sched["work_start"] + sched["work_end"]) / 2
    day_f = np.where(hol | (dow >= 5), sched["weekend_factor"], 1.0)
    prof = (_gauss(h, sched["work_start"] - 0.5, 1.0) + 0.8 * _gauss(h, sched["work_end"], 1.5) + 0.12) * day_f
    veh = rng.poisson(np.clip(pop * 0.055 * prof, 0.5, None)).astype(float)
    emit("traffic", "_site", "gate-main", "vehicles_in", veh)
    emit("traffic", "_site", "gate-main", "queue_min", np.clip((veh - pop * 0.03) / max(pop * 0.03, 1) * 6, 0, None))
    for z in zones:
        if z["type"] == "parking":
            occp = 100 * np.clip(occ_z[z["id"]] * 0.97 + rng.normal(0, 0.03, n), 0.02, 1.0)
            emit("traffic", z["id"], f"park-{z['id']}", "occupancy_pct", occp)

    # ---- assets --------------------------------------------------------------------------------
    zone_type = {z["id"]: z["type"] for z in zones}
    degr = [a for a in cfg["assets"][1:] if a["type"] != "dg"][0]["id"]
    for a in cfg["assets"]:
        zocc = occ_z[a["zone"]]
        if a["type"] == "dg":
            util = np.where(outage, rng.uniform(55, 80, n), 0.0)
        elif a["type"] == "hvac":
            util = 100 * np.clip(0.2 + 0.6 * zocc + 0.02 * (temp - 26), 0, 1)
        else:
            util = 100 * np.clip(0.85 * zocc + rng.normal(0, 0.03, n), 0, 1)
        base_vib = 1.6 + (sum(map(ord, a["id"])) % 8) / 10
        vib = base_vib + 0.5 * util / 100 + rng.normal(0, 0.08, n)
        tmp = 42 + 0.3 * util + 0.25 * temp + rng.normal(0, 0.6, n)
        lab = label_none()
        service_days = 25 + (sum(map(ord, a["id"])) * 7) % 150
        if a["id"] == degr:
            ramp = np.clip((np.arange(n) - (n - 25 * 24)) / (25 * 24), 0, 1)
            vib = vib + 3.6 * ramp ** 1.5
            tmp = tmp + 14 * ramp ** 1.5
            lab[(vib - base_vib) > 2.0] = "degradation"
            service_days = 230
        emit("assets", a["zone"], a["id"], "util_pct", util)
        emit("assets", a["zone"], a["id"], "vibration_mm_s", vib, lab)
        emit("assets", a["zone"], a["id"], "temp_c", tmp)
        sd = pd.DataFrame({"ts": ts[::24], "module": "assets", "zone": a["zone"], "entity": a["id"],
                           "metric": "days_since_service", "value": service_days - (len(ts[::24]) - 1 - np.arange(len(ts[::24]))), "label": ""})
        parts.append(sd)

    readings = pd.concat(parts, ignore_index=True)

    # ---- safety incidents ----------------------------------------------------------------------
    inc = []
    hot_zone = max(non_parking, key=lambda z: z["load_kw"])["id"]
    sev_p = [0.55, 0.30, 0.12, 0.03] if cfg["type"] != "industrial_estate" else [0.4, 0.35, 0.18, 0.07]
    for z in zones:
        lam = 0.05 + 0.06 * (z["type"] in ("industrial", "utility", "clinical", "parking"))
        for d in range(days):
            k = rng.poisson(lam * (3.2 if (z["id"] == hot_zone and d >= days - 20) else 1.0))
            for _ in range(k):
                t = ts[0] + pd.Timedelta(days=d, hours=int(rng.integers(0, 24)))
                if t > end:
                    continue
                inc.append({"ts": t, "zone": z["id"], "kind": str(rng.choice(INCIDENT_KINDS)),
                            "severity": int(rng.choice([1, 2, 3, 4], p=sev_p)),
                            "status": "open" if (end - t).days < 7 and rng.random() < 0.7 else "closed"})
    incidents = pd.DataFrame(inc, columns=["ts", "zone", "kind", "severity", "status"])
    return readings, incidents
