"""Pre-generate synthetic data for all six facility types so the first switch in the UI is instant.
Run: cd backend && python ../scripts/seed_all.py"""
import os, sys
sys.path.insert(0, os.getcwd())
from app.core.facilities import list_facility_ids
from app.db.seed import init_db, seed_facility
init_db()
for fid in list_facility_ids():
    print(fid, seed_facility(fid), "readings")
