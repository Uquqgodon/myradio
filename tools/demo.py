"""Package up to three editions as a single, offline, playable HTML file."""

import argparse
import base64
import json
import mimetypes
from pathlib import Path, PurePosixPath
import re


ROOT = Path(__file__).resolve().parent.parent
MARKER = '<script id="demo-data" type="application/json">'


def read_json(path):
    return json.loads(path.read_text(encoding="utf-8"))


def bundle(output, state=None, start=None):
    if state is not None and not (state / "episodes.json").is_file():
        raise ValueError(f"No episodes.json in {state}")

    def source(path):
        if PurePosixPath(path).is_absolute() or ".." in PurePosixPath(path).parts or re.search(r"[:\\]", path):
            raise ValueError(f"Cannot bundle a non-local asset: {path}")
        if state and (state / path).is_file():
            return state / path
        return ROOT / path

    station = read_json(ROOT / "station.json")
    station.update(tagline="オフライン試聴版", weather=False)
    station.pop("comments", None)
    character = read_json(ROOT / "character/character.json")
    files = {"station.json": station, "character/character.json": character}
    media = {"icons/icon-192.png", "assets/world-land.svg"}
    if station.get("logo"):
        media.add(station["logo"])
    media.update(path.relative_to(ROOT).as_posix() for path in (ROOT / "character").iterdir()
                 if path.is_file() and path.suffix != ".json")

    entries = []
    for entry in read_json(source("episodes.json")):
        name = entry.get("id", entry["date"])
        if not re.fullmatch(r"\d{4}-\d{2}-\d{2}(?:-\d{4})?", name):
            raise ValueError(f"Invalid edition id: {name}")
        script = f"episodes/{name}.json"
        episode = read_json(source(script))
        audio = episode.get("audio", f"audio/{name}.mp3")
        if not source(audio).is_file():
            continue
        entries.append(entry)
        files[script] = episode
        media.add(audio)
        if len(entries) == 3:
            break
    if not entries:
        raise ValueError("No playable editions to bundle.")
    if start and start not in {entry.get("id", entry["date"]) for entry in entries}:
        raise ValueError(f"The start edition is not in the demo: {start}")
    files["episodes.json"] = entries

    assets = {}
    for name in sorted(media):
        mime = mimetypes.guess_type(name)[0] or "application/octet-stream"
        encoded = base64.b64encode(source(name).read_bytes()).decode("ascii")
        assets[name] = f"data:{mime};base64,{encoded}"

    html = (ROOT / "index.html").read_text(encoding="utf-8")
    if html.count(MARKER) != 1:
        raise ValueError("The player is missing its demo data marker.")
    data = json.dumps({"json": files, "assets": assets, "start": start}, ensure_ascii=False).replace("<", "\\u003c")
    html = html.replace(MARKER, MARKER + data)
    html = re.sub(r'^<link rel="(?:manifest|apple-touch-icon)"[^\n]*\n', "", html, flags=re.MULTILINE)
    html = html.replace('href="./icons/icon-192.png"', f'href="{assets["icons/icon-192.png"]}"')
    license_text = (ROOT / "LICENSE").read_text(encoding="utf-8")
    html = html.replace("<!doctype html>", f"<!doctype html>\n<!--\n{license_text}-->\n", 1)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(html, encoding="utf-8")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--state-dir", type=Path, help="Optional output from tools/broadcast.py")
    parser.add_argument("--start", help="Optional episode ID to open first")
    args = parser.parse_args()
    bundle(args.output, args.state_dir, args.start)


if __name__ == "__main__":
    main()
