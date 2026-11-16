"""Step 4: apply the risk rule -> daily_risk.json.

Rule (per zone, per day), each signal yes/no:
  algae_high : NDCI >= zone's own 80th percentile (latest clear image, at most 10 days old)
  warm       : 3-day mean air temp >= zone's own 80th percentile
  calm       : 3-day mean wind speed <= zone's own 20th percentile
0 or 1 yes = Low, 2 = Watch, 3 = High. Missing NDCI (no clear image in 10 days) or missing
weather = Unknown.

This module never reads fish-kill events, by design: cutoffs are fixed before any
event is looked at.

daily_risk.json is columnar to keep the file small:
  {"meta": {...}, "dates": [...], "zones": {zone_id: {"ndci": [...], "ndci_date": [...],
   "temp_3d": [...], "wind_3d": [...], "algae_high": [...], "warm": [...], "calm": [...],
   "level": [...]}}}
Every list lines up with "dates". Missing values are null.
"""
import json
from datetime import datetime, timezone

import numpy as np
import pandas as pd

from . import config as C
from . import weather as W
from .ndci import build_daily
from .zones import load_zones

SIGNALS = ["algae_high", "warm", "calm"]


def compute_zone(obs: pd.Series, weather: pd.DataFrame, dates: pd.DatetimeIndex):
    """obs: clear NDCI by image date. weather: daily temp_c, wind_kmh. Returns (frame, thresholds)."""
    w = weather.reindex(dates)
    temp3 = w["temp_c"].rolling(C.ROLL_DAYS, min_periods=C.ROLL_DAYS).mean()
    wind3 = w["wind_kmh"].rolling(C.ROLL_DAYS, min_periods=C.ROLL_DAYS).mean()

    on_day = obs.reindex(dates)
    obs_date = pd.Series(dates.where(on_day.notna().to_numpy()), index=dates)
    ndci = on_day.ffill(limit=C.MAX_IMAGE_AGE_DAYS)          # carry the latest image forward
    ndci_date = obs_date.ffill(limit=C.MAX_IMAGE_AGE_DAYS)   # ...and remember which image it was

    out = pd.DataFrame({"ndci": ndci, "ndci_date": ndci_date,
                        "temp_3d": temp3, "wind_3d": wind3}, index=dates)

    enough = len(obs) >= C.MIN_NDCI_OBS and temp3.notna().any() and wind3.notna().any()
    if not enough:
        for s in SIGNALS:
            out[s] = np.nan
        out["level"] = "Unknown"
        return out, None

    th = {"ndci_p80": float(obs.quantile(C.TOP_Q)),
          "temp3_p80": float(temp3.dropna().quantile(C.TOP_Q)),
          "wind3_p20": float(wind3.dropna().quantile(C.BOTTOM_Q)),
          "n_ndci_obs": int(len(obs))}
    known = ndci.notna() & temp3.notna() & wind3.notna()
    a, b, c = ndci >= th["ndci_p80"], temp3 >= th["temp3_p80"], wind3 <= th["wind3_p20"]
    n = a.astype(int) + b.astype(int) + c.astype(int)
    for name, sig in zip(SIGNALS, (a, b, c)):
        out[name] = sig.astype(float).where(known)
    out["level"] = np.where(~known, "Unknown", np.where(n >= 3, "High", np.where(n == 2, "Watch", "Low")))
    return out, th


def _col(s: pd.Series, nd: int | None = None) -> list:
    if pd.api.types.is_datetime64_any_dtype(s):
        return [None if pd.isna(v) else v.strftime("%Y-%m-%d") for v in s]
    if s.dtype == object:
        return list(s)
    return [None if pd.isna(v) else (round(float(v), nd) if nd is not None else int(v)) for v in s]


def build(ndci_daily: pd.DataFrame, weather_by_zone: dict, zone_ids: list[str]) -> dict:
    ndci_daily = ndci_daily[ndci_daily["valid_fraction"] >= C.MIN_VALID_FRACTION]
    last_weather = [w["temp_c"].dropna().index.max() for w in weather_by_zone.values()
                    if w["temp_c"].notna().any()]
    if not last_weather:
        raise SystemExit("No weather data cached. Run the `weather` step first.")
    end = min(last_weather)
    dates = pd.date_range(C.START_DATE, end, freq="D")

    zones_out, thresholds, last_image = {}, {}, {}
    for zid in zone_ids:
        obs = (ndci_daily[ndci_daily["zone_id"] == zid].set_index("date")["ndci"]
               .sort_index())
        frame, th = compute_zone(obs, weather_by_zone.get(zid, pd.DataFrame(columns=["temp_c", "wind_kmh"])), dates)
        thresholds[zid] = th
        last_image[zid] = obs.index.max().strftime("%Y-%m-%d") if len(obs) else None
        zones_out[zid] = {"ndci": _col(frame["ndci"], 3), "ndci_date": _col(frame["ndci_date"]),
                          "temp_3d": _col(frame["temp_3d"], 2), "wind_3d": _col(frame["wind_3d"], 1),
                          **{s: _col(frame[s]) for s in SIGNALS}, "level": list(frame["level"])}
    return {
        "meta": {
            "generated_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
            "as_of": end.strftime("%Y-%m-%d"),
            "baseline_start": C.START_DATE,
            "rule": {"top_quantile": C.TOP_Q, "bottom_quantile": C.BOTTOM_Q,
                     "rolling_days": C.ROLL_DAYS, "max_image_age_days": C.MAX_IMAGE_AGE_DAYS,
                     "min_valid_fraction": C.MIN_VALID_FRACTION},
            "thresholds": thresholds,
            "last_image": last_image,
        },
        "dates": [d.strftime("%Y-%m-%d") for d in dates],
        "zones": zones_out,
    }


def run() -> None:
    zone_ids = [f["properties"]["zone_id"] for f in load_zones()["features"]]
    weather = {z: W.load(z) for z in zone_ids}
    result = build(build_daily(), weather, zone_ids)
    (C.OUTPUT_DIR / "daily_risk.json").write_text(json.dumps(result, separators=(",", ":")), encoding="utf-8")
    print(f"daily_risk.json: {len(zone_ids)} zones x {len(result['dates'])} days, as of {result['meta']['as_of']}")
