"""Build weather and earthquake segments from the public data providers."""

from datetime import datetime, timedelta, timezone
import json
import logging
import math
from urllib.parse import urlencode
from urllib.request import Request, urlopen


WEATHER = "https://api.open-meteo.com/v1/forecast"
JMA = "https://www.jma.go.jp/bosai/quake/data/list.json"
USGS = "https://earthquake.usgs.gov/earthquakes/feed/v1.0/summary/4.5_day.geojson"
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


def section(kind, label, source, url, intro, points):
    return {"kind": kind, "label": label, "points": points,
            "lines": [{"say": line, "show": line} for line in [intro, *points]],
            "url": url, "link": {"url": url, "site": source, "title": label}}


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
    cities = []
    snapshot = now
    if isinstance(data, list) and len(data) == len(CAPITALS):
        timestamp = data[0].get("current", {}).get("time")
        if isinstance(timestamp, str):
            snapshot = datetime.fromisoformat(timestamp).replace(tzinfo=timezone.utc).astimezone(now.tzinfo)
        for (name, _, _), row in zip(CAPITALS, data):
            current = row.get("current", {})
            temp = current.get("temperature_2m")
            if isinstance(temp, (int, float)) and math.isfinite(temp):
                degrees = f"マイナス{abs(round(temp))}" if round(temp) < 0 else str(round(temp))
                cities.append(f"{name}は{weather_name(current.get('weather_code'))}、{degrees}度")
            else:
                cities.append(f"{name}はデータなし")
    points = ["。".join(cities[i:i+2]) + "。" for i in range(0, len(cities), 2)]
    if not points:
        points = ["各都市の天気を取得できませんでした。"]
    return section("weather", "世界の天気", "Open-Meteo", "https://open-meteo.com/",
                   f"世界の主要都市の天気です。日本時間{snapshot.hour}時{snapshot.minute}分ごろの推定です。", points)


def earthquake_window(now, date, slot, slots):
    end = datetime.fromisoformat(f"{date}T{slot}").replace(tzinfo=now.tzinfo)
    candidates = [datetime.fromisoformat(f"{date}T{time}").replace(tzinfo=now.tzinfo) for time in slots]
    start = max((candidate for candidate in candidates if candidate < end),
                default=max(candidates) - timedelta(days=1))
    return start, min(now, end)


def jp_time(value, include_day=False):
    return (f"{value.day}日" if include_day else "") + f"{value.hour}時{value.minute}分"


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
            intensity = JMA_INTENSITY[item["maxi"]]
            events.append((time, f"{jp_time(time, True)}ごろ、{item['anm']}で最大震度{intensity}。"))
    return events


def world_quakes(data, start, end):
    events = []
    for feature in data:
        item = feature.get("properties") or {}
        magnitude, millis = item.get("mag"), item.get("time")
        place = item.get("place") or ""
        if (item.get("type") != "earthquake" or not isinstance(magnitude, (int, float))
                or not 5 <= magnitude <= 10 or not isinstance(millis, (int, float))
                or place.casefold().endswith(("japan", "japan region"))):
            continue
        try:
            time = datetime.fromtimestamp(millis / 1000, start.tzinfo)
        except (OverflowError, OSError, ValueError):
            continue
        if start < time <= end:
            # The source uses English place names. Keep them as reported.
            events.append((time, f"{jp_time(time, True)}ごろ、{place or '震源地不明'}でマグニチュード{magnitude:.1f}。"))
    return events


def quake_points(events, threshold):
    if events is None:
        return ["地震情報を取得できませんでした。"]
    if not events:
        return [f"この時間帯の公表データに、{threshold}の地震はありませんでした。"]
    points = [text for _, text in sorted(events, reverse=True)[:3]]
    if len(events) > 3:
        points.append(f"この時間帯の該当件数は、合わせて{len(events)}件です。")
    return points


def earthquake_sections(start, end):
    if start >= end:
        return []
    intro = f"日本時間{jp_time(start, True)}から{jp_time(end, True)}までの地震情報です。"
    jma = fetch_json(JMA)
    usgs = fetch_json(USGS)
    jp = japan_quakes(jma, start, end) if isinstance(jma, list) else None
    overseas = usgs.get("features") if isinstance(usgs, dict) else None
    world = world_quakes(overseas, start, end) if isinstance(overseas, list) else None
    return [
        section("earthquake", "日本の地震", "気象庁",
                "https://www.jma.go.jp/bosai/map.html#contents=earthquake_map",
                intro, quake_points(jp, "最大震度3以上")),
        section("earthquake", "海外の地震", "USGS",
                "https://earthquake.usgs.gov/earthquakes/map/",
                "続いて、海外の地震です。", quake_points(world, "マグニチュード5以上")),
    ]
