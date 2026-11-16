"""Step 6: test the rule against past fish kills -> backtest.json.

Hit: the event's zone showed Watch or High on at least one of the 7 days before the event.
Miss: none of those days did. No data: all 7 days Unknown (not counted as hit or miss).
False alarm: a zone-week (fixed 7-day block) with at least one High day and no reported
event in that zone from the start of the block to 7 days after its end. The news may miss
kills, so some "false alarms" may be real. Counts only, no percentages (about 6 events).
"""
import json
from datetime import timedelta

import pandas as pd

from . import config as C

CAVEAT = ("Checked against only the fish kills reported in the news. Unreported kills would turn "
          "some 'false alarms' into correct warnings. Too few events to call this accurate.")


def run_backtest(daily: dict, events: list[dict]) -> dict:
    dates = pd.to_datetime(daily["dates"])
    pos = {d: i for i, d in enumerate(dates)}
    levels = daily["zones"]
    rows, skipped = [], []
    for e in events:
        if not e.get("date"):
            skipped.append({"id": e["id"], "reason": "no exact date"})
            continue
        if e["zone_id"] not in levels:
            skipped.append({"id": e["id"], "reason": "zone not found"})
            continue
        d0 = pd.Timestamp(e["date"])
        before = []
        for k in range(C.EVENT_LOOKBACK_DAYS, 0, -1):
            d = d0 - timedelta(days=k)
            lvl = levels[e["zone_id"]]["level"][pos[d]] if d in pos else "Unknown"
            before.append({"date": d.strftime("%Y-%m-%d"), "level": lvl})
        seen = {b["level"] for b in before}
        result = ("hit" if seen & {"Watch", "High"}
                  else "no_data" if seen == {"Unknown"} else "miss")
        rows.append({"id": e["id"], "place": e["place"], "zone_id": e["zone_id"],
                     "date": e["date"], "levels_before": before, "result": result})

    ev_by_zone: dict[str, list[pd.Timestamp]] = {}
    for e in events:
        if e.get("date") and e["zone_id"] in levels:
            ev_by_zone.setdefault(e["zone_id"], []).append(pd.Timestamp(e["date"]))

    zone_weeks = high_weeks = false_alarms = 0
    for zid, z in levels.items():
        lv = z["level"]
        for s in range(0, len(lv) - 6, 7):
            zone_weeks += 1
            if "High" not in lv[s:s + 7]:
                continue
            high_weeks += 1
            start, stop = dates[s], dates[s + 6] + timedelta(days=C.EVENT_LOOKBACK_DAYS)
            if not any(start <= d <= stop for d in ev_by_zone.get(zid, [])):
                false_alarms += 1

    count = lambda r: sum(1 for x in rows if x["result"] == r)  # noqa: E731
    return {
        "meta": {"as_of": daily["meta"]["as_of"], "caveat": CAVEAT,
                 "lookback_days": C.EVENT_LOOKBACK_DAYS},
        "summary": {"events_total": len(events), "events_tested": len(rows),
                    "hits": count("hit"), "misses": count("miss"), "no_data": count("no_data"),
                    "zone_weeks_total": zone_weeks, "zone_weeks_high": high_weeks,
                    "false_alarm_zone_weeks": false_alarms},
        "skipped": skipped,
        "events": rows,
    }


def run() -> None:
    daily = json.loads((C.OUTPUT_DIR / "daily_risk.json").read_text(encoding="utf-8"))
    events = json.loads((C.OUTPUT_DIR / "events.json").read_text(encoding="utf-8"))
    result = run_backtest(daily, events)
    (C.OUTPUT_DIR / "backtest.json").write_text(json.dumps(result, indent=2), encoding="utf-8")
    print(json.dumps(result["summary"], indent=2))
    if result["skipped"]:
        print("skipped:", result["skipped"])
