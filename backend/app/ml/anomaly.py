"""Anomaly detection: robust profile residuals + IsolationForest + flatline (sensor fault) rule.

Each entity is compared with its own typical value for the same hour of day and weekday/weekend. Optional weather
(temperature) adjustment avoids flagging heat-driven energy rises as faults. Evaluated against injected labels.
"""
from __future__ import annotations
import numpy as np
import pandas as pd
from sklearn.ensemble import IsolationForest


def _entity_scores(g: pd.DataFrame, exog: pd.Series | None, baseline: str) -> pd.DataFrame:
    g = g.sort_values("ts").copy()
    v = g["value"].astype(float)
    key = g["ts"].dt.hour * 2 + (g["ts"].dt.dayofweek >= 5).astype(int)
    if baseline == "local":  # slowly drifting signals (e.g. seasonal PM2.5): 7-day rolling median
        prof = v.rolling(168, center=True, min_periods=24).median()
    else:  # same hour of day + weekday/weekend typical level
        prof = v.groupby(key).transform("median")
    floor = max(abs(float(np.median(v))) * 0.1, 1e-6)
    resid = (v - prof) / np.maximum(prof.abs(), floor)  # relative deviation from this hour's typical level
    if exog is not None:
        t = exog.reindex(g["ts"]).values
        ok = ~np.isnan(t)
        if ok.sum() > 48 and np.std(t[ok]) > 0:
            beta = np.polyfit(t[ok] - np.nanmean(t), resid.values[ok], 1)[0]
            resid = resid - beta * (np.nan_to_num(t, nan=np.nanmean(t)) - np.nanmean(t))
    mad = np.median(np.abs(resid - np.median(resid))) * 1.4826
    scale = max(mad, 0.15 if baseline == "local" else 0.06)
    g["z"] = resid / scale
    g["typical"] = prof
    roll_std = v.rolling(4).std()
    span = v.rolling(4).max() - v.rolling(4).min()
    g["flat"] = (span == 0) & (v > 0)
    feats = np.column_stack([g["z"].values, v.diff().fillna(0).values / max(abs(float(np.median(v))), 1e-6), roll_std.fillna(roll_std.median()).values / max(abs(float(np.median(v))), 1e-6)])
    if (g["z"].abs() > 4).any():  # only worth fitting the second opinion when something looks unusual
        iso = IsolationForest(n_estimators=40, max_samples=256, contamination=0.012, random_state=0, n_jobs=1).fit(feats)
        g["iso"] = iso.predict(feats) == -1
    else:
        g["iso"] = False
    raw = (g["z"].abs() > 5.0) | (g["iso"] & (g["z"].abs() > 4.0))
    sustained = raw & (raw.shift(1, fill_value=False) | raw.shift(-1, fill_value=False) | (g["z"].abs() > 8))
    g["flag"] = sustained | g["flat"]
    return g


def detect(df: pd.DataFrame, exog: pd.Series | None = None, baseline: str = "profile") -> pd.DataFrame:
    """df columns: ts, entity, zone, metric, value, label. Returns scored rows incl. `flag` and `reason`."""
    parts = [_entity_scores(g, exog, baseline) for _, g in df.groupby(["entity", "metric"])]
    out = pd.concat(parts, ignore_index=True) if parts else df.assign(flag=False, z=0.0, typical=0.0, flat=False)
    out["reason"] = np.where(out["flat"], "flatline", np.where(out["z"] > 0, "high", "low"))
    return out


def _events(mask: pd.DataFrame, gap_hours: int = 3) -> list[dict]:
    ev = []
    for (ent, met), g in mask.groupby(["entity", "metric"]):
        t = g["ts"].sort_values().values
        if len(t) == 0:
            continue
        start = prev = t[0]
        for x in t[1:]:
            if (x - prev) > np.timedelta64(gap_hours, "h"):
                ev.append({"entity": ent, "metric": met, "start": start, "end": prev}); start = x
            prev = x
        ev.append({"entity": ent, "metric": met, "start": start, "end": prev})
    return ev


def evaluate(scored: pd.DataFrame) -> dict:
    """Event-level precision/recall vs injected labels (consecutive hours = one event)."""
    truth = _events(scored[scored["label"] != ""])
    pred = _events(scored[scored["flag"]])

    def overlap(a, b):
        return a["entity"] == b["entity"] and a["metric"] == b["metric"] and a["start"] <= b["end"] + np.timedelta64(3, "h") and b["start"] <= a["end"] + np.timedelta64(3, "h")
    hit_truth = sum(any(overlap(t, p) for p in pred) for t in truth)
    hit_pred = sum(any(overlap(p, t) for t in truth) for p in pred)
    return {"injected_events": len(truth), "flagged_events": len(pred),
            "recall": round(hit_truth / len(truth), 3) if truth else None,
            "precision": round(hit_pred / len(pred), 3) if pred else None}
