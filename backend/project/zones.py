"""Step 1: lake outline (Earth Engine water mask, or bundled) -> ~5 km grid zones -> zones.json."""
import json
import math

import numpy as np
from pyproj import Transformer
from shapely.geometry import Point, box, mapping, shape
from shapely.ops import transform

from . import config as C

_to_utm = Transformer.from_crs(4326, C.UTM_EPSG, always_xy=True).transform
_to_ll = Transformer.from_crs(C.UTM_EPSG, 4326, always_xy=True).transform


def ee_init():
    """Initialise Earth Engine, signing in with your Google account on first use."""
    import ee
    if not C.EE_PROJECT:
        raise SystemExit("Set EE_PROJECT to your Google Cloud project id, e.g. "
                         "export EE_PROJECT=my-project-123")
    try:
        ee.Initialize(project=C.EE_PROJECT)
    except Exception:  # noqa: BLE001  (not signed in yet)
        print("Signing in to Google Earth Engine. Follow the link, approve access, "
              "and paste the code back here.")
        ee.Authenticate(auth_mode="notebook")
        ee.Initialize(project=C.EE_PROJECT)
    return ee


def _lake_from_ee() -> dict:
    """Largest permanent-water polygon in the Laguna de Bay bbox (JRC Global Surface Water)."""
    ee = ee_init()
    region = ee.Geometry.Rectangle(list(C.LAKE_BBOX))
    water = (ee.Image("JRC/GSW1_4/GlobalSurfaceWater").select("occurrence").gt(60)
             .selfMask().rename("w"))
    vectors = water.reduceToVectors(geometry=region, scale=100, geometryType="polygon",
                                    eightConnected=True, maxPixels=int(1e10))
    vectors = vectors.map(lambda f: f.set("a", f.geometry().area(100)))
    return vectors.sort("a", False).first().geometry().getInfo()


def _lake_bundled() -> dict:
    path = C.DATA_DIR / "lake.geojson"
    if not path.exists():
        raise SystemExit(f"{path} is missing. Copy lake.geojson into the data folder.")
    gj = json.loads(path.read_text(encoding="utf-8"))
    return gj.get("geometry", gj)


def fetch_lake_polygon() -> tuple[dict, str]:
    """Returns (polygon, source). Earth Engine first; bundled outline if that fails."""
    if C.LAKE_SOURCE == "gee":
        try:
            return _lake_from_ee(), "gee"
        except SystemExit:
            raise
        except Exception as exc:  # noqa: BLE001
            print(f"Earth Engine lake outline failed ({exc}). Using the bundled outline.")
    return _lake_bundled(), "bundled"


def nearest_town(lat: float, lon: float) -> str:
    p = Point(_to_utm(lon, lat))
    return min(C.TOWNS.items(),
               key=lambda kv: Point(_to_utm(kv[1][1], kv[1][0])).distance(p))[0]


def build_zones(lake_geojson: dict, buffer_m: float | None = None) -> dict:
    buffer_m = C.SHORE_BUFFER_M if buffer_m is None else buffer_m
    lake = transform(_to_utm, shape(lake_geojson)).buffer(-buffer_m)
    minx, miny, maxx, maxy = lake.bounds
    s = C.CELL_SIZE_M
    feats = []
    for x in np.arange(math.floor(minx / s) * s, maxx, s):
        for y in np.arange(math.floor(miny / s) * s, maxy, s):
            piece = lake.intersection(box(x, y, x + s, y + s))
            if piece.is_empty or piece.area / 1e6 < C.MIN_ZONE_AREA_KM2:
                continue
            piece = piece.simplify(30)
            rp = transform(_to_ll, piece.representative_point())
            feats.append({
                "type": "Feature",
                "geometry": mapping(transform(_to_ll, piece)),
                "properties": {
                    # grid-based id: stable across re-runs
                    "zone_id": f"Z{int(x // s)}_{int(y // s)}",
                    "area_km2": round(piece.area / 1e6, 2),
                    "centroid_lat": round(rp.y, 5),
                    "centroid_lon": round(rp.x, 5),
                    "nearest_town": nearest_town(rp.y, rp.x),
                },
            })
    # number zones per town, north to south, for readable labels
    feats.sort(key=lambda f: (-f["properties"]["centroid_lat"], f["properties"]["centroid_lon"]))
    seen: dict[str, int] = {}
    for f in feats:
        t = f["properties"]["nearest_town"]
        seen[t] = seen.get(t, 0) + 1
        f["properties"]["label"] = f"{t} {seen[t]}"
    return {"type": "FeatureCollection", "features": feats}


def run() -> dict:
    C.CACHE_DIR.mkdir(parents=True, exist_ok=True)
    C.OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    lake, src = fetch_lake_polygon()
    (C.CACHE_DIR / "lake.geojson").write_text(json.dumps(lake), encoding="utf-8")
    zones = build_zones(lake, C.SHORE_BUFFER_EE_M if src == "gee" else C.SHORE_BUFFER_M)
    (C.OUTPUT_DIR / "zones.json").write_text(json.dumps(zones, separators=(",", ":")), encoding="utf-8")
    print(f"zones.json: {len(zones['features'])} zones (outline from {src})")
    return zones


def load_zones() -> dict:
    return json.loads((C.OUTPUT_DIR / "zones.json").read_text(encoding="utf-8"))
