import io

H = "/api/v1"


def test_health(client):
    assert client.get("/healthz").json() == {"status": "ok"}


def test_auth_required_and_login_roles(client, admin):
    assert client.get(f"{H}/overview").status_code == 401
    assert client.post(f"{H}/auth/login", json={"username": "admin", "password": "nope"}).status_code == 401
    me = client.get(f"{H}/auth/me", headers=admin).json()
    assert me["role"] == "administrator" and "edit_config" in me["permissions"]


def test_overview_and_modules(client, admin):
    ov = client.get(f"{H}/overview", headers=admin).json()
    assert ov["kpis"]["energy_kwh_24h"] > 0 and len(ov["zones"]) == 7
    for path in ("views/air", "views/energy", "views/water", "views/waste", "views/traffic", "views/assets", "views/safety", "views/emissions", "scorecard", "data-quality"):
        assert client.get(f"{H}/{path}", headers=admin).status_code == 200, path
    m = client.get(f"{H}/metrics/energy?days=2", headers=admin).json()
    assert len(m["ts"]) == 48 and m["unit"] == "kWh"


def test_forecast_and_anomalies(client, admin):
    f = client.get(f"{H}/forecast/energy?horizon=24", headers=admin).json()
    assert f["metrics"]["improvement_vs_baseline_pct"] is not None and len(f["yhat"]) == 24
    a = client.get(f"{H}/anomalies", headers=admin).json()
    assert a["events"] and all("explanation" in e for e in a["events"])


def test_recommendations_are_role_filtered_and_actionable(client, admin, ops, green):
    all_r = client.get(f"{H}/recommendations", headers=admin).json()["recommendations"]
    ops_r = client.get(f"{H}/recommendations", headers=ops).json()["recommendations"]
    assert all_r and len(ops_r) <= len(all_r)
    assert all(r["owner"] == "operations" or r["urgency"] == "Critical" for r in ops_r)
    for r in all_r:
        assert r["action"] and r["basis"] and r["urgency"] in ("Critical", "High", "Medium", "Low")
    key = ops_r[0]["key"]
    assert client.patch(f"{H}/actions/{key}", headers=ops, json={"status": "In progress"}).status_code == 200
    assert client.patch(f"{H}/actions/{key}", headers=ops, json={"status": "Bogus"}).status_code == 422


def test_rbac(client, admin, ops, green):
    body = {"thresholds": {"pm25_alert": 70}}
    assert client.put(f"{H}/facilities/engineering_college/config", headers=ops, json=body).status_code == 403
    r = client.put(f"{H}/facilities/engineering_college/config", headers=admin, json=body)
    assert r.status_code == 200 and r.json()["thresholds"]["pm25_alert"] == 70
    assert client.put(f"{H}/facilities/engineering_college/config", headers=admin, json={"thresholds": {"nope": 1}}).status_code == 422
    client.put(f"{H}/facilities/engineering_college/config", headers=admin, json={"thresholds": {"pm25_alert": 60}})
    assert client.get(f"{H}/audit", headers=green).status_code == 403
    assert client.post(f"{H}/advisories/generate", headers=green, json={"kind": "air", "channel": "sms"}).status_code == 403


def test_scenario_math_is_monotonic(client, admin):
    base = client.post(f"{H}/scenarios/simulate", headers=admin, json={}).json()
    sol = client.post(f"{H}/scenarios/simulate", headers=admin, json={"add_solar_kw": 200}).json()
    ac = client.post(f"{H}/scenarios/simulate", headers=admin, json={"ac_setpoint_delta_c": 2}).json()
    shift = client.post(f"{H}/scenarios/simulate", headers=admin, json={"shift_peak_pct": 30}).json()
    assert base["monthly"]["cost_saving_inr"] == 0
    assert sol["monthly"]["cost_saving_inr"] > 0 and sol["monthly"]["co2_saving_kg"] > 0
    assert ac["monthly"]["kwh_saving"] > 0
    assert shift["monthly"]["cost_saving_inr"] > 0 and shift["monthly"]["kwh_saving"] == 0
    assert sol["assumptions"]


def test_ingest_validation_and_csv(client, admin):
    good = {"ts": "2026-10-09T14:00:00", "zone": "acad", "entity": "aq-acad", "metric": "pm25", "value": 41.5}
    bad_range = {**good, "ts": "2026-10-09T15:00:00", "value": 5000}
    bad_zone = {**good, "ts": "2026-10-09T16:00:00", "zone": "nowhere"}
    r = client.post(f"{H}/ingest/air", headers=admin, json={"readings": [good, bad_range, bad_zone]}).json()
    assert r["accepted"] == 0 and r["rejected"] == 3  # first is a duplicate of existing data
    csv = "ts,module,zone,entity,metric,value\n2026-10-09T15:00:00,air,acad,aq-acad,pm25,44\n"
    up = client.post(f"{H}/ingest/upload", headers=admin, files={"file": ("a.csv", io.BytesIO(csv.encode()), "text/csv")}).json()
    assert up["accepted"] == 1


def test_chat_advisory_and_export(client, admin):
    c = client.post(f"{H}/insights/chat", headers=admin, json={"question": "Why did energy cost rise this week?"}).json()
    assert "Electricity cost" in c["answer"] and c["mode"] == "template"
    adv = client.post(f"{H}/advisories/generate", headers=admin, json={"kind": "air", "channel": "sms"}).json()
    assert adv["chars"] <= 300
    assert client.get(f"{H}/reports/export?kind=scorecard", headers=admin).text.startswith("window,overall")


def test_facility_switch_and_live_spike(client, admin):
    assert client.get(f"{H}/overview?facility=government_hospital", headers=admin).json()["facility"]["id"] == "government_hospital"
    assert client.get(f"{H}/overview?facility=zzz", headers=admin).status_code == 404
    r = client.post(f"{H}/simulate/spike", headers=admin, json={"kind": "pollution"}).json()
    assert r["added_hours"] == 3
    ev = client.get(f"{H}/anomalies?module=air", headers=admin).json()["events"]
    assert any(e["active"] for e in ev)
