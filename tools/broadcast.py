"""Turn RSS/Atom entries into one dated, timed Japanese radio edition."""

import argparse
from datetime import datetime, timedelta, timezone
import json
import os
from pathlib import Path
import re
import shutil
import tempfile
import unicodedata

from conditions import earthquake_sections, earthquake_window, world_weather
from news_feeds import article_key, collect_news
from voice import LILIN, MEI, load_voice


ROOT = Path(__file__).resolve().parent.parent
JST = timezone(timedelta(hours=9))


def read_json(path):
    return json.loads(path.read_text(encoding="utf-8"))


def write_json(path, data):
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def sentence_key(text):
    text = unicodedata.normalize("NFKC", text).casefold()
    return "".join(char for char in text if char.isalnum())


def summarize(article):
    """Pick up to two complete, non-redundant sentences from the RSS description."""
    seen = {sentence_key(article["title"])}
    selected = []
    length = 0
    for match in re.finditer(r"[^。！？]+[。！？]+[」』”）]*", article["description"]):
        sentence = match[0].strip()
        key = sentence_key(sentence)
        if (len(key) < 8 or key in seen or length + len(sentence) > 120
                or re.search(r"https?://|続きを読む|詳しくはこちら|こちらをクリック|…", sentence)):
            continue
        selected.append(sentence)
        seen.add(key)
        length += len(sentence)
        if len(selected) == 2:
            break
    return "".join(selected)


def make_episode(stories, edition, now, limit, sections):
    news = []
    seen_titles = set()
    for article in stories:
        title = article["title"].rstrip("。")
        title_key = sentence_key(title)
        summary = summarize(article)
        if not summary or title_key in seen_titles:
            continue
        seen_titles.add(title_key)
        spoken = f"{article['source']}から。{summary}"
        news.append({
            "label": title,
            "points": [summary],
            "lines": [line(spoken)],
            "url": article["url"],
            "link": {"url": article["url"], "title": title, "site": article["source"], "description": summary},
        })
        if len(news) == limit:
            break
    news.extend(sections)
    if not news:
        return None
    hour, minute = map(int, edition["time"].split(":"))
    clock = f"{hour}時" + (f"{minute}分" if minute else "")
    return {
        "format": "monoradio/news-1", **edition, "lang": "ja",
        "title": f"{clock}のニュース",
        "opening": [line(f"マイラジオです。{clock}のニュースをお届けします。")],
        "news": news,
        "closing": [line("詳しくは出典をご覧ください。以上、マイラジオでした。")],
        "credits": ["天気：Open-Meteo（CC BY 4.0）", "地震：気象庁、USGS"] if sections else [],
        "made_at": now.isoformat(timespec="seconds"),
    }


def line(text):
    return {"say": text, "show": text}


def synthesize(episode, config):
    import lameenc

    speak, rate, credit = load_voice(config)
    episode["voice_credit"] = credit
    if credit == LILIN:
        episode["closing"].append({"say": "音声は、コエイロインクのリリンちゃんでした。", "show": LILIN})

    parts = [("opening", None, episode["opening"])]
    parts.extend(("news", i, story["lines"]) for i, story in enumerate(episode["news"]))
    parts.append(("closing", None, episode["closing"]))
    silence = bytes(2 * (rate // 5))
    samples = 0
    audio, timed, segments = [], [], []

    def stamp():
        return round(samples / rate, 3)

    for part, (kind, index, lines) in enumerate(parts):
        start = stamp()
        for spoken in lines:
            clip = speak(spoken["say"])
            if not clip or len(clip) % 2:
                raise RuntimeError("Japanese TTS returned unexpected audio.")
            audio.append(clip)
            line_start = stamp()
            samples += len(clip) // 2
            timed.append({"start": line_start, "end": stamp(), "show": spoken["show"], "part": part})
            audio.append(silence)
            samples += len(silence) // 2
        segments.append({"kind": kind, "index": index, "start": start, "end": stamp()})
    episode.update(seconds=stamp(), lines_timed=timed, segments=segments)
    encoder = lameenc.Encoder()
    encoder.set_in_sample_rate(rate)
    encoder.set_channels(1)
    encoder.set_bit_rate(64)
    encoder.set_quality(2)
    return encoder.encode(b"".join(audio)) + encoder.flush()


def stage_previous(state, output, cutoff):
    entries = {e.get("id", e["date"]): e for e in read_json(ROOT / "episodes.json")}
    for folder in ("episodes", "audio"):
        (output / folder).mkdir()
    if state and (state / "episodes.json").is_file():
        for item in read_json(state / "episodes.json"):
            episode_id = item.get("id")
            if not episode_id or not re.fullmatch(r"\d{4}-\d{2}-\d{2}-\d{4}", episode_id):
                continue
            script = state / "episodes" / f"{episode_id}.json"
            if not script.is_file():
                raise ValueError(f"Missing saved script: {episode_id}")
            entries[episode_id] = item
            shutil.copyfile(script, output / "episodes" / script.name)
            audio = state / "audio" / f"{episode_id}.mp3"
            if item["date"] >= cutoff and audio.is_file():
                shutil.copyfile(audio, output / "audio" / audio.name)
    return entries


def broadcast(config, slot, state, output, now):
    date = now.date().isoformat()
    episode_id = f"{date}-{slot.replace(':', '')}"
    edition = {"id": episode_id, "date": date, "time": slot}
    station = read_json(ROOT / "station.json")
    keep_days = int(station["audio"]["keep_days"])
    entries = stage_previous(state, output, (now.date() - timedelta(days=keep_days)).isoformat())
    generated = False
    expected_voice = {"lilin": LILIN, "mei": MEI}.get(config.get("voice", "lilin"))
    if expected_voice is None:
        raise ValueError("news.json の voice は lilin または mei を指定してください。")
    saved_script = output / "episodes" / f"{episode_id}.json"
    has_audio = (output / "audio" / f"{episode_id}.mp3").is_file()
    if not has_audio or read_json(saved_script).get("voice_credit", MEI) != expected_voice:
        recent = (now.date() - timedelta(days=1)).isoformat()
        aired = {article_key(story["url"]) for key, item in entries.items() if item.get("id") and key != episode_id and item["date"] >= recent
                 for story in read_json(output / "episodes" / f"{key}.json")["news"] if not story.get("kind")}
        limit = int(config.get("max_stories", 4))
        if not 1 <= limit <= 8 or not config["sources"]:
            raise ValueError("Configure at least one source and 1–8 stories in news.json.")
        stories = collect_news(config["sources"], now=now, max_age_hours=int(config.get("max_age_hours", 24)),
                               limit=limit * 8)
        stories = [item for item in stories if article_key(item["url"]) not in aired]
        start, end = earthquake_window(now, date, slot, station["schedule"]["times"])
        sections = [world_weather(now), *earthquake_sections(start, end)]
        episode = make_episode(stories, edition, now, limit, sections)
        if episode:
            mp3 = synthesize(episode, config)
            (output / "audio" / f"{episode_id}.mp3").write_bytes(mp3)
            write_json(saved_script, episode)
            entries[episode_id] = {**edition, "title": episode["title"], "seconds": episode["seconds"]}
            generated = True
            print(f"Generated {episode_id}: {len(episode['news'])} segments, {episode['seconds']:.1f} seconds.")
        else:
            print("No new stories with usable RSS descriptions. Kept the previous editions.")
    else:
        print(f"Edition {episode_id} already exists. Reusing it.")
    write_json(output / "episodes.json", [entries[key] for key in sorted(entries, reverse=True)])
    return generated


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--slot", required=True, help="Scheduled time in JST, HH:MM")
    parser.add_argument("--config", type=Path, default=ROOT / "news.json")
    parser.add_argument("--state-dir", type=Path)
    parser.add_argument("--output-dir", required=True, type=Path, help="A new directory for the generated files")
    args = parser.parse_args()
    if not re.fullmatch(r"(?:[01]\d|2[0-3]):[0-5]\d", args.slot):
        parser.error("--slot must be a 24-hour time in HH:MM format")
    output = args.output_dir.resolve()
    if output.exists():
        parser.error("--output-dir must not exist")
    output.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(dir=output.parent) as temp:
        staged = Path(temp) / "broadcast"
        staged.mkdir()
        generated = broadcast(read_json(args.config), args.slot, args.state_dir, staged, datetime.now(JST))
        staged.rename(output)
    if github_output := os.environ.get("GITHUB_OUTPUT"):
        with open(github_output, "a", encoding="utf-8") as file:
            print(f"generated={str(generated).lower()}", file=file)


if __name__ == "__main__":
    main()
