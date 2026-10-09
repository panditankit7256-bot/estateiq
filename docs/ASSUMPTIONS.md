# Assumptions and limitations
Everything here is shown in the app under Settings and beside each result. Replace placeholders before real use.

## Data
- All readings are **synthetic**, generated with seeded randomness so demos are repeatable. They imitate Indian conditions but are not measurements of any real site.
- Times are local (IST) and the data ends at the moment of seeding; "now" in the app means the latest reading.

## Factors you should replace
| Item | Placeholder | Where |
|---|---|---|
| Grid emission factor | 0.71 kg CO2/kWh | `config/facilities/*.yaml` → `emission`, editable in Settings |
| Diesel generator | 0.82 kg CO2/kWh | same |
| Tariff | ₹6-10/kWh peak/off-peak examples, peak 18:00-22:00 | `tariff` |
| Water cost | ₹18/kL | `GRID_ASSUMPTIONS` in `analytics.py` |
| Solar yield | 4.2 kWh per kW per day | same |
| Cooling share and AC saving | 45% of HVAC-zone load; 6% per °C setpoint | same |
| Rainwater | 1450 mm/year, roof = 30% of built area, 0.8 runoff | same |
| Commute (Scope 3) | 9 km per trip, 0.14 kg CO2/km | same, indicative only |
| PM2.5 categories | CPCB bands (30/60/90/120/250) | `AQI_BANDS` |

## Models
- Forecasts learn from recent history only. They do not know holidays, events, weather forecasts or equipment changes. Ranges are approximate (residual based), not guaranteed intervals.
- Anomaly detection compares a sensor with its own typical level for that hour; it needs a few weeks of history and will flag genuine but harmless changes (for example a new class schedule).
- Maintenance risk and bin-overflow models were trained on **synthetic labels**; real accuracy needs validation on your own failure and overflow logs.
- Scenario results use closed-form estimates with the constants above; they are for planning, not guarantees.

## Health and environment wording
Air-quality text is indicative advice for sensitive groups and is not an official AQI or medical guidance. Heat and waterlogging indicators are screening aids, not engineering risk assessments.
