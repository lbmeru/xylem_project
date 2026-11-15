"""Step 2: NDCI per zone per image from Sentinel-2 L2A.

Two sources, chosen with BL_NDCI_SOURCE:
  gee (default): Google Earth Engine does the work on Google's servers (needs a Google login).
  pc: Microsoft Planetary Computer, no account, but images are downloaded to your computer.

NDCI = (B5 - B4) / (B5 + B4). B4 is 10 m and B5 is 20 m, so B4 is averaged down to
B5's 20 m grid. Clouds, shadow, cirrus and snow are masked with the SCL band. We do not
keep only SCL "water": Sen2Cor can label dense blooms as vegetation. The lake mask is the zones.
Output rows (one per zone per image) are cached per quarter, same format as before.
"""
import concurrent.futures as cf
import time

import numpy as np
import pandas as pd
from pyproj import Transformer
from shapely.geometry import shape
from shapely.ops import transform as shp_transform

from . import config as C
from .zones import ee_init, load_zones

STAC_URL = "https://planetarycomputer.microsoft.com/api/stac/v1"
BAD_SCL = [0, 1, 3, 8, 9, 10, 11]  # no data, saturated, cloud shadow, clouds, cirrus, snow
COLS = ["zone_id", "date", "image_id", "mean", "count"]


def zone_stats(b4, b5, scl, labels, n_zones):
    """b4, b5: reflectance (NaN = no data). scl: class codes. labels: 0 outside, 1..n zone.
    Returns (sum of NDCI, pixel count) per label, index 0 unused."""
    ok = (labels > 0) & ~np.isin(scl, BAD_SCL) & np.isfinite(b4) & np.isfinite(b5) & (b4 > 0) & (b5 > 0)
    ndci = (b5[ok] - b4[ok]) / (b5[ok] + b4[ok])
    lab = labels[ok]
    return (np.bincount(lab, weights=ndci, minlength=n_zones + 1),
            np.bincount(lab, minlength=n_zones + 1))


def _scale_offset(asset):
    rb = (asset.extra_fields.get("raster:bands") or [{}])[0]
    return rb.get("scale", 1e-4), rb.get("offset", 0.0)


def _reflectance(dn, scale, offset):
    return np.where(dn == 0, np.nan, dn.astype("float32") * scale + offset)


def _read_item(item, geoms, ids):
    """Read B04/B05/SCL for the lake window and return one row per zone with valid pixels."""
    import rasterio
    from rasterio.enums import Resampling
    from rasterio.features import rasterize
    from rasterio.warp import transform_bounds
    from rasterio.windows import bounds as win_bounds
    from rasterio.windows import from_bounds

    a = item.assets
    with rasterio.open(a["B05"].href) as d5, rasterio.open(a["B04"].href) as d4, \
            rasterio.open(a["SCL"].href) as ds:
        box = transform_bounds("EPSG:4326", d5.crs, *C.LAKE_BBOX)
        win = from_bounds(*box, transform=d5.transform).round_offsets().round_lengths()
        shp = (int(win.height), int(win.width))
        tr = d5.window_transform(win)
        b5 = d5.read(1, window=win, boundless=True, fill_value=0)
        scl = ds.read(1, window=win, boundless=True, fill_value=0)
        w4 = from_bounds(*win_bounds(win, d5.transform), transform=d4.transform)
        b4 = d4.read(1, window=w4, out_shape=shp, resampling=Resampling.average,
                     boundless=True, fill_value=0)
        to_crs = Transformer.from_crs(4326, d5.crs, always_xy=True).transform
        labels = rasterize([(shp_transform(to_crs, g), i + 1) for i, g in enumerate(geoms)],
                           out_shape=shp, transform=tr, fill=0, dtype="int32")
    s4, o4 = _scale_offset(a["B04"])
    s5, o5 = _scale_offset(a["B05"])
    sums, counts = zone_stats(_reflectance(b4, s4, o4), _reflectance(b5, s5, o5), scl, labels, len(ids))
    date = item.datetime.strftime("%Y-%m-%d")
    return [{"zone_id": ids[i], "date": date, "image_id": item.id,
             "mean": sums[i + 1] / counts[i + 1], "count": int(counts[i + 1])}
            for i in range(len(ids)) if counts[i + 1] > 0]


def _process(item, geoms, ids):
    import planetary_computer as pc
    for attempt in range(3):
        try:
            return _read_item(pc.sign(item), geoms, ids)   # sign right before use: links expire
        except Exception as exc:  # noqa: BLE001
            if attempt == 2:
                print(f"  skipped {item.id}: {exc}")
                return None
            time.sleep(3 * (attempt + 1))


def _fetch_pc(end: pd.Timestamp) -> None:
    from pystac_client import Client
    zones = load_zones()["features"]
    ids = [f["properties"]["zone_id"] for f in zones]
    geoms = [shape(f["geometry"]) for f in zones]
    catalog = Client.open(STAC_URL)
    out = C.CACHE_DIR / "ndci_raw"
    out.mkdir(parents=True, exist_ok=True)
    start = pd.Timestamp(C.START_DATE)
    for q in pd.period_range(start, end, freq="Q"):
        path = out / f"{q}.csv"
        q_end = q.end_time.normalize()
        if path.exists() and q_end < end - pd.Timedelta(days=45):
            continue  # finished quarters are cached; recent ones are re-fetched
        s = max(q.start_time, start).strftime("%Y-%m-%d")
        e = min(q_end, end).strftime("%Y-%m-%d")
        items = list(catalog.search(collections=["sentinel-2-l2a"], bbox=C.LAKE_BBOX,
                                    datetime=f"{s}/{e}",
                                    query={"eo:cloud_cover": {"lt": 90}}).items())
        print(f"{s} -> {e}: {len(items)} images")
        rows, failed = [], 0
        with cf.ThreadPoolExecutor(C.NDCI_WORKERS) as ex:
            for res in ex.map(lambda it: _process(it, geoms, ids), items):
                if res is None:
                    failed += 1
                else:
                    rows += res
        if failed and failed == len(items):
            raise SystemExit("Every image failed to download. Check your internet connection.")
        pd.DataFrame(rows, columns=COLS).to_csv(path, index=False)


# ---------------------------------------------------------------- Earth Engine
def _gee_per_image_fn(ee, zones_fc):
    def fn(img):
        img = ee.Image(img)
        scl = img.select("SCL")
        clear = scl.neq(BAD_SCL[0])
        for c in BAD_SCL[1:]:
            clear = clear.And(scl.neq(c))
        b5 = img.select("B5")
        b4 = (img.select("B4").reduceResolution(ee.Reducer.mean(), maxPixels=64)
              .reproject(b5.projection()))
        ok = clear.And(b4.gt(0)).And(b5.gt(0))
        ndci = b5.subtract(b4).divide(b5.add(b4)).updateMask(ok).rename("ndci")
        date = img.date().format("YYYY-MM-dd")
        stats = ndci.reduceRegions(
            collection=zones_fc,
            reducer=ee.Reducer.mean().combine(ee.Reducer.count(), sharedInputs=True),
            scale=20, crs=f"EPSG:{C.UTM_EPSG}")
        return stats.map(lambda ft: ee.Feature(None, {
            "zone_id": ft.get("zone_id"), "date": date,
            "image_id": img.get("system:index"),
            "mean": ft.get("mean"), "count": ft.get("count")}))
    return fn


def _gee_chunk(ee, zones_fc, aoi, start, end_exclusive) -> pd.DataFrame:
    col = (ee.ImageCollection("COPERNICUS/S2_SR_HARMONIZED")
           .filterBounds(aoi).filterDate(start, end_exclusive))
    fc = col.map(_gee_per_image_fn(ee, zones_fc)).flatten()
    for attempt in range(4):
        try:
            feats = fc.getInfo()["features"]
            break
        except Exception as exc:  # noqa: BLE001
            if attempt == 3:
                raise
            print(f"  retry after error: {exc}")
            time.sleep(5 * (attempt + 1))
    return pd.DataFrame([f["properties"] for f in feats], columns=COLS)


def _fetch_gee(end: pd.Timestamp) -> None:
    ee = ee_init()
    zones = load_zones()
    zones_fc = ee.FeatureCollection([
        ee.Feature(ee.Geometry(f["geometry"]), {"zone_id": f["properties"]["zone_id"]})
        for f in zones["features"]])
    aoi = zones_fc.geometry().bounds()
    out = C.CACHE_DIR / "ndci_raw"
    out.mkdir(parents=True, exist_ok=True)
    start = pd.Timestamp(C.START_DATE)
    for q in pd.period_range(start, end, freq="Q"):
        path = out / f"{q}.csv"
        q_end = q.end_time.normalize() + pd.Timedelta(days=1)
        if path.exists() and q_end < end - pd.Timedelta(days=45):
            continue  # finished quarters are cached; recent ones are re-fetched
        s = max(q.start_time, start).strftime("%Y-%m-%d")
        e = min(q_end, end + pd.Timedelta(days=1)).strftime("%Y-%m-%d")
        print(f"Earth Engine: {s} -> {e}")
        _gee_chunk(ee, zones_fc, aoi, s, e).to_csv(path, index=False)


def fetch(end: pd.Timestamp | None = None) -> None:
    """Download per-image zone stats, one cached CSV per quarter."""
    end = end or pd.Timestamp.today().normalize()
    if C.NDCI_SOURCE == "gee":
        _fetch_gee(end)
    elif C.NDCI_SOURCE == "pc":
        _fetch_pc(end)
    else:
        raise SystemExit(f"BL_NDCI_SOURCE must be 'gee' or 'pc', not {C.NDCI_SOURCE!r}")



def build_daily() -> pd.DataFrame:
    """Combine per-image rows into one row per (zone, date): pixel-weighted mean NDCI."""
    files = sorted((C.CACHE_DIR / "ndci_raw").glob("*.csv"))
    if not files:
        raise SystemExit("No NDCI data cached. Run the `ndci` step first.")
    raw = pd.concat([pd.read_csv(f) for f in files], ignore_index=True)
    raw["count"] = raw["count"].fillna(0)
    raw["mean"] = raw["mean"].astype(float)
    raw = raw[raw["count"] > 0].copy()
    raw["wsum"] = raw["mean"] * raw["count"]
    g = raw.groupby(["zone_id", "date"], as_index=False).agg(wsum=("wsum", "sum"),
                                                              n=("count", "sum"))
    area = {f["properties"]["zone_id"]: f["properties"]["area_km2"]
            for f in load_zones()["features"]}
    g["ndci"] = g["wsum"] / g["n"]
    expected = g["zone_id"].map(area) * 1e6 / 400.0  # 20 m pixels in the zone
    g["valid_fraction"] = (g["n"] / expected).clip(upper=1.0)
    g["date"] = pd.to_datetime(g["date"])
    out = g[["zone_id", "date", "ndci", "valid_fraction"]].sort_values(["zone_id", "date"])
    out.to_csv(C.CACHE_DIR / "ndci_daily.csv", index=False)
    return out
