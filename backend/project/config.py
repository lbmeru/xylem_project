"""All tunable settings in one place.

The risk-rule cutoffs below are FIXED by the build plan. Do not change them after
looking at fish-kill events, or the backtest stops meaning anything.
"""
import os
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DATA_DIR = ROOT / "data"                                      # hand-edited inputs
CACHE_DIR = Path(os.getenv("BL_CACHE_DIR", ROOT / "cache"))   # downloaded raw data
OUTPUT_DIR = Path(os.getenv("BL_OUTPUT_DIR", ROOT / "output"))  # JSON the app reads
EE_PROJECT = os.getenv("EE_PROJECT")                          # Google Cloud project for Earth Engine
NDCI_SOURCE = os.getenv("BL_NDCI_SOURCE", "gee")             # "gee" (Earth Engine) or "pc" (Planetary Computer)
LAKE_SOURCE = os.getenv("BL_LAKE_SOURCE", "gee")             # "gee" or "bundled" (data/lake.geojson)

# ---- Study window -------------------------------------------------------
START_DATE = os.getenv("BL_START_DATE", "2019-01-01")   # baseline start; must include the May 2019 Biñan/Pila event
WEATHER_LAG_DAYS = 5        # Open-Meteo archive lags ~5 days, so the app shows "as of" data

# ---- Zones --------------------------------------------------------------
LAKE_BBOX = (121.0, 14.15, 121.45, 14.65)   # lon_min, lat_min, lon_max, lat_max
UTM_EPSG = 32651                            # UTM 51N, metres
CELL_SIZE_M = 5000                          # ~5 km grid
MIN_ZONE_AREA_KM2 = 5.0                     # drop thin shoreline slivers
SHORE_BUFFER_M = 300                        # inward shrink for the coarse bundled outline
SHORE_BUFFER_EE_M = 60                      # inward shrink for the Earth Engine water outline
NDCI_WORKERS = 4                            # parallel image downloads

# ---- Risk rule (fixed per plan) -----------------------------------------
TOP_Q = 0.80                # "top 20%"  -> 80th percentile of the zone's own history
BOTTOM_Q = 0.20             # "bottom 20%" -> 20th percentile
ROLL_DAYS = 3               # 3-day mean for temperature and wind
MAX_IMAGE_AGE_DAYS = 10     # no clear image in last 10 days -> Unknown
MIN_VALID_FRACTION = 0.5    # ASSUMPTION (not in plan): a zone needs >=50% clear pixels in an image
MIN_NDCI_OBS = 20           # need this many clear observations to set an NDCI cutoff
LEVELS = ["Low", "Watch", "High", "Unknown"]

# ---- Backtest -----------------------------------------------------------
EVENT_LOOKBACK_DAYS = 7

# ---- Weather ------------------------------------------------------------
OPEN_METEO_URL = "https://archive-api.open-meteo.com/v1/archive"
MIN_HOURS_PER_DAY = 18

# Approximate town-centre coordinates (lat, lon), used to label zones and place
# news events. Approximate: verify against the map before trusting a match.
TOWNS = {
    "Taguig": (14.5200, 121.0500), "Muntinlupa": (14.4000, 121.0400),
    "San Pedro": (14.3595, 121.0473), "Biñan": (14.3333, 121.0833),
    "Santa Rosa": (14.3122, 121.1114), "Cabuyao": (14.2724, 121.1250),
    "Calamba": (14.2117, 121.1653), "Los Baños": (14.1699, 121.2437),
    "Bay": (14.1833, 121.2833), "Pila": (14.2333, 121.3667),
    "Santa Cruz": (14.2792, 121.4161), "Jala-jala": (14.3258, 121.3239),
    "Pililla": (14.4839, 121.3039), "Tanay": (14.4981, 121.2847),
    "Baras": (14.5222, 121.2650), "Morong": (14.5128, 121.2393),
    "Cardona": (14.4856, 121.2306), "Binangonan": (14.4647, 121.1925),
    "Angono": (14.5249, 121.1537), "Taytay": (14.5569, 121.1324),
}
