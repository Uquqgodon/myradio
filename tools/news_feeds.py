"""Read RSS and Atom metadata for the daily bulletin."""

from collections import defaultdict
from datetime import datetime, timedelta, timezone
from email.utils import parsedate_to_datetime
from html.parser import HTMLParser
from http.client import HTTPException
from itertools import chain, zip_longest
import logging
from urllib.parse import parse_qsl, urljoin, urlsplit
from urllib.request import HTTPRedirectHandler, Request, build_opener
import xml.etree.ElementTree as ET


_MAX_FEED_BYTES = 4 * 1024 * 1024
_TIMEOUT_SECONDS = 12
_XML_BASE = "{http://www.w3.org/XML/1998/namespace}base"
_TRACKING_KEYS = {"fbclid", "gclid", "mc_cid", "mc_eid"}
_OLDEST = datetime.min.replace(tzinfo=timezone.utc)


class _HttpRedirects(HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        if not _http_url(newurl):
            raise ValueError("feed redirected outside HTTP(S)")
        return super().redirect_request(req, fp, code, msg, headers, newurl)


class _FeedTree(ET.TreeBuilder):
    def doctype(self, name, pubid, system):
        raise ValueError("feed contains a DOCTYPE declaration")


class _PlainText(HTMLParser):
    def __init__(self):
        super().__init__()
        self.parts = []
        self.hidden = False

    def handle_starttag(self, tag, attrs):
        if tag in {"script", "style"}:
            self.hidden = True
        if tag in {"br", "div", "li", "p"}:
            self.parts.append(" ")

    def handle_endtag(self, tag):
        if tag in {"script", "style"}:
            self.hidden = False
        if tag in {"div", "li", "p"}:
            self.parts.append(" ")

    def handle_data(self, data):
        if not self.hidden:
            self.parts.append(data)


def _plain(value, limit):
    parser = _PlainText()
    try:
        parser.feed(value)
        parser.close()
    except AssertionError:
        # Malformed HTML declarations can still leave usable text before them.
        pass
    return " ".join("".join(parser.parts).split())[:limit]


def _http_url(value, base=""):
    if not value or not value.strip():
        return None
    try:
        resolved = urljoin(base, value.strip())
        parts = urlsplit(resolved)
        if parts.scheme in {"http", "https"} and parts.hostname and parts.username is None:
            # Accessing .port also rejects malformed or out-of-range ports.
            if parts.port != 0 and not any(char.isspace() for char in resolved):
                return resolved
    except ValueError:
        pass
    return None


def article_key(url):
    parts = urlsplit(url)
    query = tuple(sorted(
        (name, value) for name, value in parse_qsl(parts.query, keep_blank_values=True)
        if not name.lower().startswith("utm_") and name.lower() not in _TRACKING_KEYS
    ))
    default_port = 80 if parts.scheme == "http" else 443
    port = None if parts.port == default_port else parts.port
    return parts.hostname, port, parts.path or "/", query


def _utc(value):
    return value.astimezone(timezone.utc) if value.tzinfo else value.replace(tzinfo=timezone.utc)


def _date(value):
    if not value:
        return None
    try:
        try:
            iso = value[:-1] + "+00:00" if value.endswith("Z") else value
            parsed = datetime.fromisoformat(iso)
        except ValueError:
            parsed = parsedate_to_datetime(value)
        return _utc(parsed)
    except (TypeError, ValueError, OverflowError):
        return None


def _tag(element):
    return element.tag.rsplit("}", 1)[-1].lower()


def _text(element):
    return "".join(element.itertext()).strip() if element is not None else ""


def _base(element, parent_url):
    return _http_url(element.get(_XML_BASE), parent_url) or parent_url


def _article_link(fields, base, atom):
    for link in fields["link"]:
        if atom and link.get("rel", "alternate") != "alternate":
            continue
        url = _http_url(link.get("href") or _text(link), _base(link, base))
        if url:
            return url
    for guid in fields["guid"]:
        if guid.get("isPermaLink", "true").lower() != "false":
            url = _http_url(_text(guid))
            if url:
                return url
    return None


def _read_feed(name, url, start, end):
    request = Request(url, headers={
        "User-Agent": "myradio-feed-reader/1.0",
        "Accept": "application/rss+xml, application/atom+xml, application/xml, text/xml, */*;q=0.1",
    })
    with build_opener(_HttpRedirects()).open(request, timeout=_TIMEOUT_SECONDS) as response:
        size = response.headers.get("Content-Length", "")
        if size.isdecimal() and int(size) > _MAX_FEED_BYTES:
            raise ValueError("feed exceeds the response size limit")
        content = response.read(_MAX_FEED_BYTES + 1)
        final_url = response.geturl()
    if len(content) > _MAX_FEED_BYTES:
        raise ValueError("feed exceeds the response size limit")

    root = ET.fromstring(content, parser=ET.XMLParser(target=_FeedTree()))
    root_tag = _tag(root)
    atom = root_tag == "feed"
    parent = root
    base = _base(root, final_url)
    if root_tag == "rss":
        parent = next((child for child in root if _tag(child) == "channel"), None)
        if parent is None:
            raise ValueError("RSS channel missing")
        base = _base(parent, base)
    elif root_tag not in {"feed", "rdf"}:
        raise ValueError("expected an RSS or Atom feed")

    items = []
    for entry in parent:
        if _tag(entry) != ("entry" if atom else "item"):
            continue
        fields = defaultdict(list)
        for field in entry:
            fields[_tag(field)].append(field)
        title = _plain(_text(next(iter(fields["title"]), None)), 300)
        link = _article_link(fields, _base(entry, base), atom)
        if not title or not link:
            continue
        date_fields = ("published", "updated") if atom else ("pubdate", "date", "published", "updated")
        dates = (_date(_text(field)) for key in date_fields for field in fields[key])
        published = next((value for value in dates if value is not None), None)
        if published is not None and not start <= published <= end:
            continue
        descriptions = (_plain(_text(field), 1200) for key in ("summary", "description") for field in fields[key])
        description = next((value for value in descriptions if value), "")
        items.append((published, {"source": name, "title": title, "url": link, "description": description}))
    return items


def _recency(row):
    return row[0] or _OLDEST


def collect_news(sources, *, now, max_age_hours, limit):
    """Return recent unique RSS/Atom items, using undated items only as fallback."""
    if limit <= 0:
        return []
    now = _utc(now)
    cutoff = now - timedelta(hours=max_age_hours)
    candidates = []
    for index, source in enumerate(sources):
        if not isinstance(source, dict):
            logging.warning("Skipping feed %d: expected a source object", index + 1)
            continue
        name = source.get("name", "")
        url = source.get("url", "")
        if not isinstance(name, str) or not name.strip() or not isinstance(url, str) or not _http_url(url):
            logging.warning("Skipping feed %d: name and HTTP(S) URL required", index + 1)
            continue
        try:
            items = _read_feed(name.strip(), url.strip(), cutoff, now)
        except (OSError, HTTPException, ValueError, LookupError, ET.ParseError) as error:
            logging.warning("Could not read feed %s: %s", name, error)
            continue
        candidates.extend((published, index, item) for published, item in items)

    # Dedupe before balancing so each copy goes to the feed with the newest metadata.
    dated, undated, seen = defaultdict(list), defaultdict(list), set()
    for published, index, item in sorted(candidates, key=_recency, reverse=True):
        key = article_key(item["url"])
        if key in seen:
            continue
        seen.add(key)
        (dated if published is not None else undated)[index].append((published, item))

    selected = []
    # Take one from each feed in each round, favouring the newest on a partial round.
    rounds = chain(zip_longest(*dated.values()), zip_longest(*undated.values()))
    for row in rounds:
        batch = sorted((entry for entry in row if entry is not None), key=_recency, reverse=True)
        selected.extend(batch[:limit - len(selected)])
        if len(selected) == limit:
            break
    return [item for _, item in sorted(selected, key=_recency, reverse=True)]
