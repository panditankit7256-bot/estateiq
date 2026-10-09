# Architecture

## Layers
1. **Simulator** (`backend/app/simulator/generator.py`): hourly synthetic sensor data for air, energy, water, waste bins, traffic and parking, assets and weather, plus safety incidents. Uses facility config (zones, loads, schedule, holidays) and Indian patterns: summer heat, monsoon rain and cloud (solar dip), post-monsoon PM2.5, DG use during power cuts, exam/holiday cycles. Injects **labelled** anomalies (leak, energy spike, pollution episode, stuck sensor, bin overflow, equipment degradation) and a demo storyline in the final days (heat spell, hidden overnight leak, missed canteen collections, PM2.5 episode, worn pump, rising lab incidents).
2. **Storage** (`app/db`): `readings(facility_id, ts, module, zone, entity, metric, value, label)` plus `incidents`, `users`, `actions`, `audit_log`, `facility_overrides`. Indexed for time-range queries; optional TimescaleDB hypertable script.
3. **Ingestion** (`app/api/v1/data.py`): JSON batch and CSV upload with range checks, schema checks, in-batch and stored duplicate rejection; every import is audited.
4. **Analytics services** (`app/services/analytics.py`): per-module views (cached per facility, invalidated on any new data), scorecard, scenario simulation.
5. **ML** (`app/ml`): forecasting, anomaly detection, bin overflow classifier and route optimiser, maintenance risk model, safety zone risk, IDW hotspot grid.
6. **Engine** (`app/engine`): turns findings into recommendation cards; chat and advisory generation; optional LLM provider with deterministic fallback.
7. **API** (`app/api/v1`): FastAPI routers under `/api/v1`, JWT auth, role checks, CORS, per-IP rate limiting, request logging, health endpoints, WebSocket feed.
8. **Frontend** (`frontend/src`): React SPA, route-level code splitting, role-aware navigation, facility/time-window in the top bar (facility mirrored in `?f=` URL param), live updates via WebSocket that invalidate cached queries.

## Request flow for a live demo
`POST /simulate/spike` appends 3 hours of data with an injected incident, bumps the facility cache version, broadcasts `data_update` on the WebSocket; the browser invalidates its queries; analytics, anomalies and recommendations recompute (first recompute takes a few seconds).

## Role-based access
| Role | Default page | Menu | Can change |
|---|---|---|---|
| administrator | Command centre | everything | config, any action status, imports, audit view |
| operations | Waste | ops modules + insights | own actions, imports, advisories, live scenarios |
| sustainability | Scorecard | energy, water, air, emissions, scorecard, scenarios, insights | own actions |

Enforced on the API (`require_roles`) and in the UI (route guard + menu).

## Configuration
`config/facilities/<id>.yaml`: location, zones (coordinates, area, load, water, bins, parking capacity), assets, thresholds (PM2.5 alert, bin alert %, litres per person per day, kWh/m²/month target), tariff (peak/off-peak, peak window), emission factors, working schedule and holidays, sustainability score weights. Administrators can override thresholds, tariff, emission factors and weights from Settings (stored in `facility_overrides`).
