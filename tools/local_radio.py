"""Update the private radio library and its offline player."""

import argparse
from datetime import datetime, timedelta
from pathlib import Path
import re
import tempfile

from broadcast import JST, ROOT, broadcast, read_json
from demo import bundle


def update(library, slot, config, now):
    archive = library / "archive"
    for folder in ("episodes", "audio"):
        (archive / folder).mkdir(parents=True, exist_ok=True)

    with tempfile.TemporaryDirectory(dir=library) as temp:
        work = Path(temp)
        snapshot = work / "snapshot"
        snapshot.mkdir()
        broadcast(config, slot, archive, snapshot, now)
        preview = work / "My Radio.html"
        bundle(preview, snapshot)

        for folder in ("audio", "episodes"):
            for item in (snapshot / folder).iterdir():
                item.replace(archive / folder / item.name)
        (snapshot / "episodes.json").replace(archive / "episodes.json")
        preview.replace(library / preview.name)

    keep_days = read_json(ROOT / "station.json")["audio"]["keep_days"]
    cutoff = (now.date() - timedelta(days=keep_days)).isoformat()
    for entry in read_json(archive / "episodes.json"):
        if entry.get("id") and entry["date"] < cutoff:
            (archive / "audio" / f"{entry['id']}.mp3").unlink(missing_ok=True)
    return library / preview.name


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--slot", required=True, help="Scheduled time in JST, HH:MM")
    parser.add_argument("--library", type=Path, required=True)
    parser.add_argument("--config", type=Path, default=ROOT / "news.json")
    args = parser.parse_args()
    if not re.fullmatch(r"(?:[01]\d|2[0-3]):[0-5]\d", args.slot):
        parser.error("--slot must be a 24-hour time in HH:MM format")
    print(update(args.library, args.slot, read_json(args.config), datetime.now(JST)))


if __name__ == "__main__":
    main()
