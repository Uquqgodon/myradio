"""Collect weather and earthquake snapshots from the public data providers."""

from datetime import datetime, timedelta, timezone
import json
import logging
import math
import re
from urllib.parse import urlencode
from urllib.request import Request, urlopen


WEATHER = "https://api.open-meteo.com/v1/forecast"
JMA = "https://www.jma.go.jp/bosai/quake/data/list.json"
USGS = "https://earthquake.usgs.gov/earthquakes/feed/v1.0/summary/4.5_week.geojson"
CAPITALS = [
    ("東京", 35.68, 139.69), ("ソウル", 37.57, 126.98),
    ("北京", 39.90, 116.41), ("ニューデリー", 28.61, 77.21),
    ("ロンドン", 51.51, -0.13), ("パリ", 48.86, 2.35),
    ("ベルリン", 52.52, 13.41), ("ローマ", 41.90, 12.50),
    ("ワシントン", 38.91, -77.04), ("オタワ", 45.42, -75.70),
]
JMA_INTENSITY = {"3": "3", "4": "4", "5-": "5弱", "5+": "5強",
                 "6-": "6弱", "6+": "6強", "7": "7"}


def fetch_json(url):
    try:
        with urlopen(Request(url, headers={"User-Agent": "myradio-bulletin/1.0"}), timeout=12) as response:
            return json.load(response)
    except (OSError, ValueError) as exc:
        logging.warning("Could not load %s: %s", url.split("?")[0], exc)
        return None


def weather_name(code):
    if code == 0:
        return "晴れ"
    if code == 1:
        return "おおむね晴れ"
    if code in (2, 3):
        return "曇り"
    if code in (45, 48):
        return "霧"
    if code in (71, 73, 75, 77, 85, 86):
        return "雪"
    if code in (95, 96, 99):
        return "雷雨"
    if code in (51, 53, 55, 56, 57, 61, 63, 65, 66, 67, 80, 81, 82):
        return "雨"
    return "天気不明"


def world_weather(now):
    query = urlencode({
        "latitude": ",".join(str(city[1]) for city in CAPITALS),
        "longitude": ",".join(str(city[2]) for city in CAPITALS),
        "current": "temperature_2m,weather_code",
    })
    data = fetch_json(f"{WEATHER}?{query}")
    rows = data if isinstance(data, list) and len(data) == len(CAPITALS) else [{} for _ in CAPITALS]
    cities = []
    observed_at = None
    for (name, _, _), row in zip(CAPITALS, rows):
        current = (row.get("current") or {}) if isinstance(row, dict) else {}
        temp = current.get("temperature_2m")
        if not isinstance(temp, (int, float)) or not math.isfinite(temp):
            temp = None
        timestamp = current.get("time")
        if temp is not None and observed_at is None and isinstance(timestamp, str):
            try:
                observed_at = datetime.fromisoformat(timestamp).replace(tzinfo=timezone.utc).astimezone(now.tzinfo)
            except ValueError:
                pass
        cities.append({"name": name, "temp_c": temp, "condition": weather_name(current.get("weather_code"))})
    return {"observed_at": observed_at.isoformat(timespec="minutes") if observed_at else None,
            "cities": cities}


def earthquake_window(now, date, slot, slots):
    end = datetime.fromisoformat(f"{date}T{slot}").replace(tzinfo=now.tzinfo)
    candidates = [datetime.fromisoformat(f"{date}T{time}").replace(tzinfo=now.tzinfo) for time in slots]
    start = max((candidate for candidate in candidates if candidate < end),
                default=max(candidates) - timedelta(days=1))
    return start, min(now, end)


def position(lat, lon):
    if isinstance(lat, (int, float)) and isinstance(lon, (int, float)) and -90 <= lat <= 90 and -180 <= lon <= 180:
        return {"lat": lat, "lon": lon}
    return {}


def japan_quakes(data, start, end):
    seen = set()
    events = []
    for item in sorted(data, key=lambda row: row.get("rdt", ""), reverse=True):
        event = item.get("eid")
        if not event or event in seen:
            continue
        seen.add(event)
        if item.get("ift") == "取消" or item.get("maxi") not in JMA_INTENSITY or not item.get("anm"):
            continue
        try:
            time = datetime.fromisoformat(item["at"]).astimezone(start.tzinfo)
        except (KeyError, TypeError, ValueError):
            continue
        if start < time <= end:
            coordinates = re.match(r"([+-]\d+(?:\.\d+)?)([+-]\d+(?:\.\d+)?)", item.get("cod") or "")
            point = position(*map(float, coordinates.groups())) if coordinates else {}
            events.append({"source": "jma", "place": item["anm"], "time": time.isoformat(),
                           "intensity": JMA_INTENSITY[item["maxi"]], **point,
                           "url": "https://www.jma.go.jp/bosai/map.html#contents=earthquake_map"})
    return events


def world_quakes(data, start, end):
    events = []
    for feature in data:
        item = feature.get("properties") or {}
        magnitude, millis = item.get("mag"), item.get("time")
        place = item.get("place") or ""
        if (item.get("type") != "earthquake" or not isinstance(magnitude, (int, float))
                or not 5 <= magnitude <= 10 or not isinstance(millis, (int, float))):
            continue
        try:
            time = datetime.fromtimestamp(millis / 1000, start.tzinfo)
        except (OverflowError, OSError, ValueError):
            continue
        if start < time <= end:
            coordinates = (feature.get("geometry") or {}).get("coordinates") or []
            point = position(coordinates[1], coordinates[0]) if len(coordinates) >= 2 else {}
            url = item.get("url") or ""
            if not url.startswith("https://earthquake.usgs.gov/earthquakes/eventpage/"):
                url = "https://earthquake.usgs.gov/earthquakes/map/"
            events.append({"source": "usgs", "place": place or "震源地不明", "time": time.isoformat(),
                           "magnitude": magnitude, "url": url, **point})
    return events


def same_quake(first, second):
    if not all(key in event for event in (first, second) for key in ("lat", "lon")):
        return False
    delta = datetime.fromisoformat(first["time"]) - datetime.fromisoformat(second["time"])
    longitude = abs(first["lon"] - second["lon"])
    return (abs(delta.total_seconds()) <= 60 and abs(first["lat"] - second["lat"]) < 0.5
            and min(longitude, 360 - longitude) < 0.5)


def earthquakes(start, end):
    snapshot = {"start": start.isoformat(), "end": end.isoformat(), "sources": {}, "events": []}
    if start >= end:
        return snapshot
    jma = fetch_json(JMA)
    usgs = fetch_json(USGS)
    global_data = usgs.get("features") if isinstance(usgs, dict) else None
    snapshot["sources"] = {"jma": isinstance(jma, list), "usgs": isinstance(global_data, list)}
    japan = japan_quakes(jma, start, end) if snapshot["sources"]["jma"] else []
    world = world_quakes(global_data, start, end) if snapshot["sources"]["usgs"] else []
    events = japan + [event for event in world if not any(same_quake(event, jp) for jp in japan)]
    snapshot["events"] = sorted(events, key=lambda event: event["time"], reverse=True)
    return snapshot
