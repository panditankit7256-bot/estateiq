"""Print accuracy metrics for every model on the default (synthetic) facility. Used to fill docs/MODEL_CARDS.md.
Run: cd backend && python ../scripts/model_report.py"""
import os, sys, json
sys.path.insert(0, os.getcwd())
os.environ.setdefault("DATABASE_URL", "sqlite:////tmp/report.db")
os.environ.setdefault("FIXED_NOW", "2026-10-09T14:00:00")
from app.db.seed import init_db, seed_facility
from app.services import analytics as A
fid = os.environ.get("FACILITY", "engineering_college")
init_db(); seed_facility(fid)
for mod, met in [("energy", "kwh"), ("water", "flow_kl"), ("air", "pm25"), ("traffic", "occupancy_pct")]:
    print("forecast", mod, met, json.dumps(A.forecast_view(fid, mod, met, 24)["metrics"]))
print("anomaly", json.dumps(A.anomalies_view(fid)["evaluation"], indent=1))
print("assets", [(a["id"], a["risk_band"], a["risk"]) for a in A.assets_view(fid)["assets"]], A.assets_view(fid)["feature_importance"])
print("score", A.scorecard(fid)["current"]["overall"])
