"""Safety-incident zone risk ranking (transparent weighted score) and hotspot interpolation (IDW)."""
from __future__ import annotations
import numpy as np
import pandas as pd

SEV_W = {1: 1.0, 2: 2.5, 3: 6.0, 4: 12.0}


def zone_risk(inc: pd.DataFrame, now: pd.Timestamp, zones: list[str]) -> pd.DataFrame:
    rows = []
    for z in zones:
        g = inc[inc["zone"] == z]
        age = (now - g["ts"]).dt.total_seconds() / 86400 if len(g) else pd.Series(dtype=float)
        recency = float(sum(SEV_W[int(s)] * np.exp(-a / 21) for s, a in zip(g["severity"], age)))
        last30 = g[(now - g["ts"]).dt.days < 30] if len(g) else g
        prev30 = g[((now - g["ts"]).dt.days >= 30) & ((now - g["ts"]).dt.days < 60)] if len(g) else g
        rows.append({"zone": z, "incidents_90d": int(len(g)), "incidents_30d": int(len(last30)),
                     "incidents_prev30d": int(len(prev30)), "risk_score": round(recency, 2),
                     "open": int((g["status"] == "open").sum()) if len(g) else 0})
    df = pd.DataFrame(rows)
    mx = max(df["risk_score"].max(), 1e-6)
    df["risk_index"] = (df["risk_score"] / mx * 100).round(0).astype(int)
    return df.sort_values("risk_score", ascending=False)


def idw_grid(points: list[tuple[float, float, float]], n: int = 18, power: float = 2.0) -> dict:
    """Inverse-distance-weighted interpolation of zone values over the facility bounding box."""
    lats, lons, vals = (np.array(x) for x in zip(*points))
    pad_lat, pad_lon = max(np.ptp(lats) * 0.2, 1e-4), max(np.ptp(lons) * 0.2, 1e-4)
    gy = np.linspace(lats.min() - pad_lat, lats.max() + pad_lat, n)
    gx = np.linspace(lons.min() - pad_lon, lons.max() + pad_lon, n)
    grid = np.zeros((n, n))
    for i, la in enumerate(gy):
        for j, lo in enumerate(gx):
            d = np.sqrt((lats - la) ** 2 + (lons - lo) ** 2) + 1e-9
            w = 1 / d ** power
            grid[i, j] = float((w * vals).sum() / w.sum())
    return {"lat_min": float(gy.min()), "lat_max": float(gy.max()), "lon_min": float(gx.min()), "lon_max": float(gx.max()),
            "n": n, "values": np.round(grid, 2).tolist()}
