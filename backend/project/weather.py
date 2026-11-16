"""Step 3: daily temperature and wind per zone from Open-Meteo.

Free for non-commercial use, no API key.
  fetch():          historical archive (newest data lags ~5 days), used for the risk rule and training.
  fetch_forecast(): the last two weeks plus the next week from the forecast API, used by the forecast step.
"""
import time

import pandas as pd
import requests

from . import config as C
from .zones import load_zones


def _get_json(url: str, params: dict) -> dict:
    for attempt in range(5):
        r = requests.get(url, params=params, timeout=60)
        if r.status_code == 429:
            time.sleep(10 * (attempt + 1))
            continue
        r.raise_for_status()
        return r.json()
    raise RuntimeError("Open-Meteo rate limit: try again later")


def _daily_from_hourly(h: dict) -> pd.DataFrame:
    df = pd.DataFrame({"time": pd.to_datetime(h["time"]),
                       "temp_c": h["temperature_2m"], "wind_kmh": h["wind_speed_10m"]})
    df["date"] = df["time"].dt.normalize()
    g = df.groupby("date").agg(temp_c=("temp_c", "mean"), wind_kmh=("wind_kmh", "mean"),
                               hours=("temp_c", "count"))
    g.loc[g["hours"] < C.MIN_HOURS_PER_DAY, ["temp_c", "wind_kmh"]] = float("nan")
    return g[["temp_c", "wind_kmh"]]


def _fetch_range(lat, lon, start, end) -> pd.DataFrame:
    params = {"latitude": lat, "longitude": lon, "start_date": start, "end_date": end,
              "hourly": "temperature_2m,wind_speed_10m", "wind_speed_unit": "kmh",
              "timezone": "Asia/Manila"}
    return _daily_from_hourly(_get_json(C.OPEN_METEO_URL, params)["hourly"])


def fetch(end: pd.Timestamp | None = None) -> None:
    end = end or (pd.Timestamp.today().normalize() - pd.Timedelta(days=C.WEATHER_LAG_DAYS))
    out = C.CACHE_DIR / "weather"
    out.mkdir(parents=True, exist_ok=True)
    zones = load_zones()["features"]
    for i, f in enumerate(zones, 1):
        p = f["properties"]
        print(f"weather {i}/{len(zones)} {p['zone_id']}")
        for year in range(pd.Timestamp(C.START_DATE).year, end.year + 1):
            path = out / f"{p['zone_id']}_{year}.csv"
            if path.exists() and year < end.year:
                continue
            s = max(pd.Timestamp(C.START_DATE), pd.Timestamp(year=year, month=1, day=1))
            e = min(end, pd.Timestamp(year=year, month=12, day=31))
            _fetch_range(p["centroid_lat"], p["centroid_lon"],
                         s.strftime("%Y-%m-%d"), e.strftime("%Y-%m-%d")).to_csv(path)
            time.sleep(0.3)


def fetch_forecast() -> None:
    """Recent past days and the coming week per zone. Overwritten on every run."""
    out = C.CACHE_DIR / "weather_forecast"
    out.mkdir(parents=True, exist_ok=True)
    zones = load_zones()["features"]
    for i, f in enumerate(zones, 1):
        p = f["properties"]
        print(f"weather forecast {i}/{len(zones)} {p['zone_id']}")
        params = {"latitude": p["centroid_lat"], "longitude": p["centroid_lon"],
                  "hourly": "temperature_2m,wind_speed_10m", "wind_speed_unit": "kmh",
                  "timezone": "Asia/Manila", "past_days": C.FORECAST_PAST_DAYS,
                  "forecast_days": C.FORECAST_DAYS + 2}
        _daily_from_hourly(_get_json(C.FORECAST_URL, params)["hourly"]).to_csv(out / f"{p['zone_id']}.csv")
        time.sleep(0.3)


def load(zone_id: str) -> pd.DataFrame:
    files = sorted((C.CACHE_DIR / "weather").glob(f"{zone_id}_*.csv"))
    if not files:
        return pd.DataFrame(columns=["temp_c", "wind_kmh"])
    df = pd.concat([pd.read_csv(f, index_col=0, parse_dates=True) for f in files])
    return df[~df.index.duplicated(keep="last")].sort_index()


def load_forecast(zone_id: str) -> pd.DataFrame:
    path = C.CACHE_DIR / "weather_forecast" / f"{zone_id}.csv"
    if not path.exists():
        return pd.DataFrame(columns=["temp_c", "wind_kmh"])
    return pd.read_csv(path, index_col=0, parse_dates=True).sort_index()
