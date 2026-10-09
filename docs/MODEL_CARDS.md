# Model cards
Metrics below were produced by `make report` on the default synthetic facility (engineering college, 90 days, data ending 9 Oct 2026 14:00). They show the model works on this simulator, **not** how it will perform on real sites.

## 1. Short-term forecaster (`ml/forecasting.py`)
- **Method:** gradient boosting on lags (1, 2, 3, 24, 48, 168 h), 24 h rolling mean and calendar features; recursive multi-step. Approximate 95% band from recent residuals, widening with horizon.
- **Evaluation:** last 24 h held out; compared with seasonal-naive ("same hour yesterday").

| Series | MAE | MAPE | Naive MAE | Improvement |
|---|---|---|---|---|
| Energy (kWh/h, site) | 18.0 | 2.7% | 22.9 | 21% |
| Water (kL/h, site) | 0.88 | 3.4% | 1.12 | 21% |
| PM2.5 (µg/m³, campus mean) | 11.6 | 19.0% | 19.9 | 42% |
| Parking occupancy (%) | 2.5 | 12.5% | 2.6 | 6% |

- **Limits:** one 24 h holdout is a small sample; no external regressors; replace with Prophet or a regression with weather inputs for production.

## 2. Anomaly detector (`ml/anomaly.py`)
- **Method:** relative deviation from the entity's typical level for the same hour and weekday/weekend (7-day rolling median for drifting signals such as PM2.5), temperature adjustment for energy, IsolationForest as second opinion, flatline rule for stuck sensors; isolated one-hour blips are suppressed unless extreme.
- **Evaluation:** event-level against injected faults (consecutive hours = one event).

| Signal | Injected events | Found | Flagged events | Real |
|---|---|---|---|---|
| Energy | 4 | 100% | 4 | 100% |
| Water | 3 | 100% | 9 | 67% |
| PM2.5 | 2 | 100% | 2 | 100% |
| PM10 | 1 | 100% | 1 | 100% |

- Other facility types vary (for example PM2.5 precision falls where daily noise is heavy). Live numbers are shown in the app under "How reliable is detection?".
- **Limits:** slow equipment drift is deliberately *not* handled here (see model 4).

## 3. Bin overflow (`ml/waste.py`)
- **Method:** gradient boosting classifier for "bin reaches 90% within 6 h" using fill level, 6 h fill rate, hours since collection and hour of day; hours-to-90% from recent rate. Route = nearest neighbour + 2-opt over bins that are at or above the alert level or likely to overflow.
- **Limits:** trained and scored on the same simulated history (no held-out split); treat probabilities as a ranking aid.

## 4. Maintenance risk (`ml/maintenance.py`)
- **Method:** RandomForest on vibration and temperature excess over each asset's own first-30-day baseline, 24 h utilisation and days since service, blended 60/40 with a transparent rule score.
- **Result on demo data:** the injected degrading pump ranks first (Critical, 0.92); the other five assets stay Normal. Feature importance: vibration excess 0.55, service age 0.39.
- **Limits:** one degrading asset in the training data; real failure labels are required before relying on the probability part.

## 5. Safety zone risk (`ml/risk.py`) and hotspot map
- Weighted severity × recency decay per zone, normalised to 0-100; IDW interpolation (power 2) of zone PM2.5 for the map. Both are transparent formulas, not learned models.
