"""Waste-bin overflow prediction and collection-route optimisation."""
from __future__ import annotations
import math
import numpy as np
import pandas as pd
from sklearn.ensemble import GradientBoostingClassifier


def haversine(a: tuple[float, float], b: tuple[float, float]) -> float:
    R = 6371.0
    p1, p2 = math.radians(a[0]), math.radians(b[0])
    dphi, dl = p2 - p1, math.radians(b[1] - a[1])
    x = math.sin(dphi / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2
    return 2 * R * math.asin(math.sqrt(x))


def route_length(depot, stops: list[dict]) -> float:
    pts = [depot] + [(s["lat"], s["lon"]) for s in stops] + [depot]
    return sum(haversine(pts[i], pts[i + 1]) for i in range(len(pts) - 1))


def optimise_route(depot, stops: list[dict]) -> list[dict]:
    """Nearest-neighbour tour improved with 2-opt."""
    if len(stops) < 3:
        return list(stops)
    left, cur, order = list(stops), depot, []
    while left:
        nxt = min(left, key=lambda s: haversine(cur, (s["lat"], s["lon"])))
        order.append(nxt); left.remove(nxt); cur = (nxt["lat"], nxt["lon"])
    improved = True
    while improved:
        improved = False
        for i in range(len(order) - 1):
            for j in range(i + 1, len(order)):
                cand = order[:i] + order[i:j + 1][::-1] + order[j + 1:]
                if route_length(depot, cand) + 1e-9 < route_length(depot, order):
                    order, improved = cand, True
    return order


def _features(g: pd.DataFrame) -> pd.DataFrame:
    g = g.sort_values("ts").copy()
    g["rate6"] = g["value"].diff().clip(lower=0).rolling(6, min_periods=2).mean().fillna(0)
    resets = (g["value"].diff() < -20).cumsum()
    g["since_collect"] = g.groupby(resets).cumcount()
    g["hour"] = g["ts"].dt.hour
    fut_max = g["value"][::-1].rolling(6, min_periods=1).max()[::-1].shift(-1)
    g["y"] = (fut_max >= 90).astype(float)
    return g


def train_and_score(df: pd.DataFrame) -> pd.DataFrame:
    """df: ts, entity, value (fill %). Returns latest status per bin incl. overflow probability (next 6 h)."""
    frames = [_features(g) for _, g in df.groupby("entity")]
    full = pd.concat(frames)
    cols = ["value", "rate6", "since_collect", "hour"]
    train = full.dropna(subset=["y"])
    clf = GradientBoostingClassifier(n_estimators=50, max_depth=3, random_state=0)
    if train["y"].nunique() > 1:
        clf.fit(train[cols], train["y"])
        prob = lambda X: clf.predict_proba(X)[:, 1]
    else:
        prob = lambda X: np.zeros(len(X))
    last = full.sort_values("ts").groupby("entity").tail(1).copy()
    last["p_overflow_6h"] = prob(last[cols])
    last["hours_to_90"] = np.where(last["value"] >= 90, 0.0, (90 - last["value"]) / np.clip(last["rate6"], 0.2, None))
    return last[["entity", "value", "rate6", "p_overflow_6h", "hours_to_90"]].reset_index(drop=True)
