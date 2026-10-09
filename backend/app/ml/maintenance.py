"""Predictive-maintenance risk score: RandomForest on condition features blended with a transparent rule score."""
from __future__ import annotations
import numpy as np
import pandas as pd
from sklearn.ensemble import RandomForestClassifier

FEATS = ["vib_excess", "temp_excess", "util24", "days_since_service"]


def _snapshots(wide: pd.DataFrame) -> pd.DataFrame:
    out = []
    for ent, g in wide.groupby("entity"):
        g = g.sort_values("ts").copy()
        ref = g.iloc[: 24 * 30]
        g["vib_excess"] = g["vibration_mm_s"] - ref["vibration_mm_s"].median()
        g["temp_excess"] = g["temp_c"] - ref["temp_c"].median()
        g["util24"] = g["util_pct"].rolling(24, min_periods=1).mean()
        g["days_since_service"] = g["days_since_service"].ffill().bfill()
        g["y"] = (g["label"] == "degradation").astype(int)
        out.append(g)
    return pd.concat(out)


def score(wide: pd.DataFrame) -> pd.DataFrame:
    """wide: ts, entity, vibration_mm_s, temp_c, util_pct, days_since_service, label."""
    snaps = _snapshots(wide)
    tr = snaps.dropna(subset=FEATS)
    tr = tr.iloc[::3]
    rf = RandomForestClassifier(n_estimators=120, max_depth=5, class_weight="balanced", random_state=0)
    use_model = tr["y"].sum() >= 5
    if use_model:
        rf.fit(tr[FEATS], tr["y"])
    last = snaps.sort_values("ts").groupby("entity").tail(1).copy()
    last["p_model"] = rf.predict_proba(last[FEATS])[:, 1] if use_model else 0.0
    rule = (np.clip(last["vib_excess"] / 3.0, 0, 1) * 0.5 + np.clip(last["temp_excess"] / 12, 0, 1) * 0.3
            + np.clip((last["days_since_service"] - 120) / 180, 0, 1) * 0.2)
    last["rule"] = rule
    last["risk"] = (0.6 * last["p_model"] + 0.4 * rule) if use_model else rule
    imp = dict(zip(FEATS, rf.feature_importances_)) if use_model else {}
    last.attrs["importance"] = {k: round(float(v), 3) for k, v in imp.items()}
    return last.sort_values("risk", ascending=False)
