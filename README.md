# EstateIQ: Sustainable Facility and Estate Intelligence Dashboard for India

An AI-assisted decision dashboard for government and institution-run facilities (hospitals, colleges, company campuses, PSUs, industrial estates, municipal complexes). It ingests sensor-style data, visualises trends, detects anomalies, forecasts short-term changes, simulates "what if" scenarios and turns all of it into plain-language, role-specific action recommendations.

> **All data is synthetic.** Outputs are decision-support insights, not official measurements. See `docs/ASSUMPTIONS.md`.

## Quick start

**Docker (recommended)**
```bash
cp .env.example .env
docker compose up --build        # web: http://localhost:3000   API docs: http://localhost:8000/docs
```

**Without Docker** (SQLite, two terminals)
```bash
# terminal 1: API
cd backend && pip install -r requirements.txt && uvicorn app.main:app --reload --port 8000
# terminal 2: web
cd frontend && npm install && npm run dev        # http://localhost:5173
```
The first start generates 90 days of data for the default facility (about 4 seconds). Other facilities are generated the first time you switch to them. Optional: `cd backend && python ../scripts/seed_all.py` pre-generates all six.

**Demo logins**

| Role | Username | Password | Lands on |
|---|---|---|---|
| Administrator | `admin` | `admin123` | Command centre |
| Operations team | `ops` | `ops123` | Waste |
| Sustainability officer | `green` | `green123` | Scorecard |

## What is inside

| Area | What it does |
|---|---|
| Command centre | KPIs, site plan with zone status, top actions for your role, alert feed, live-scenario buttons |
| Air quality | Zone PM2.5, CPCB categories, IDW hotspot map, 24 h forecast, advisory text |
| Energy | Daily load/cost, solar and DG share, peak-hour exposure, 24 h / 7 day forecast, load-shift saving |
| Water | Per-person use vs benchmark, leak watch, tank forecast, rainwater potential |
| Waste | Bin map, overflow probability, optimised collection route vs round of all bins |
| Traffic and parking | Gate arrivals, queue estimate, parking hotspots and forecast |
| Assets | Failure-risk ranking with reasons, idle assets, feature importance |
| Safety | Incident trend, zone risk ranking, open incidents |
| Emissions and climate | Scope 1/2/3 (indicative), heat and rain readiness |
| Scorecard | 0-100 weighted score, month-on-month, CSV export, print view |
| Scenario simulator | Solar, AC setpoint, load shifting, extra collections, leak fix, occupancy |
| Insights and actions | Ranked recommendation cards with owner, impact, confidence, status; "Ask the dashboard"; advisory drafts |
| Settings | Assumptions, editable thresholds/tariffs/emission factors, CSV upload, data quality, audit trail |

Six facility types are configured in `config/facilities/*.yaml`. Switching facility in the top bar changes zones, load patterns, thresholds, tariffs and the sustainability weights.

## Architecture

```
React 18 + TypeScript (Vite, Tailwind, ECharts, TanStack Query)
        |  REST /api/v1  +  WebSocket /api/v1/ws/live     (nginx in Docker)
FastAPI  -> routers -> services (analytics, scenarios, live) -> ml (forecast, anomaly, waste, maintenance, risk) + engine (recommendations, insights, optional LLM)
        |
PostgreSQL 16 / TimescaleDB (SQLite fallback)    sensor data in one long-format `readings` table
```
See `docs/ARCHITECTURE.md` for the full picture, `docs/API.md` for endpoints, `docs/MODEL_CARDS.md` for model accuracy and limits.

## Optional AI wording
Set `ANTHROPIC_API_KEY` in `.env` and the top recommendations and chat answers are rewritten by Claude from the computed facts only (numbers are never changed). Without a key, deterministic templates are used and everything still works.

## Tests
```bash
make test           # backend pytest (16 tests) + frontend typecheck + vitest
cd frontend && npm run e2e     # Playwright smoke tests against a running stack
```

## Notes and honest limits
- The Docker / PostgreSQL path has not been executed in the environment this was authored in; the SQLite path (backend tests, API, built frontend, WebSocket) was run end to end. Please run `docker compose up --build` once and report anything that differs.
- TimescaleDB hypertables are optional: after the API has started once, run `docker compose exec db psql -U estateiq -d estateiq -f /opt/timescale.sql`.
- The site plan is a schematic SVG drawn from zone coordinates (no map tiles), so the demo works offline. Swapping in MapLibre only requires replacing `frontend/src/components/SitePlan.tsx`.
- Forecasting uses gradient boosting instead of Prophet to keep installs light; the function in `backend/app/ml/forecasting.py` is the single place to swap models.
- PDF export is provided as a print-friendly view (browser Print / Save as PDF) and CSV downloads.

## Data sources to cite when you move beyond synthetic data
CPCB (air quality and PM2.5 bands), data.gov.in open datasets, NASA POWER (weather/solar), CEA (grid emission factors), your DISCOM tariff order.
