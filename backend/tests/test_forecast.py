"""Tests for the forecast step, on synthetic data. Run from backend/: python -m pytest tests"""
import json

import numpy as np
import pandas as pd

from project import config as C
from project import forecast as F

TODAY = pd.Timestamp("2026-11-16")


def _weather(start, end, ramp=False, seed=0):
    idx = pd.date_range(start, end, freq="D")
    rng = np.random.default_rng(seed)
    if ramp:   # temperature equals the day number, so window means are easy to check by hand
        temp = np.arange(len(idx), dtype=float)
    else:
        temp = 28 + 3 * np.sin(2 * np.pi * idx.dayofyear / 365.25) + rng.normal(0, 0.8, len(idx))
    return pd.DataFrame({"temp_c": temp, "wind_kmh": 12 + rng.normal(0, 3, len(idx))}, index=idx)


def _obs(start, n, seed, step=5, mu=0.05, phi=0.8):
    """Mean-reverting NDCI readings about every `step` days (some days skipped like clouds)."""
    rng = np.random.default_rng(seed)
    dates, x, d, vals = [], mu, pd.Timestamp(start), []
    for _ in range(n):
        gap = int(rng.choice([step, step, step, 2 * step]))
        d = d + pd.Timedelta(days=gap)
        x = mu + (x - mu) * phi ** (gap / step) + rng.normal(0, 0.004)
        dates.append(d)
        vals.append(x)
    return pd.Series(vals, index=pd.DatetimeIndex(dates))


def _world(n_zones=6, n_obs=120, end_today=True):
    obs = {f"Z{i}": _obs("2022-01-01", n_obs, seed=i) for i in range(n_zones)}
    last = max(o.index.max() for o in obs.values())
    weather = {z: _weather("2021-12-01", max(last, TODAY) + pd.Timedelta(days=10), seed=i)
               for i, z in enumerate(obs)}
    if end_today:   # make every zone's latest reading recent
        for z in obs:
            obs[z] = obs[z].copy()
            shift = TODAY - pd.Timedelta(days=3) - obs[z].index.max()
            obs[z].index = obs[z].index + shift
            weather[z] = _weather("2021-12-01", TODAY + pd.Timedelta(days=10), seed=1)
    return obs, weather


def _thresholds(obs, weather):
    return {z: {"ndci_p80": float(o.quantile(0.8)), "temp3_p80": float(weather[z]["temp_c"].quantile(0.8)),
                "wind3_p20": float(weather[z]["wind_kmh"].quantile(0.2))} for z, o in obs.items()}


def test_pairs_use_only_the_past_and_the_window_between():
    obs = {"Z": _obs("2022-01-01", 40, seed=1)}
    w = {"Z": _weather("2021-12-01", "2023-06-30", ramp=True)}
    pairs = F.build_pairs(obs, w)
    assert len(pairs) > 50
    first = w["Z"].index[0]
    for _, r in pairs.head(60).iterrows():
        a, b = r["a"], r["b"]
        assert 1 <= (b - a).days <= C.MAX_PAIR_GAP_DAYS
        assert r["ndci"] == obs["Z"].loc[a]
        assert abs(r["y"] - (obs["Z"].loc[b] - obs["Z"].loc[a])) < 1e-12
        da, db = (a - first).days, (b - first).days
        assert abs(r["temp_win"] - (da + 1 + db) / 2) < 1e-9       # mean over days a+1 .. b
        assert abs(r["temp3"] - (da - 1)) < 1e-9                    # mean over days a-2 .. a
        assert r["h"] == (b - a).days


def test_split_never_trains_on_future_readings():
    obs, weather = _world()
    pairs = F.build_pairs(obs, weather)
    train, test, cut = F._split(pairs, 0.8)
    assert train["b"].max() < cut <= test["a"].min()


def test_forecast_shape_and_json_safe():
    obs, weather = _world()
    result = F.run_forecast(obs, weather, _thresholds(obs, weather), TODAY)
    json.dumps(result, allow_nan=False)          # no NaN or numpy types
    assert result["meta"]["horizon_days"] == 5
    for z in obs:
        days = result["zones"][z]["days"]
        assert [d["date"] for d in days] == [(TODAY + pd.Timedelta(days=k)).strftime("%Y-%m-%d") for k in range(1, 6)]
        for d in days:
            assert d["level"] in C.LEVELS
            if d["signals"]:
                assert d["level"] == F.level_of(sum(d["signals"].values()))
                assert d["ndci_low"] <= d["ndci"] <= d["ndci_high"]


def test_model_beats_no_change_on_mean_reverting_data():
    obs, weather = _world(n_zones=8, n_obs=150)
    pairs = F.build_pairs(obs, weather)
    info, production = F.evaluate(pairs, {z: float(o.quantile(0.8)) for z, o in obs.items()})
    assert info["test_mae"] is not None and info["test_mae_persistence"] is not None
    assert info["beats_persistence"] is True
    assert production in ("ridge", "gbm")
    assert info["test_mae"] < info["test_mae_persistence"]


def test_short_history_falls_back_to_no_change():
    obs = {"Z": _obs("2026-09-01", 12, seed=3)}
    weather = {"Z": _weather("2026-08-01", "2026-12-31")}
    result = F.run_forecast(obs, weather, _thresholds(obs, weather), TODAY)
    assert result["meta"]["model"] == "persistence"
    assert "reason" in result["meta"]["validation"]


def test_old_image_gives_no_forecast():
    obs = {"Z": _obs("2025-01-01", 60, seed=4)}
    weather = {"Z": _weather("2024-12-01", "2026-12-31")}
    out = F.run_forecast(obs, weather, _thresholds(obs, weather), TODAY)["zones"]["Z"]
    assert out["days"] == [] and "satellite image" in out["reason"]
