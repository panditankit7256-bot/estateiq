"""'Ask the dashboard' chat and advisory generator, grounded in computed facts (never free-form data)."""
from __future__ import annotations
import re
import pandas as pd
from ..services import analytics as A, data as D
from . import llm, recommendations as R

TOPICS = {"energy": r"energy|power|electric|kwh|bill|cost|tariff|solar|peak", "water": r"water|leak|tank|lpcd", "air": r"air|aqi|pm2|pm10|pollut|dust|smoke",
          "waste": r"waste|bin|garbage|collection|overflow", "traffic": r"park|traffic|gate|vehicle|queue", "assets": r"asset|maintenance|equipment|machine|pump|chiller",
          "safety": r"safety|incident|accident|inspection", "emissions": r"carbon|co2|emission|scope", "score": r"score|grade|sustainab"}


def _energy_why(fid: str) -> dict:
    cfg = A.cfg_of(fid)
    f = A._energy_frame(fid, 14)
    cur, prev = f.iloc[-168:], f.iloc[-336:-168]
    temp = D.load(fid, "weather", "temp_c", 14).set_index("ts")["value"]
    tc, tp = float(temp.iloc[-168:].mean()), float(temp.iloc[:-168].mean())
    return {"cost_this_week_inr": round(float(cur["cost"].sum())), "cost_last_week_inr": round(float(prev["cost"].sum())),
            "cost_change_pct": round((float(cur["cost"].sum()) / max(float(prev["cost"].sum()), 1) - 1) * 100, 1),
            "kwh_change_pct": round((float(cur["total"].sum()) / max(float(prev["total"].sum()), 1) - 1) * 100, 1),
            "avg_temp_c_this_week": round(tc, 1), "avg_temp_c_last_week": round(tp, 1),
            "peak_share_this_week_pct": round(float(cur.loc[cur["peak"], "grid"].sum() / max(cur["grid"].sum(), 1) * 100), 1),
            "peak_share_last_week_pct": round(float(prev.loc[prev["peak"], "grid"].sum() / max(prev["grid"].sum(), 1) * 100), 1),
            "solar_kwh_change_pct": round((float(cur["solar"].sum()) / max(float(prev["solar"].sum()), 1) - 1) * 100, 1),
            "dg_kwh_this_week": round(float(cur["dg"].sum())), "dg_kwh_last_week": round(float(prev["dg"].sum()))}


def _facts(fid: str, topics: list[str]) -> dict:
    out: dict = {}
    for t in topics:
        if t == "energy":
            ev = A.energy_view(fid); out["energy"] = {"why_cost_changed": _energy_why(fid), "total_kwh_30d": ev["total_kwh"], "cost_inr_30d": ev["cost_inr"], "peak_demand_kw": ev["peak_demand_kw"],
                                                       "peak_window_share_pct": ev["peak_window_share_pct"], "solar_share_pct": ev["solar_share_pct"], "shift_saving_inr_month": ev["shift"]["saving_inr_per_month"]}
        elif t == "water":
            w = A.water_view(fid); out["water"] = {"lpcd": w["lpcd"], "benchmark_lpcd": w["benchmark_lpcd"], "leak_suspects": [z for z in w["zones"] if z["leak_suspect"]]}
        elif t == "air":
            a = A.air_view(fid); out["air"] = {"campus_pm25_24h": a["campus_pm25_24h"], "category": a["category"]["label"], "hotspot": a["hotspot"]["name"], "hotspot_pm25": a["hotspot"]["pm25_24h"]}
        elif t == "waste":
            w = A.waste_view(fid); out["waste"] = {"bins_needing_pickup": [b["id"] for b in w["bins"] if b["alert"]], "route_km_current": w["route"]["current_km"], "route_km_optimized": w["route"]["optimized_km"]}
        elif t == "traffic":
            v = A.traffic_view(fid); out["traffic"] = {"gate_peak_hour": v["peak_hour"], "parking": [{k: p[k] for k in ("name", "now_pct", "hours_over_90_14d", "peak_hour")} for p in v["parking"]]}
        elif t == "assets":
            v = A.assets_view(fid); out["assets"] = [{k: a[k] for k in ("name", "risk", "risk_band", "reasons")} for a in v["assets"][:3]]
        elif t == "safety":
            v = A.safety_view(fid); out["safety"] = {"open_incidents": v["open"], "top_zone": v["zone_risk"][0]["name"], "top_zone_30d": v["zone_risk"][0]["incidents_30d"], "prev_30d": v["zone_risk"][0]["incidents_prev30d"]}
        elif t == "emissions":
            v = A.emissions_view(fid); out["emissions"] = {k: v[k] for k in ("scope1_kg", "scope2_kg", "scope3_indicative_kg", "solar_avoided_kg")}
        elif t == "score":
            s = A.scorecard(fid)["current"]; out["score"] = {"overall": s["overall"], "grade": s["grade"], "sub": s["sub"]}
    return out


def _template(question: str, facts: dict) -> str:
    lines = []
    e = facts.get("energy")
    if e:
        w = e["why_cost_changed"]
        direction = "rose" if w["cost_change_pct"] > 0 else "fell"
        drivers = []
        if abs(w["kwh_change_pct"]) >= 1: drivers.append(f"energy use changed {w['kwh_change_pct']:+.1f}%")
        if abs(w["avg_temp_c_this_week"] - w["avg_temp_c_last_week"]) >= 0.5: drivers.append(f"average temperature moved from {w['avg_temp_c_last_week']} to {w['avg_temp_c_this_week']} °C (cooling load)")
        if abs(w["peak_share_this_week_pct"] - w["peak_share_last_week_pct"]) >= 1: drivers.append(f"peak-hour share went from {w['peak_share_last_week_pct']}% to {w['peak_share_this_week_pct']}%")
        if w["dg_kwh_this_week"] != w["dg_kwh_last_week"]: drivers.append(f"DG energy changed from {w['dg_kwh_last_week']} to {w['dg_kwh_this_week']} kWh")
        lines.append(f"Electricity cost {direction} {abs(w['cost_change_pct'])}% this week (₹{w['cost_this_week_inr']:,} vs ₹{w['cost_last_week_inr']:,}). Likely drivers: " + ("; ".join(drivers) or "no single large driver") + f". Shifting flexible loads off-peak could save about ₹{e['shift_saving_inr_month']:,.0f} per month.")
    if (w := facts.get("water")): lines.append(f"Water use is {w['lpcd']} L/person/day against a benchmark of {w['benchmark_lpcd']}. " + (f"Possible leak in: {', '.join(z['name'] for z in w['leak_suspects'])}." if w["leak_suspects"] else "No leak suspects right now."))
    if (a := facts.get("air")): lines.append(f"Campus PM2.5 (24 h) is {a['campus_pm25_24h']} µg/m³ ({a['category']}); highest at {a['hotspot']} ({a['hotspot_pm25']}). Indicative only.")
    if (w := facts.get("waste")): lines.append(f"{len(w['bins_needing_pickup'])} bins need pickup; the optimised route is {w['route_km_optimized']} km versus {w['route_km_current']} km.")
    if (t := facts.get("traffic")): lines.append(f"Gate traffic peaks around {t['gate_peak_hour']}:00. " + "; ".join(f"{p['name']} is {p['now_pct']}% full" for p in t["parking"]) + ".")
    if (a := facts.get("assets")): lines.append("Highest-risk assets: " + "; ".join(f"{x['name']} ({x['risk_band']}, risk {x['risk']})" for x in a) + ".")
    if (s := facts.get("safety")): lines.append(f"{s['open_incidents']} incidents are open; {s['top_zone']} is the highest-risk zone ({s['top_zone_30d']} incidents in 30 days vs {s['prev_30d']} before).")
    if (m := facts.get("emissions")): lines.append(f"Emissions (30 days): Scope 1 {m['scope1_kg']:,} kg, Scope 2 {m['scope2_kg']:,} kg, indicative Scope 3 {m['scope3_indicative_kg']:,} kg CO2e; solar avoided {m['solar_avoided_kg']:,} kg.")
    if (s := facts.get("score")): lines.append(f"Sustainability score is {s['overall']} (grade {s['grade']}); weakest area: {min(s['sub'], key=s['sub'].get)}.")
    return " ".join(lines)


def ask(fid: str, question: str) -> dict:
    topics = [t for t, pat in TOPICS.items() if re.search(pat, question, re.I)] or ["energy", "water", "air", "waste", "score"]
    facts = _facts(fid, topics[:4])
    ai = llm.answer(question, facts)
    return {"answer": ai or _template(question, facts), "mode": "llm" if ai else "template", "topics": topics[:4], "facts": facts,
            "disclaimer": "Decision-support insight from (synthetic) facility data, not an official measurement."}


def advisory(fid: str, kind: str, channel: str) -> dict:
    cfg = A.cfg_of(fid)
    name = cfg["name"]
    if kind == "air":
        a = A.air_view(fid)
        body = (f"Air-quality advisory for {name}: PM2.5 over the last 24 h averaged {a['campus_pm25_24h']} µg/m³ ({a['category']['label']}), highest near {a['hotspot']['name']}. {a['advisory']}")
    elif kind == "heat":
        e = A.emissions_view(fid)
        body = (f"Heat advisory for {name}: {e['heat_days']} days at or above 35 °C in the last 30 days. Drink water regularly, avoid outdoor activity in the afternoon, and report heat-related discomfort to the help desk.")
    elif kind == "water":
        w = A.water_view(fid)
        s = [z["name"] for z in w["zones"] if z["leak_suspect"]]
        body = f"Water notice for {name}: use is {w['lpcd']} L/person/day (benchmark {w['benchmark_lpcd']}). " + (f"Maintenance is checking a possible leak in {', '.join(s)}; short supply interruptions may occur." if s else "Please report dripping taps and overflowing tanks.")
    elif kind == "waste":
        w = A.waste_view(fid)
        body = f"Waste notice for {name}: {sum(b['alert'] for b in w['bins'])} bins are near capacity. Collection teams are re-routed; please segregate wet, dry and e-waste and avoid placing waste beside full bins."
    else:
        body = f"Notice for {name}: please conserve energy and water, segregate waste, and report unsafe conditions to the estate office."
    if channel == "sms":
        text = body if len(body) <= 300 else body[:297] + "..."
        return {"channel": "sms", "kind": kind, "subject": None, "body": text, "chars": len(text)}
    return {"channel": "email", "kind": kind, "subject": f"[{cfg['name']}] {kind.title()} advisory", "body": f"Dear all,\n\n{body}\n\nRegards,\nEstate Office\n\n(Decision-support message generated from facility sensor data; indicative, not an official measurement.)", "chars": len(body)}
