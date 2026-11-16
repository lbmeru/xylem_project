"""Step 7: five-day forecast -> forecast.json.

For every zone it predicts the NDCI on each of the next 5 days, then applies the same
Low/Watch/High rule (see levels.py) to the predicted NDCI and the forecast weather.

How the model is built and checked. It uses past satellite and weather data only, never
fish-kill events:
  * Training pairs: two clear readings of the same zone at most 15 days apart. Features are
    what was known at the first reading plus the weather between the two dates. The target
    is the change in NDCI between them.
  * Candidates: "persistence" (no change), ridge regression, gradient boosting.
  * Time split: the last 20% of dates are held out as a test set. The candidate is picked on a
    validation slice cut from the end of the training part. Pairs whose second reading falls
    after a cut are dropped from the part before it, so nothing from the future leaks in.
  * If the picked model does not beat "no change" on the held-out dates, the forecast keeps
    NDCI as it is and only the weather signals move.
  * The test numbers are saved in forecast.json (meta.validation) and shown in the app.

Weather for the coming days comes from the Open-Meteo forecast. Training used archived
weather, so some mismatch is expected.
"""
import json
from datetime import datetime, timezone

import numpy as np
import pandas as pd
from sklearn.ensemble import HistGradientBoostingRegressor
from sklearn.linear_model import Ridge
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import StandardScaler

from . import config as C

FEATURES = ["ndci", "prev_delta", "prev_gap", "anom", "h", "temp_win", "wind_win",
            "temp3", "wind3", "doy_sin", "doy_cos"]
DAY = pd.Timedelta(days=1)
DATE_FMT = "%Y-%m-%d"


def _num(x, nd: int = 3):
    x = float(x)
    return round(x, nd) if np.isfinite(x) else None


def _window_mean(w: pd.DataFrame, start, end, col: str) -> float:
    s = w[col].loc[start:end]
    return float(s.mean()) if s.notna().any() else float("nan")


def level_of(n_yes: int) -> str:
    return "High" if n_yes >= 3 else "Watch" if n_yes == 2 else "Low"


# ------------------------------------------------------------------ features
def make_features(obs: pd.Series, cmean: np.ndarray, i: int, target, w: pd.DataFrame) -> dict | None:
    """Features for predicting NDCI on `target` from the reading at position i.

    Uses only readings up to and including i, weather up to i (temp3, wind3) and the weather
    between i and the target (temp_win, wind_win). Returns None if anything is missing.
    """
    if i + 1 < C.MIN_HISTORY_OBS:
        return None
    a = obs.index[i]
    target = pd.Timestamp(target)
    h = (target - a).days
    if h < 1:
        return None
    ndci = float(obs.iloc[i])
    doy = target.dayofyear / 365.25 * 2 * np.pi
    f = {
        "ndci": ndci,
        "prev_delta": ndci - float(obs.iloc[i - 1]),
        "prev_gap": float((a - obs.index[i - 1]).days),
        "anom": ndci - float(cmean[i]),
        "h": float(h),
        "temp_win": _window_mean(w, a + DAY, target, "temp_c"),
        "wind_win": _window_mean(w, a + DAY, target, "wind_kmh"),
        "temp3": _window_mean(w, a - 2 * DAY, a, "temp_c"),
        "wind3": _window_mean(w, a - 2 * DAY, a, "wind_kmh"),
        "doy_sin": float(np.sin(doy)),
        "doy_cos": float(np.cos(doy)),
    }
    return None if any(np.isnan(v) for v in f.values()) else f


def build_pairs(obs_by_zone: dict, weather_by_zone: dict) -> pd.DataFrame:
    rows = []
    for zid, obs in obs_by_zone.items():
        obs = obs.sort_index()
        w = weather_by_zone.get(zid)
        if len(obs) < C.MIN_HISTORY_OBS + 1 or w is None or w.empty:
            continue
        cmean = obs.expanding().mean().to_numpy()
        idx = obs.index
        for i in range(C.MIN_HISTORY_OBS - 1, len(obs) - 1):
            for j in range(i + 1, len(obs)):
                if (idx[j] - idx[i]).days > C.MAX_PAIR_GAP_DAYS:
                    break
                f = make_features(obs, cmean, i, idx[j], w)
                if f is None:
                    continue
                rows.append({**f, "zone_id": zid, "a": idx[i], "b": idx[j],
                             "y": float(obs.iloc[j] - obs.iloc[i])})
    return pd.DataFrame(rows)


# ------------------------------------------------------------------ models
def _candidates() -> dict:
    return {
        "persistence": None,
        "ridge": make_pipeline(StandardScaler(), Ridge(alpha=10.0)),
        "gbm": HistGradientBoostingRegressor(max_depth=3, learning_rate=0.05, max_iter=250,
                                             l2_regularization=1.0, min_samples_leaf=30,
                                             random_state=0),
    }


def _fit(name: str, X, y):
    if name == "persistence":
        return None
    model = _candidates()[name]
    model.fit(X, y)
    return model


def _predict(model, X) -> np.ndarray:
    return np.zeros(len(X)) if model is None else np.asarray(model.predict(X), dtype=float)


def _split(pairs: pd.DataFrame, frac: float):
    """Time split. Train pairs end before the cut, test pairs start at or after it."""
    cut = pairs["a"].sort_values().iloc[int(len(pairs) * frac)]
    return pairs[pairs["b"] < cut], pairs[pairs["a"] >= cut], cut


def _pick(train: pd.DataFrame) -> tuple[str, dict]:
    tr, va, _ = _split(train, 0.85)
    if len(tr) < C.MIN_PAIRS // 2 or len(va) < 30:
        return "persistence", {}
    maes = {}
    for name in _candidates():
        model = _fit(name, tr[FEATURES], tr["y"])
        maes[name] = float(np.mean(np.abs(va["y"].to_numpy() - _predict(model, va[FEATURES]))))
    return min(maes, key=maes.get), maes   # persistence wins ties


def _signal_counts(actual: pd.Series, predicted: pd.Series) -> dict:
    return {"true_yes": int((actual & predicted).sum()), "false_yes": int((~actual & predicted).sum()),
            "missed_yes": int((actual & ~predicted).sum()), "true_no": int((~actual & ~predicted).sum())}


def evaluate(pairs: pd.DataFrame, ndci_cut: dict) -> tuple[dict, str]:
    """Returns (validation info, name of the model to use in production)."""
    info = {"n_pairs": int(len(pairs)), "residual_q10": 0.0, "residual_q90": 0.0}
    if len(pairs) < C.MIN_PAIRS:
        return {**info, "chosen": "persistence", "production": "persistence",
                "reason": "Not enough history to train a model."}, "persistence"
    train, test, cut = _split(pairs, 0.8)
    if len(train) < C.MIN_PAIRS // 2 or len(test) < 50:
        return {**info, "chosen": "persistence", "production": "persistence",
                "reason": "Not enough history to hold out a test set."}, "persistence"

    chosen, val_mae = _pick(train)
    model = _fit(chosen, train[FEATURES], train["y"])
    y = test["y"].to_numpy()
    pred = _predict(model, test[FEATURES])
    mae, mae_persist = float(np.mean(np.abs(y - pred))), float(np.mean(np.abs(y)))
    beats = chosen != "persistence" and mae < mae_persist
    production = chosen if beats else "persistence"
    resid = (y - pred) if beats else y   # actual minus predicted, for the model actually used

    th = test["zone_id"].map(ndci_cut)
    ok = th.notna().to_numpy()
    algae = None
    if ok.any():
        thv = th[ok]
        base = test["ndci"][ok]
        actual = (base + test["y"][ok]) >= thv
        algae = {"model": _signal_counts(actual, (base + pd.Series(pred, index=test.index)[ok]) >= thv),
                 "persistence": _signal_counts(actual, base >= thv)}

    return {**info, "chosen": chosen, "production": production,
            "validation_mae": {k: _num(v, 4) for k, v in val_mae.items()},
            "n_train": int(len(train)), "n_test": int(len(test)),
            "test_from": cut.strftime(DATE_FMT),
            "test_mae": _num(mae, 4), "test_mae_persistence": _num(mae_persist, 4),
            "beats_persistence": bool(beats),
            "residual_q10": _num(np.quantile(resid, 0.10), 4), "residual_q90": _num(np.quantile(resid, 0.90), 4),
            "algae_high": algae}, production


# ------------------------------------------------------------------ forecast
def forecast_zone(obs: pd.Series, w: pd.DataFrame, th: dict | None, model, today: pd.Timestamp,
                  q_lo: float, q_hi: float) -> dict:
    obs = obs.sort_index()
    if len(obs) < C.MIN_HISTORY_OBS or w is None or w.empty:
        return {"base_date": None, "days": [], "reason": "Not enough satellite or weather history for this zone."}
    base = obs.index[-1]
    base_s = base.strftime(DATE_FMT)
    if (today - base).days > C.MAX_IMAGE_AGE_DAYS:
        return {"base_date": base_s, "days": [],
                "reason": f"No clear satellite image in the last {C.MAX_IMAGE_AGE_DAYS} days."}
    if not th:
        return {"base_date": base_s, "days": [], "reason": "Not enough images to set cutoffs for this zone."}

    cmean = obs.expanding().mean().to_numpy()
    i = len(obs) - 1
    days = []
    for k in range(1, C.FORECAST_DAYS + 1):
        target = today + k * DAY
        entry = {"date": target.strftime(DATE_FMT), "h": int((target - base).days)}
        f = make_features(obs, cmean, i, target, w)
        temp3 = _window_mean(w, target - 2 * DAY, target, "temp_c")
        wind3 = _window_mean(w, target - 2 * DAY, target, "wind_kmh")
        if f is None or np.isnan(temp3) or np.isnan(wind3):
            days.append({**entry, "ndci": None, "ndci_low": None, "ndci_high": None, "temp_3d": None,
                         "wind_3d": None, "signals": None, "level": "Unknown"})
            continue
        delta = 0.0 if model is None else float(model.predict(pd.DataFrame([f])[FEATURES])[0])
        nd = f["ndci"] + delta
        s = {"algae_high": int(nd >= th["ndci_p80"]), "warm": int(temp3 >= th["temp3_p80"]),
             "calm": int(wind3 <= th["wind3_p20"])}
        days.append({**entry, "ndci": _num(nd), "ndci_low": _num(nd + q_lo), "ndci_high": _num(nd + q_hi),
                     "temp_3d": _num(temp3, 2), "wind_3d": _num(wind3, 1), "signals": s,
                     "level": level_of(sum(s.values()))})
    return {"base_date": base_s, "base_ndci": _num(obs.iloc[-1]), "days": days}


def run_forecast(obs_by_zone: dict, weather_by_zone: dict, thresholds: dict, today: pd.Timestamp) -> dict:
    ndci_cut = {z: (t or {}).get("ndci_p80") for z, t in thresholds.items()}
    pairs = build_pairs(obs_by_zone, weather_by_zone)
    info, production = evaluate(pairs, ndci_cut)
    model = None if production == "persistence" else _fit(production, pairs[FEATURES], pairs["y"])
    zones = {z: forecast_zone(obs, weather_by_zone.get(z), thresholds.get(z), model, today,
                              info["residual_q10"], info["residual_q90"])
             for z, obs in obs_by_zone.items()}
    return {"meta": {"generated_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
                     "issued": today.strftime(DATE_FMT), "horizon_days": C.FORECAST_DAYS,
                     "model": production, "validation": info},
            "zones": zones}


def run() -> None:
    from . import weather as W
    from .ndci import build_daily
    from .zones import load_zones

    daily = json.loads((C.OUTPUT_DIR / "daily_risk.json").read_text(encoding="utf-8"))
    zone_ids = [f["properties"]["zone_id"] for f in load_zones()["features"]]
    W.fetch_forecast()
    nd = build_daily()
    nd = nd[nd["valid_fraction"] >= C.MIN_VALID_FRACTION]
    obs = {z: nd[nd["zone_id"] == z].set_index("date")["ndci"].sort_index() for z in zone_ids}
    weather = {z: W.load(z).combine_first(W.load_forecast(z)) for z in zone_ids}
    result = run_forecast(obs, weather, daily["meta"]["thresholds"], pd.Timestamp.today().normalize())
    (C.OUTPUT_DIR / "forecast.json").write_text(json.dumps(result, separators=(",", ":"), allow_nan=False), encoding="utf-8")
    v = result["meta"]["validation"]
    print(f"forecast.json: {len(zone_ids)} zones, model: {result['meta']['model']}")
    if "test_mae" in v:
        print(f"  held-out NDCI error {v['test_mae']} vs {v['test_mae_persistence']} for 'no change' "
              f"({v['n_test']} test pairs from {v['test_from']})")
    else:
        print(f"  {v.get('reason')}")
