# 5-minute demo script
Setup: `docker compose up --build`, open http://localhost:3000, sign in as **admin**.

1. **(0:00) The problem and the facility.** "A campus administrator needs one place to see air, energy, water, waste, parking, equipment and safety, and know what to do next." Show the Command centre: KPIs and the site plan (rings = status, numbers = PM2.5).
2. **(0:45) Actions, not charts.** Point at *Top actions*: leak in Hostels, worn pump, bins. Expand "Data and assumptions behind this" on one card to show owner, impact in ₹/kL/kg CO2, confidence.
3. **(1:30) Live incident.** Click **Pollution episode** (or **Water leak**). The banner appears, alerts and recommendations refresh without reloading. "Detection is event-level; here is how reliable it is" → open *Air quality* → "How reliable is detection?".
4. **(2:15) Forecast you can trust.** Energy page: toggle 24 h / 7 days; read the accuracy sentence ("21% better than same-as-yesterday").
5. **(3:00) Waste route.** Waste page: show suggested order and km saved.
6. **(3:30) What if.** Scenarios: add 200 kW solar, +2 °C AC setpoint, shift 20% of peak load. Read the monthly savings and the assumptions list.
7. **(4:15) Adapt and respect roles.** Switch facility to *Government hospital* (24x7 load, biomedical bins, higher water benchmark). Sign out and sign in as **ops** to show the reduced menu and task-focused actions.
8. **(4:45) Honesty slide.** Settings → Assumptions: synthetic data, editable factors, decision-support wording. Close with the audit trail.

Backup if a step is slow: the first load of a facility computes models (a few seconds); later loads are cached.
