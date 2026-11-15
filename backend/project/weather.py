"""Step 3: daily temperature and wind per zone from Open-Meteo historical archive.

Free for non-commercial use, no API key. Newest data lags ~5 days.
"""
import time

import pandas as pd
import requests

from . import config as C
from .zones import load_zones


def _fetch_range(lat, lon, start, end) -> pd.DataFrame:
    params = {"latitude": lat, "longitude": lon, "start_date": start, "end_date": end,
              "hourly": "temperature_2m,wind_speed_10m", "wind_speed_unit": "kmh",
              "timezone": "Asia/Manila"}
    for attempt in range(5):
        r = requests.get(C.OPEN_METEO_URL, params=params, timeout=60)
        if r.status_code == 429:
            time.sleep(10 * (attempt + 1))
            continue
        r.raise_for_status()
        break
    else:
        raise RuntimeError("Open-Meteo rate limit: try again later")
    h = r.json()["hourly"]
    df = pd.DataFrame({"time": pd.to_datetime(h["time"]),
                       "temp_c": h["temperature_2m"], "wind_kmh": h["wind_speed_10m"]})
    df["date"] = df["time"].dt.normalize()
    g = df.groupby("date").agg(temp_c=("temp_c", "mean"), wind_kmh=("wind_kmh", "mean"),
                               hours=("temp_c", "count"))
    g.loc[g["hours"] < C.MIN_HOURS_PER_DAY, ["temp_c", "wind_kmh"]] = float("nan")
    return g[["temp_c", "wind_kmh"]]


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


def load(zone_id: str) -> pd.DataFrame:
    files = sorted((C.CACHE_DIR / "weather").glob(f"{zone_id}_*.csv"))
    if not files:
        return pd.DataFrame(columns=["temp_c", "wind_kmh"])
    df = pd.concat([pd.read_csv(f, index_col=0, parse_dates=True) for f in files])
    return df[~df.index.duplicated(keep="last")].sort_index()
