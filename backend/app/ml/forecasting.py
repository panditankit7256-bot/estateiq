"""Short-term forecasting: gradient boosting on lag + calendar features (recursive multi-step).

Why not Prophet by default? It is heavy to install; this model needs only scikit-learn, trains in ~1 s, and is
always benchmarked against a seasonal-naive baseline (value 24 h earlier) on a held-out final day.
"""
from __future__ import annotations
import numpy as np
import pandas as pd
from sklearn.ensemble import GradientBoostingRegressor

LAGS = (1, 2, 3, 24, 48, 168)
COLS = [f"lag{l}" for l in LAGS] + ["roll24", "hsin", "hcos", "dow", "weekend"]


def _calendar(idx: pd.DatetimeIndex) -> np.ndarray:
    h = idx.hour.values
    return np.column_stack([np.sin(2 * np.pi * h / 24), np.cos(2 * np.pi * h / 24), idx.dayofweek.values, (idx.dayofweek.values >= 5).astype(float)])


def _train_frame(s: pd.Series):
    X = {f"lag{l}": s.shift(l) for l in LAGS}
    X["roll24"] = s.shift(1).rolling(24).mean()
    df = pd.DataFrame(X)
    cal = _calendar(s.index)
    for i, c in enumerate(["hsin", "hcos", "dow", "weekend"]):
        df[c] = cal[:, i]
    df["y"] = s.values
    return df.dropna()


def _fit(s: pd.Series) -> GradientBoostingRegressor:
    d = _train_frame(s)
    m = GradientBoostingRegressor(n_estimators=140, max_depth=3, learning_rate=0.08, subsample=0.9, random_state=0)
    m.fit(d[COLS], d["y"])
    return m


def _recursive(model, history: pd.Series, steps: int) -> pd.Series:
    hist = list(history.values)
    idx = pd.date_range(history.index[-1] + pd.Timedelta(hours=1), periods=steps, freq="h")
    cal = _calendar(idx)
    out = []
    for i in range(steps):
        row = [hist[-l] for l in LAGS] + [np.mean(hist[-24:])] + list(cal[i])
        yhat = float(model.predict(pd.DataFrame([row], columns=COLS))[0])
        out.append(yhat); hist.append(yhat)
    return pd.Series(out, index=idx)


def forecast(series: pd.Series, horizon: int = 24, holdout: int = 24, unit: str = "") -> dict:
    """Return forecast, 95% interval, and honest accuracy metrics vs a seasonal-naive baseline."""
    s = series.asfreq("h").interpolate(limit=6).dropna()
    if len(s) < 24 * 10:
        raise ValueError("Need at least 10 days of hourly data to forecast")
    train, test = s.iloc[:-holdout], s.iloc[-holdout:]
    m_eval = _fit(train)
    pred = _recursive(m_eval, train, holdout)
    base = s.shift(24).iloc[-holdout:]
    err = test.values - pred.values
    mae, rmse = float(np.mean(np.abs(err))), float(np.sqrt(np.mean(err ** 2)))
    mape = float(np.mean(np.abs(err) / np.clip(np.abs(test.values), 1e-6, None)) * 100)
    base_mae = float(np.mean(np.abs(test.values - base.values)))
    model = _fit(s)
    fut = _recursive(model, s, horizon)
    resid = []
    d = _train_frame(s.iloc[-24 * 14:])
    if len(d):
        resid = d["y"].values - model.predict(d.drop(columns="y")[COLS])
    sigma = float(np.std(resid)) if len(resid) else rmse
    sigma = max(sigma, rmse * 0.7)
    steps = np.arange(1, horizon + 1)
    width = 1.96 * sigma * np.sqrt(1 + 0.12 * steps)
    return {
        "history_ts": [t.isoformat() for t in s.index[-72:]], "history": [round(float(v), 3) for v in s.values[-72:]],
        "ts": [t.isoformat() for t in fut.index], "yhat": [round(float(v), 3) for v in fut.values],
        "lo": [round(float(max(v - w, 0)), 3) for v, w in zip(fut.values, width)],
        "hi": [round(float(v + w), 3) for v, w in zip(fut.values, width)],
        "metrics": {"mae": round(mae, 3), "rmse": round(rmse, 3), "mape_pct": round(mape, 2), "baseline_mae": round(base_mae, 3),
                    "improvement_vs_baseline_pct": round((base_mae - mae) / base_mae * 100, 1) if base_mae else 0.0,
                    "holdout_hours": holdout, "unit": unit},
        "assumptions": ["Model: gradient boosting on lagged values and calendar features, forecast recursively.",
                        "Interval is an approximate 95% band from recent residuals; it widens with horizon and is not guaranteed.",
                        "Accuracy is measured on the last 24 h held out from training; weather/events outside history are not modelled.",
                        "Data in this prototype is synthetic. Treat output as decision support, not an official measurement."],
    }
