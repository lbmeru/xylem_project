"""Build the 3-sheet response guide PDF for fish cage operators.

    python build_blueprint.py [output/zones.json] [out.pdf]

Sheet 1 zones and levels, sheet 2 response card (from data/response_cards.json, every
action printed with its source), sheet 3 blank field check log.
If zones.json is missing, sheet 1 shows a placeholder box instead of the zone grid.
"""
import json
import math
import sys
from pathlib import Path

from reportlab.lib.colors import HexColor, white
from reportlab.lib.pagesizes import letter
from reportlab.lib.utils import simpleSplit
from reportlab.pdfgen import canvas

ROOT = Path(__file__).resolve().parent
W, H = letter
M = 40
INK, MUTED, LINE, DEEP = HexColor("#14262b"), HexColor("#5a6b70"), HexColor("#d3dcde"), HexColor("#0f4c5c")
COL = {"Low": HexColor("#3d8c7a"), "Watch": HexColor("#e3a72f"), "High": HexColor("#c0392b"),
       "Unknown": HexColor("#9aa6aa")}
LETTER = {"Low": "L", "Watch": "W", "High": "H", "Unknown": "?"}
MEANING = {
    "Low": "0 or 1 of the 3 checks is yes. Normal routine.",
    "Watch": "2 of the 3 checks are yes.",
    "High": "All 3 checks are yes.",
    "Unknown": "No clear satellite image in the last 10 days, or weather data is missing.",
}
ABOUT = ("A simple rule checked against about 6 fish kills reported in the news. "
         "It is not a guarantee that a zone is safe or unsafe.")


def para(c, text, x, y, width, font="Helvetica", size=10, lead=None, color=INK):
    """Draw wrapped text from the top (y); return y after the last line."""
    lead = lead or size * 1.35
    c.setFont(font, size); c.setFillColor(color)
    for line in simpleSplit(text, font, size, width):
        y -= lead
        c.drawString(x, y, line)
    return y


def header(c, title, sub, page):
    c.setFillColor(DEEP); c.rect(0, H - 78, W, 78, stroke=0, fill=1)
    c.setFillColor(white); c.setFont("Helvetica-Bold", 22); c.drawString(M, H - 42, title)
    c.setFont("Helvetica", 10.5); c.drawString(M, H - 62, sub)
    c.setFillColor(MUTED); c.setFont("Helvetica", 8)
    c.drawString(M, 24, "Bantay Lawa · A simple rule checked on a few news-reported fish kills, not a guarantee.")
    c.drawRightString(W - M, 24, f"Page {page} of 3")


def draw_zone_grid(c, zones_path, x, y, w, h):
    """Fit the zone polygons into the box (x, y, w, h)."""
    if not zones_path or not Path(zones_path).exists():
        c.setStrokeColor(MUTED); c.setDash(4, 3); c.rect(x, y, w, h); c.setDash()
        para(c, "Zone grid goes here. Run the data pipeline, then run build_blueprint.py again "
                "to draw the zones.", x + 20, y + h / 2 + 10, w - 40, color=MUTED, size=10)
        return
    feats = json.loads(Path(zones_path).read_text())["features"]
    rings = []
    for f in feats:
        g = f["geometry"]
        polys = [g["coordinates"]] if g["type"] == "Polygon" else g["coordinates"]
        rings.append((f, polys))
    lats = [p[1] for _, ps in rings for poly in ps for p in poly[0]]
    lons = [p[0] for _, ps in rings for poly in ps for p in poly[0]]
    k = math.cos(math.radians(sum(lats) / len(lats)))
    sx = (max(lons) - min(lons)) * k
    sy = max(lats) - min(lats)
    s = min(w / sx, h / sy) * 0.96
    ox = x + (w - sx * s) / 2
    oy = y + (h - sy * s) / 2
    pt = lambda p: (ox + (p[0] - min(lons)) * k * s, oy + (p[1] - min(lats)) * s)  # noqa: E731
    c.setLineWidth(1.2); c.setStrokeColor(white)
    for f, polys in rings:
        c.setFillColor(HexColor("#cfe0e4"))
        for poly in polys:
            path = c.beginPath()
            for i, p in enumerate(poly[0]):
                (path.moveTo if i == 0 else path.lineTo)(*pt(p))
            path.close(); c.drawPath(path, stroke=1, fill=1)
    for f, _ in rings:
        pr = f["properties"]
        cx, cy = pt((pr["centroid_lon"], pr["centroid_lat"]))
        c.setFillColor(INK); c.setFont("Helvetica", 5.5)
        town, _, n = pr["label"].rpartition(" ")
        c.drawCentredString(cx, cy + 2, town); c.drawCentredString(cx, cy - 5, n)


def sheet1(c, zones_path):
    header(c, "Which zones are at risk", "Sheet 1 of 3 · Zones and levels", 1)
    y = para(c, "Laguna de Bay is split into squares of about 5 km called zones. Every day the Bantay Lawa "
                "map gives each zone one of four levels. Find your zone on the grid, then check its level "
                "in the app.", M, H - 96, W - 2 * M, size=10.5)
    gy = y - 12
    box_h = 300
    c.setStrokeColor(LINE); c.rect(M, gy - box_h, W - 2 * M, box_h)
    draw_zone_grid(c, zones_path, M + 8, gy - box_h + 8, W - 2 * M - 16, box_h - 16)
    y = gy - box_h - 22
    c.setFont("Helvetica-Bold", 12); c.setFillColor(INK); c.drawString(M, y, "What each level means")
    y -= 10
    for name in ["Low", "Watch", "High", "Unknown"]:
        y -= 26
        c.setFillColor(COL[name]); c.roundRect(M, y - 4, 22, 22, 3, stroke=0, fill=1)
        c.setFillColor(white); c.setFont("Helvetica-Bold", 11); c.drawCentredString(M + 11, y + 3, LETTER[name])
        c.setFillColor(INK); c.setFont("Helvetica-Bold", 11); c.drawString(M + 32, y + 3, name)
        para(c, MEANING[name], M + 90, y + 17, W - 2 * M - 90, size=10)
    y -= 22
    para(c, "How a zone gets its level: the app runs three yes/no checks. (1) Algae: the satellite algae "
            "reading is in the top 20% of that zone's own history. (2) Warm: the 3-day average air "
            "temperature is in the top 20% of its history. (3) Calm: the 3-day average wind speed is in the "
            "bottom 20%. Air temperature stands in for water temperature, which we do not measure.",
         M, y, W - 2 * M, size=9, color=MUTED)


def sheet2(c, cards):
    header(c, "What to do at each level", "Sheet 2 of 3 · Response card", 2)
    gap, colw = 12, (W - 2 * M - 24) / 3
    top = H - 100
    bottom_y = top
    for i, name in enumerate(["Low", "Watch", "High"]):
        x = M + i * (colw + gap)
        c.setFillColor(COL[name]); c.rect(x, top - 28, colw, 28, stroke=0, fill=1)
        c.setFillColor(white); c.setFont("Helvetica-Bold", 13)
        c.drawString(x + 10, top - 19, f"{LETTER[name]}  {name}")
        y = top - 28
        for a in cards["levels"][name]["actions"]:
            y -= 8
            y = para(c, a["text"], x + 8, y, colw - 16, "Helvetica-Bold", 10.5)
            y = para(c, f"Source: {a['source']}", x + 8, y - 1, colw - 16, "Helvetica-Oblique", 8.5, color=MUTED)
            y -= 6
            c.setStrokeColor(LINE); c.line(x + 8, y, x + colw - 8, y)
        bottom_y = min(bottom_y, y)
    # column outlines down to a common bottom
    box_bottom = min(bottom_y - 10, top - 250)
    for i in range(3):
        x = M + i * (colw + gap)
        c.setStrokeColor(LINE); c.rect(x, box_bottom, colw, top - 28 - box_bottom)
    y = box_bottom - 18
    c.setFont("Helvetica-Bold", 11); c.setFillColor(INK); c.drawString(M, y, "Limits to know")
    y = para(c, "Early harvest depends on a buyer. " + cards["limit"].split(". ", 1)[-1], M, y - 2, W - 2 * M, size=10)
    y = para(c, cards["oxygen_link"], M, y - 4, W - 2 * M, size=10)
    y -= 24
    c.setFont("Helvetica-Bold", 11); c.setFillColor(COL["Unknown"]); c.drawString(M, y, "Unknown (grey)")
    ua = cards["levels"]["Unknown"]["actions"][0]
    para(c, f"{ua['text']} (Source: {ua['source']})", M, y - 2, W - 2 * M, size=10)


def sheet3(c):
    header(c, "Field check log", "Sheet 3 of 3 · Blank form to copy and keep", 3)
    y = para(c, "For operators who own an oxygen kit or meter. Bantay Lawa collects no readings itself, "
                "so this log is only for your own records.", M, H - 96, W - 2 * M, size=10.5)
    cols = [("Date", 70), ("Time", 52), ("Zone", 80), ("Dissolved oxygen reading", 108),
            ("Water color", 100), ("Dead fish count", 102)]
    tw = sum(w for _, w in cols)
    x0 = M + (W - 2 * M - tw) / 2
    top = y - 18
    c.setFillColor(DEEP); c.rect(x0, top - 30, tw, 30, stroke=0, fill=1)
    x = x0
    c.setFillColor(white); c.setFont("Helvetica-Bold", 9)
    for label, w in cols:
        for j, line in enumerate(simpleSplit(label, "Helvetica-Bold", 9, w - 8)):
            c.drawString(x + 5, top - 12 - j * 11, line)
        x += w
    rows, rh = 17, 32
    c.setStrokeColor(LINE); c.setFillColor(INK)
    for r in range(rows):
        ry = top - 30 - (r + 1) * rh
        c.line(x0, ry, x0 + tw, ry)
    x = x0
    for _, w in cols + [("", 0)]:
        c.line(x, top, x, top - 30 - rows * rh)
        x += w
    c.setFillColor(MUTED); c.setFont("Helvetica", 8)
    c.drawString(x0, top - 30 - rows * rh - 14, "Write the unit your meter shows next to each oxygen reading.")


def build(out, zones_path, cards_path):
    cards = json.loads(Path(cards_path).read_text())
    for lv in ("Low", "Watch", "High", "Unknown"):
        for a in cards["levels"][lv]["actions"]:
            assert a.get("source"), f"Action without a source: {a['text']}"
    c = canvas.Canvas(str(out), pagesize=letter)
    c.setTitle("Bantay Lawa: response guide for fish cage operators")
    sheet1(c, zones_path); c.showPage()
    sheet2(c, cards); c.showPage()
    sheet3(c); c.showPage()
    c.save()


if __name__ == "__main__":
    zp = sys.argv[1] if len(sys.argv) > 1 else ROOT / "output" / "zones.json"
    out = Path(sys.argv[2]) if len(sys.argv) > 2 else ROOT / "output" / "Bantay_Lawa_Response_Guide.pdf"
    out.parent.mkdir(parents=True, exist_ok=True)
    build(out, zp, ROOT / "data" / "response_cards.json")
    print("wrote", out)
