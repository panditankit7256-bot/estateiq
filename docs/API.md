# API reference
Interactive docs: `http://localhost:8000/docs`. All routes are under `/api/v1`, need `Authorization: Bearer <token>` (except login) and accept `?facility=<id>` (default `engineering_college`).

| Method | Path | Purpose | Roles |
|---|---|---|---|
| POST | /auth/login | JWT login, returns role, permissions, home page | public |
| GET | /auth/me | Current user | any |
| GET | /facilities, /facilities/{id} | List facilities / config with overrides | any |
| PUT | /facilities/{id}/config | Update thresholds, tariff, emission, score weights | administrator |
| GET | /overview | KPIs and zone status for the command centre | any |
| GET | /metrics/{module} | Time series by zone (`metric`, `days`, `granularity=h|d`) | any |
| GET | /forecast/{module} | Forecast, 95% range, MAE/RMSE/MAPE vs seasonal-naive baseline | any |
| GET | /anomalies | Events with plain-language explanations and detection quality | any |
| GET | /views/{air,energy,water,waste,traffic,assets,safety,emissions} | Module dashboards | any |
| GET | /waste/routes | Current vs optimised collection route | any |
| GET | /scorecard | Weighted sustainability score, history | any |
| GET | /data-quality | Per-sensor completeness, last update, stuck-sensor count | any |
| POST | /ingest/{module} | JSON batch of readings with validation | administrator, operations |
| POST | /ingest/upload | CSV (`ts,module,zone,entity,metric,value`) | administrator, operations |
| GET | /recommendations | Ranked actions filtered for your role (`polish=true` for LLM wording) | any |
| PATCH | /actions/{key} | Update status Pending / In progress / Done | owner role or administrator |
| POST | /scenarios/simulate | Scenario levers in, before/after and assumptions out | any |
| POST | /insights/chat | Ask the dashboard, grounded in computed facts | any |
| POST | /advisories/generate | Draft email/SMS advisory | administrator, operations |
| GET | /reports/export | CSV: scorecard, recommendations, energy_daily | any |
| GET | /audit | Audit trail | administrator |
| POST | /simulate/spike | Demo: append 3 hours with leak / pollution / energy / bins / outage | administrator, operations |
| WS | /ws/live?token= | Pushes `data_update` events | any |
| GET | /healthz, /readyz | Health (outside `/api/v1`) | public |
