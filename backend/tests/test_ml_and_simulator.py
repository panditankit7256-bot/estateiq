import yaml, numpy as np, pandas as pd
from datetime import datetime
from pathlib import Path
from app.simulator.generator import generate
from app.ml import forecasting, anomaly, waste

CFG = yaml.safe_load((Path(__file__).parents[2] / "config/facilities/engineering_college.yaml").read_text())
END = datetime(2026, 10, 9, 14)
R, INC = generate(CFG, END, 90)


def test_simulator_shape_and_labels():
    assert set(R["module"]) >= {"air", "energy", "water", "waste", "traffic", "assets", "weather"}
    assert R["ts"].max() == pd.Timestamp(END).floor("h") and R["value"].notna().all()
    assert {"leak", "pollution_episode", "energy_spike", "sensor_fault", "bin_overflow", "degradation"} <= set(R["label"])
    assert (R[R.metric == "fill_pct"].value.between(0, 100)).all()
    assert len(INC) > 10


def test_every_facility_config_generates():
    for p in (Path(__file__).parents[2] / "config/facilities").glob("*.yaml"):
        cfg = yaml.safe_load(p.read_text())
        r, _ = generate(cfg, END, 20)
        assert len(r) > 10000 and r["value"].notna().all(), p.name


def test_forecast_beats_seasonal_naive_on_energy():
    s = R[(R.module == "energy") & (R.metric == "kwh")].groupby("ts").value.sum()
    f = forecasting.forecast(s, 24)
    assert len(f["yhat"]) == 24 and all(l <= y <= h for l, y, h in zip(f["lo"], f["yhat"], f["hi"]))
    assert f["metrics"]["mape_pct"] < 10
    assert f["metrics"]["improvement_vs_baseline_pct"] > 0


def test_anomaly_detection_finds_injected_energy_faults():
    d = R[(R.module == "energy") & (R.metric == "kwh")]
    temp = R[(R.module == "weather") & (R.metric == "temp_c")].set_index("ts").value
    ev = anomaly.evaluate(anomaly.detect(d, temp))
    assert ev["recall"] >= 0.75 and ev["precision"] >= 0.5


def test_flatline_sensor_is_flagged():
    d = R[(R.module == "air") & (R.metric == "pm25") & (R.entity == "aq-park")]
    sc = anomaly.detect(d, None, "local")
    assert sc[sc.label == "sensor_fault"].flag.any()


def test_route_optimiser_never_longer_than_input_order():
    rng = np.random.default_rng(1)
    stops = [{"id": i, "lat": 20.29 + rng.random() * 0.01, "lon": 85.82 + rng.random() * 0.01} for i in range(9)]
    depot = (20.29, 85.82)
    assert waste.route_length(depot, waste.optimise_route(depot, stops)) <= waste.route_length(depot, stops) + 1e-9
