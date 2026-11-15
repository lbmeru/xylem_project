"""Step 5: match news-reported fish kills to lake zones -> events.json.

Input: data/events_input.json, filled in by hand (date + source link for each event).
A town in the input is placed using config.TOWNS, or give explicit lat/lon.
The zone is the one containing the point, else the nearest zone. Check
`zone_distance_km`: a large value means the town is far from any zone, so verify by hand.
"""
import json

from pyproj import Transformer
from shapely.geometry import Point, shape
from shapely.ops import transform

from . import config as C
from .zones import load_zones

_to_utm = Transformer.from_crs(4326, C.UTM_EPSG, always_xy=True).transform


def match_zone(lat: float, lon: float, zones: dict) -> tuple[str, float]:
    p = Point(_to_utm(lon, lat))
    best = min(((f["properties"]["zone_id"], transform(_to_utm, shape(f["geometry"])).distance(p))
                for f in zones["features"]), key=lambda t: t[1])
    return best[0], round(best[1] / 1000, 2)


def build(events_in: list[dict], zones: dict) -> list[dict]:
    out = []
    for e in events_in:
        lat, lon = e.get("lat"), e.get("lon")
        if lat is None:
            if e["place"] not in C.TOWNS:
                raise ValueError(f"Unknown place {e['place']!r}: add lat/lon or add it to config.TOWNS")
            lat, lon = C.TOWNS[e["place"]]
        zone_id, dist = match_zone(lat, lon, zones)
        out.append({**{k: v for k, v in e.items() if k not in ("lat", "lon")},
                    "zone_id": zone_id, "zone_distance_km": dist})
    return out


def run() -> None:
    events_in = json.loads((C.DATA_DIR / "events_input.json").read_text())
    events = build(events_in, load_zones())
    (C.OUTPUT_DIR / "events.json").write_text(json.dumps(events, indent=2, ensure_ascii=False))
    missing = [e["id"] for e in events if not e.get("date")]
    print(f"events.json: {len(events)} events; {len(missing)} still need an exact date: {missing}")
