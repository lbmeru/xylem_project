"""Optional read-only API over the JSON files. Run: uvicorn project.api:app --reload

The React app can call this, or skip it and fetch the JSON files in output/ directly.
"""
import json
import os
from datetime import date as date_t
from pathlib import Path

from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware

from . import config as C


class Store:
    """Loads output JSON files, reloading when a file changes on disk."""

    def __init__(self, out_dir: Path, data_dir: Path):
        self.out_dir, self.data_dir = out_dir, data_dir
        self._cache: dict[str, tuple[float, object]] = {}

    def get(self, name: str, base: str = "out"):
        path = (self.out_dir if base == "out" else self.data_dir) / name
        if not path.exists():
            raise HTTPException(503, f"{name} not generated yet. Run the pipeline.")
        mtime = path.stat().st_mtime
        hit = self._cache.get(str(path))
        if not hit or hit[0] != mtime:
            self._cache[str(path)] = (mtime, json.loads(path.read_text()))
        return self._cache[str(path)][1]

    def daily(self):
        d = self.get("daily_risk.json")
        if "_idx" not in d:
            d["_idx"] = {x: i for i, x in enumerate(d["dates"])}
        return d


def create_app(output_dir: Path | None = None, data_dir: Path | None = None) -> FastAPI:
    store = Store(output_dir or C.OUTPUT_DIR, data_dir or C.DATA_DIR)
    app = FastAPI(title="Bantay Lawa API")
    origins = os.getenv("BL_CORS_ORIGINS", "http://localhost:5173,http://localhost:3000").split(",")
    app.add_middleware(CORSMiddleware, allow_origins=origins, allow_methods=["GET"], allow_headers=["*"])

    def resolve(d: date_t | None) -> tuple[dict, int, str]:
        daily = store.daily()
        iso = d.isoformat() if d else daily["dates"][-1]
        if iso not in daily["_idx"]:
            raise HTTPException(404, f"No data for {iso}. Range: {daily['dates'][0]} to {daily['dates'][-1]}")
        return daily, daily["_idx"][iso], iso

    def zone_day(daily: dict, zid: str, i: int, iso: str) -> dict:
        z = daily["zones"].get(zid)
        if z is None:
            raise HTTPException(404, f"Unknown zone {zid}")
        nd = z["ndci_date"][i]
        age = (date_t.fromisoformat(iso) - date_t.fromisoformat(nd)).days if nd else None
        th = daily["meta"]["thresholds"].get(zid)
        return {"date": iso, "level": z["level"][i], "ndci": z["ndci"][i], "ndci_date": nd,
                "ndci_age_days": age, "temp_3d": z["temp_3d"][i], "wind_3d": z["wind_3d"][i],
                "signals": {"algae_high": z["algae_high"][i], "warm": z["warm"][i], "calm": z["calm"][i]},
                "thresholds": th}

    @app.get("/api/health")
    def health():
        return {"ok": True}

    @app.get("/api/meta")
    def meta():
        d = store.daily()
        return {"as_of": d["meta"]["as_of"], "first_date": d["dates"][0], "last_date": d["dates"][-1],
                "rule": d["meta"]["rule"], "levels": C.LEVELS, "generated_at": d["meta"]["generated_at"]}

    @app.get("/api/dates")
    def dates():
        return store.daily()["dates"]

    @app.get("/api/map")
    def map_(date: date_t | None = None):
        """Zones as GeoJSON with that day's level and values: feed straight into Leaflet."""
        daily, i, iso = resolve(date)
        zones = store.get("zones.json")
        feats = []
        for f in zones["features"]:
            zid = f["properties"]["zone_id"]
            feats.append({**f, "properties": {**f["properties"], **zone_day(daily, zid, i, iso)}})
        return {"type": "FeatureCollection", "date": iso, "as_of": daily["meta"]["as_of"], "features": feats}

    @app.get("/api/zones/{zone_id}")
    def zone(zone_id: str, date: date_t | None = None):
        daily, i, iso = resolve(date)
        info = next((f["properties"] for f in store.get("zones.json")["features"]
                     if f["properties"]["zone_id"] == zone_id), None)
        if info is None:
            raise HTTPException(404, f"Unknown zone {zone_id}")
        return {**info, **zone_day(daily, zone_id, i, iso)}

    @app.get("/api/zones/{zone_id}/series")
    def series(zone_id: str, start: date_t | None = Query(None), end: date_t | None = Query(None)):
        """NDCI at actual image dates (not carried forward), daily levels, and this zone's events."""
        daily = store.daily()
        z = daily["zones"].get(zone_id)
        if z is None:
            raise HTTPException(404, f"Unknown zone {zone_id}")
        lo, hi = (start or date_t.min).isoformat(), (end or date_t.max).isoformat()
        obs = [{"date": d, "ndci": n} for d, n, nd in zip(daily["dates"], z["ndci"], z["ndci_date"])
               if nd == d and lo <= d <= hi]
        lv = [{"date": d, "level": l} for d, l in zip(daily["dates"], z["level"]) if lo <= d <= hi]
        try:
            all_events = store.get("events.json")
        except HTTPException:   # events step not run: chart simply has no fish-kill markers
            all_events = []
        ev = [e for e in all_events if e["zone_id"] == zone_id and e.get("date")]
        return {"zone_id": zone_id, "ndci_observations": obs, "levels": lv, "events": ev,
                "ndci_threshold": (daily["meta"]["thresholds"].get(zone_id) or {}).get("ndci_p80")}

    @app.get("/api/events")
    def events():
        return store.get("events.json")

    @app.get("/api/backtest")
    def backtest():
        return store.get("backtest.json")

    @app.get("/api/forecast")
    def forecast():
        """Five-day forecast for every zone, plus how the model did on held-out past dates."""
        return store.get("forecast.json")

    @app.get("/api/response-cards")
    def cards():
        return store.get("response_cards.json", base="data")

    return app


app = create_app()
