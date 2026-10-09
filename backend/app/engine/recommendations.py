"""Recommendation engine: structured findings (anomalies, forecasts, thresholds, model scores) -> ranked action cards.

Each card states what was detected, why it matters, the action, the owner, urgency, estimated impact, confidence and the
data/assumptions behind it. Narrative is template-based and optionally polished by an LLM (numbers never change)."""
from __future__ import annotations
import hashlib
import pandas as pd
from ..services import analytics as A, data as D
from ..services.cache import cached
from . import llm

URG = {"Critical": 0, "High": 1, "Medium": 2, "Low": 3}


def _rec(fid, rid, module, title, detected, why, action, owner, urgency, impact, confidence, basis, zone=None):
    return {"key": hashlib.sha1(f"{fid}:{rid}".encode()).hexdigest()[:12], "module": module, "zone": zone, "title": title, "detected": detected, "why": why,
            "action": action, "owner": owner, "urgency": urgency, "impact": impact, "confidence": confidence, "basis": basis, "narrative": "template"}


@cached
def build(fid: str) -> list[dict]:
    cfg = A.cfg_of(fid)
    zm = D.zone_map(cfg)
    now = D.last_ts(fid)
    an, ev, wv, av, wst = A.anomalies_view(fid), A.energy_view(fid), A.water_view(fid), A.air_view(fid), A.waste_view(fid)
    tv, asv, sv, scv = A.traffic_view(fid), A.assets_view(fid), A.safety_view(fid), A.scorecard(fid)
    t, tar = cfg["tariff"], cfg["thresholds"]
    recs: list[dict] = []
    W = A.GRID_ASSUMPTIONS["water_cost_inr_per_kl"]

    for z in wv["zones"]:
        if z["leak_suspect"]:
            recs.append(_rec(fid, f"leak:{z['zone']}", "water", f"Probable water leak in {z['name']}",
                f"Flow in {z['name']} between 1 and 5 am is {z['night_change_pct']:.0f}% above its usual level, roughly {z['excess_kl_per_day']:.1f} kL/day that should not be flowing.",
                "Continuous overnight flow when the area is empty usually means a leaking pipe, valve or float.",
                f"Send the plumbing team to inspect {z['name']} tonight; isolate the zone meter and check tanks, taps and underground lines.",
                "operations", "Critical" if z["excess_kl_per_day"] > 20 else "High",
                {"kl_month": round(z["excess_kl_per_day"] * 30), "inr_month": round(z["excess_kl_per_day"] * 30 * W)}, "High",
                ["Water meter data, last 72 h vs previous 27 days", f"Water valued at ₹{W:.0f}/kL (assumption)", "Rule: small-hours flow over the last 3 nights is 15%+ above the zone's earlier level and material in size"], z["zone"]))
    for e in an["events"]:
        recent = pd.Timestamp(e["end"]) >= now - pd.Timedelta(hours=72)
        if not recent:
            continue
        if e["module"] == "energy" and e["kind"] == "high":
            recs.append(_rec(fid, f"energy:{e['entity']}:{e['start']}", "energy", f"Abnormal electricity load in {e['zone_name']}",
                f"{e['zone_name']} meter peaked at {e['peak_value']:.0f} kWh/h versus a typical {e['typical_value']:.0f} for that hour (score {e['score']}).",
                "Unscheduled loads waste energy and money and can signal faulty equipment.", f"Check {e['zone_name']} for equipment left running or tripping; confirm with the zone in-charge and restore the normal schedule.",
                "operations", "High" if e["active"] else "Medium",
                {"kwh_month": 0, "inr_month": round((e["peak_value"] - e["typical_value"]) * e["hours"] * t["peak"]), "risk_note": "One-off excess cost during the event"},
                "Medium", ["Isolation Forest + hour-of-day baseline, temperature adjusted", "Cost at peak tariff"], e["zone"]))
        if e["kind"] == "flatline":
            recs.append(_rec(fid, f"sensor:{e['entity']}:{e['start']}", e["module"], f"Sensor {e['entity']} may be stuck",
                f"{e['entity']} sent the same value for {e['hours']} h.", "Bad data weakens forecasts and alerts for the whole zone.",
                "Inspect or reset the sensor and mark the interval as unreliable.", "operations", "Medium", {"risk_note": "Restores data quality"}, "Medium",
                ["Flatline rule: identical value for 4+ consecutive hours"], e["zone"]))
    worst = av["hotspot"]
    if worst["pm25_24h"] > tar["pm25_alert"] or av["campus_pm25_24h"] > tar["pm25_alert"]:
        recs.append(_rec(fid, "air:advisory", "air", f"Air-quality advisory: {av['category']['label']} levels, hotspot at {worst['name']}",
            f"Campus 24 h average PM2.5 is {av['campus_pm25_24h']:.0f} µg/m³ ({av['category']['label']}); {worst['name']} is highest at {worst['pm25_24h']:.0f}.",
            "Fine particles affect people with asthma, heart conditions, children and older adults (indicative; not an official AQI).",
            f"Send an advisory to sensitive groups, move outdoor sports indoors if levels stay high, and check sources near {worst['name']} (DG sets, burning, dust).",
            "administrator", "High" if worst["pm25_24h"] > 1.5 * tar["pm25_alert"] else "Medium", {"risk_note": "Reduces exposure for sensitive groups"}, "Medium",
            ["Zone PM2.5 sensors, last 24 h", f"Alert threshold {tar['pm25_alert']} µg/m³ (configurable)", "CPCB PM2.5 bands used for category"], worst["zone"]))
    alerts = [b for b in wst["bins"] if b["alert"]]
    if alerts:
        r = wst["route"]
        full = [b for b in alerts if b["fill_pct"] >= 95]
        recs.append(_rec(fid, "waste:route", "waste", f"Re-route waste collection: {len(alerts)} bins need pickup",
            f"{len(alerts)} of {len(wst['bins'])} bins are above {wst['threshold']}% or likely to overflow within 6 h ({len(full)} already full).",
            "Overflowing bins cause odour, pests and complaints; skipping low-fill bins saves fuel and time.",
            f"Collect only the flagged bins in the suggested order ({r['optimized_km']:.2f} km instead of {r['current_km']:.2f} km) and start with {', '.join(b['id'] for b in full[:3]) or alerts[0]['id']}.",
            "operations", "High" if full else "Medium", {"risk_note": f"Saves about {r['saved_km']:.2f} km per round", "km_saved": r["saved_km"]}, "High",
            ["Bin fill sensors", "Overflow classifier (gradient boosting), 6 h horizon", "Nearest-neighbour + 2-opt route"], alerts[0]["zone"]))
    for a in asv["assets"]:
        if a["risk_band"] in ("Critical", "High"):
            recs.append(_rec(fid, f"asset:{a['id']}", "assets", f"Schedule maintenance for {a['name']}",
                f"{a['name']} has a failure-risk score of {a['risk']:.2f} ({a['risk_band']}): " + "; ".join(a["reasons"] or ["condition indicators rising"]) + ".",
                "Rising vibration and temperature often precede breakdowns that cause unplanned downtime.", f"Book an inspection or service for {a['name']} within the week and keep a standby ready.",
                "operations", "Critical" if a["risk_band"] == "Critical" else "High", {"risk_note": "Avoids unplanned downtime"}, "Medium",
                ["RandomForest on vibration, temperature, utilisation and service age, blended with a rule score", "Trained on synthetic labels"], a["zone"]))
    idle = [a for a in asv["assets"] if a["idle"]]
    if idle:
        recs.append(_rec(fid, "asset:idle", "assets", f"{len(idle)} assets are barely used",
            ", ".join(f"{a['name']} ({a['util_7d_pct']:.0f}%)" for a in idle[:4]) + " ran below 15% utilisation in the last 7 days.",
            "Idle equipment still draws standby power and ties up maintenance budget.", "Review whether to switch off, share or retire these assets.",
            "sustainability", "Low", {"kwh_month": round(sum(a["rated_kw"] for a in idle) * 0.05 * 720)}, "Low", ["Utilisation sensors, 7 days", "Assumes 5% standby draw of rated power"]))
    over = [p for p in tv["parking"] if p["hours_over_90_14d"] >= 10]
    if over:
        p = max(over, key=lambda x: x["hours_over_90_14d"])
        recs.append(_rec(fid, f"parking:{p['zone']}", "traffic", f"Parking hotspot at {p['name']}",
            f"{p['name']} was above 90% full for {p['hours_over_90_14d']} h in the last 14 days, peaking around {p['peak_hour']}:00.",
            "Full parking creates entry queues and drivers circling for slots.", f"Open overflow parking before {max(p['peak_hour'] - 1, 0)}:00, stagger arrival times and add signage to alternate lots.",
            "administrator", "Medium", {"risk_note": "Shorter gate queues at peak"}, "Medium", ["Parking occupancy sensors, 14 days"], p["zone"]))
    pk = ev["peak_window_share_pct"]
    if pk > 15:
        recs.append(_rec(fid, "energy:shift", "energy", "Shift flexible loads out of peak-tariff hours",
            f"{pk:.0f}% of grid energy is used during peak hours ({t['peak_start']}:00 to {t['peak_end']}:00) at ₹{t['peak']}/kWh versus ₹{t['offpeak']} off-peak.",
            "Moving flexible loads such as pumps, pre-cooling and charging cuts the bill without cutting service.",
            "Run water pumps and pre-cool buildings before the peak window and delay non-urgent loads until after it.", "sustainability", "Medium",
            {"inr_month": ev["shift"]["saving_inr_per_month"], "kwh_month": 0, "co2_kg_month": 0}, "Medium",
            ["Hourly energy and tariff slabs", ev["shift"]["assumption"]]))
    rising = [z for z in sv["zone_risk"] if z["incidents_30d"] >= 3 and z["incidents_30d"] > 1.4 * max(z["incidents_prev30d"], 1)]
    top = rising[0] if rising else None
    if top:
        recs.append(_rec(fid, f"safety:{top['zone']}", "safety", f"Prioritise safety inspection in {top['name']}",
            f"{top['name']} had {top['incidents_30d']} incidents in 30 days versus {top['incidents_prev30d']} the month before (risk index {top['risk_index']}).",
            "A rising incident trend in one zone is an early sign of unsafe conditions.", f"Inspect {top['name']} first (housekeeping, wiring, floors, equipment guards) and close the {top['open']} open incidents.",
            "administrator", "High", {"risk_note": "Targets the highest-risk zone"}, "Medium", ["Incident log", sv["method"]], top["zone"]))
    if wv["lpcd"] > 1.15 * wv["benchmark_lpcd"]:
        recs.append(_rec(fid, "water:lpcd", "water", "Water use per person is above benchmark",
            f"Average use is {wv['lpcd']:.0f} litres per person per day against a benchmark of {wv['benchmark_lpcd']:.0f}.",
            "High per-capita use often hides leaks, overflowing tanks and wasteful fixtures.", "Audit the highest-use zones, install aerators and consider rainwater harvesting "
            f"(about {wv['rainwater_harvest_kl_per_year']:,} kL/year potential).", "sustainability", "Medium", {"kl_month": round((wv["lpcd"] - wv["benchmark_lpcd"]) * sum(cfg["population"].values()) * 30 / 1000)}, "Medium",
            ["Water meters (30 days)", wv["rwh_assumption"]]))
    if ev["dg_hours"] > 0:
        recs.append(_rec(fid, "energy:dg", "energy", "Reduce diesel generator running hours",
            f"The DG ran for {ev['dg_hours']} h in the last 30 days ({ev['dg_share_pct']}% of energy).", "Diesel power is costly and adds local emissions.",
            "Check grid outage causes with the utility, test changeover, and consider battery backup or more solar for critical loads.", "sustainability", "Low",
            {"co2_kg_month": 0}, "Medium", ["DG meter data, 30 days"]))
    recs.sort(key=lambda r: (URG[r["urgency"]], r["module"]))
    return recs


def for_role(fid: str, role: str, polish: bool = False) -> list[dict]:
    recs = build(fid)
    if role == "operations":
        recs = [r for r in recs if r["owner"] == "operations" or r["urgency"] == "Critical"]
    elif role == "sustainability":
        recs = [r for r in recs if r["owner"] == "sustainability" or r["module"] in ("energy", "water", "air")]
    recs = [dict(r) for r in recs]
    if polish and llm.enabled():
        recs = [llm.polish(r) if i < 5 else r for i, r in enumerate(recs)]
    return recs
