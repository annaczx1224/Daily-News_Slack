#!/usr/bin/env python3
"""
SenaHill Weekly Fintech Digest  (no API / $0 to run)
====================================================
Pulls a week of global fintech news (AI / payments / digital assets / deals),
sorts it into sections using each source query's own topic tag (plus keyword
rules for general feeds), de-dupes, and posts a clean weekly read to Slack.

No AI API, no keys to buy. The only secret needed is a free Slack webhook.

Usage:
    python digest.py            # fetch, build, post to Slack
    python digest.py --dry-run  # fetch + build, print to console, don't post

Env var (required unless --dry-run):
    SLACK_WEBHOOK_URL   a Slack Incoming Webhook pointing at the target channel
"""

from __future__ import annotations

import argparse
import os
import re
import sys
import time
import urllib.parse
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo

import feedparser
import requests
import yaml

CONFIG_PATH = os.environ.get("DIGEST_CONFIG", "config.yaml")
GOOGLE_NEWS_BASE = "https://news.google.com/rss/search"
USER_AGENT = "SenaHill-Fintech-Digest/2.0 (+internal news bot)"
HTTP_TIMEOUT = 20


@dataclass
class Article:
    title: str
    url: str
    source: str
    published: datetime | None
    section: str | None = None  # set for Google News (tagged); None for RSS

    def key(self) -> str:
        t = self.title.lower().strip()
        if " - " in t:                       # drop "Headline - Publisher"
            t = t.rsplit(" - ", 1)[0].strip()
        return re.sub(r"[^a-z0-9 ]", "", t)[:70]


# --------------------------------------------------------------------------- #
def load_config(path: str) -> dict:
    with open(path, "r", encoding="utf-8") as fh:
        return yaml.safe_load(fh)


# --------------------------------------------------------------------------- #
# Fetching
# --------------------------------------------------------------------------- #
def _parse_feed(url: str, section: str | None) -> list[Article]:
    out: list[Article] = []
    try:
        parsed = feedparser.parse(url, agent=USER_AGENT)
    except Exception as exc:
        print(f"  ! feed error ({url[:60]}): {exc}", file=sys.stderr)
        return out

    feed_title = parsed.feed.get("title", "") if getattr(parsed, "feed", None) else ""
    for entry in getattr(parsed, "entries", []):
        title = (entry.get("title") or "").strip()
        link = (entry.get("link") or "").strip()
        if not title or not link:
            continue

        published = None
        for f in ("published_parsed", "updated_parsed"):
            tm = entry.get(f)
            if tm:
                published = datetime.fromtimestamp(time.mktime(tm), tz=timezone.utc)
                break

        source = ""
        if isinstance(entry.get("source"), dict):
            source = entry["source"].get("title", "")
        if not source and " - " in title:
            source = title.rsplit(" - ", 1)[-1].strip()
        if not source:
            source = feed_title

        out.append(Article(title=title, url=link, source=source,
                            published=published, section=section))
    return out


def build_google_news_url(q: str, gl: str, lookback_days: int) -> str:
    q = re.sub(r"\s+when:\S+", "", q).strip()          # remove any stale window
    q = f"{q} when:{lookback_days}d"                    # keep in sync with lookback
    params = {"q": q, "hl": "en-US", "gl": gl, "ceid": f"{gl}:en"}
    return f"{GOOGLE_NEWS_BASE}?{urllib.parse.urlencode(params)}"


def fetch_all(cfg: dict) -> list[Article]:
    days = cfg["settings"]["lookback_days"]
    articles: list[Article] = []

    print("Fetching Google News queries...")
    for item in cfg.get("google_news_queries", []):
        url = build_google_news_url(item["q"], item.get("gl", "US"), days)
        got = _parse_feed(url, item["section"])
        print(f"  · {item.get('gl','US')} {item['section'][:18]:<18} {len(got):>3} items")
        articles.extend(got)

    print("Fetching direct RSS feeds...")
    for url in cfg.get("rss_feeds", []):
        got = _parse_feed(url, None)
        print(f"  · {len(got):>3} items  <- {url[:50]}")
        articles.extend(got)

    return articles


# --------------------------------------------------------------------------- #
# Classify (for general RSS), filter, de-dupe
# --------------------------------------------------------------------------- #
def classify(article: Article, cfg: dict) -> str | None:
    """Return the best-fit section for an untagged (RSS) article, or None."""
    if article.section:
        return article.section
    text = article.title.lower()
    scores: dict[str, int] = {}
    for sec, words in cfg.get("section_keywords", {}).items():
        hits = sum(1 for w in words if w in text)
        if hits:
            scores[sec] = hits
    if not scores:
        return None
    best = max(scores.values())
    tied = [s for s, v in scores.items() if v == best]
    if len(tied) == 1:
        return tied[0]
    for sec in cfg.get("section_priority", cfg["sections"]):   # tie-break
        if sec in tied:
            return sec
    return tied[0]


def prepare(articles: list[Article], cfg: dict) -> dict[str, list[Article]]:
    days = cfg["settings"]["lookback_days"]
    cutoff = datetime.now(timezone.utc) - timedelta(days=days)
    seen: set[str] = set()

    # freshest first so de-dupe keeps the newest copy
    def rk(a: Article):
        return a.published or datetime.min.replace(tzinfo=timezone.utc)

    buckets: dict[str, list[Article]] = {s: [] for s in cfg["sections"]}
    cap = cfg["settings"]["max_stories_per_section"]

    for art in sorted(articles, key=rk, reverse=True):
        if art.published and art.published < cutoff:
            continue
        k = art.key()
        if len(k) < 8 or k in seen:
            continue
        sec = classify(art, cfg)
        if not sec or sec not in buckets:
            continue
        if len(buckets[sec]) >= cap:
            continue
        seen.add(k)
        buckets[sec].append(art)

    return buckets


def top_highlights(buckets: dict[str, list[Article]], n: int) -> list[Article]:
    if n <= 0:
        return []
    everything = [a for lst in buckets.values() for a in lst]
    everything.sort(key=lambda a: a.published or datetime.min.replace(tzinfo=timezone.utc),
                    reverse=True)
    return everything[:n]


# --------------------------------------------------------------------------- #
# Slack formatting & posting
# --------------------------------------------------------------------------- #
def _clip(t: str, n: int) -> str:
    return t if len(t) <= n else t[: n - 1] + "…"


def _datestr(a: Article, tz: ZoneInfo) -> str:
    if not a.published:
        return ""
    return a.published.astimezone(tz).strftime("%b %-d")


def build_slack_blocks(buckets: dict[str, list[Article]], cfg: dict) -> list[dict]:
    tz = ZoneInfo(cfg["settings"].get("timezone", "America/New_York"))
    now = datetime.now(tz)
    start = (now - timedelta(days=cfg["settings"]["lookback_days"])).strftime("%b %-d")
    end = now.strftime("%b %-d, %Y")
    header = cfg["settings"]["header"].format(start=start, end=end)

    blocks: list[dict] = [
        {"type": "header", "text": {"type": "plain_text", "text": _clip(header, 150)}}
    ]

    highlights = top_highlights(buckets, cfg["settings"].get("highlights_count", 0))
    if highlights:
        lines = [f"• *<{a.url}|{_clip(a.title, 140)}>*" for a in highlights]
        blocks.append({
            "type": "section",
            "text": {"type": "mrkdwn", "text": _clip("*This week's top reads*\n" + "\n".join(lines), 2900)},
        })
    blocks.append({"type": "divider"})

    for section in cfg["sections"]:
        stories = buckets.get(section, [])
        if not stories:
            continue
        blocks.append({"type": "header",
                       "text": {"type": "plain_text", "text": _clip(section, 150)}})
        for a in stories:
            meta = " · ".join(x for x in (a.source, _datestr(a, tz)) if x)
            text = f"*<{a.url}|{_clip(a.title, 200)}>*"
            if meta:
                text += f"\n_{_clip(meta, 200)}_"
            blocks.append({"type": "section",
                           "text": {"type": "mrkdwn", "text": _clip(text, 2900)}})
        blocks.append({"type": "divider"})

    blocks.append({"type": "context", "elements": [{
        "type": "mrkdwn",
        "text": "Auto-generated weekly · free RSS + Google News · no AI/API"}]})
    return blocks


def post_to_slack(blocks: list[dict], webhook: str) -> None:
    MAX = 48
    chunks = [blocks[i:i + MAX] for i in range(0, len(blocks), MAX)] or [[]]
    for i, chunk in enumerate(chunks):
        r = requests.post(webhook, json={"blocks": chunk}, timeout=HTTP_TIMEOUT,
                          headers={"Content-Type": "application/json"})
        if r.status_code != 200:
            raise RuntimeError(f"Slack post failed ({r.status_code}): {r.text}")
        if i < len(chunks) - 1:
            time.sleep(1)
    print(f"Posted {len(blocks)} blocks in {len(chunks)} message(s).")


def print_preview(buckets: dict[str, list[Article]], cfg: dict) -> None:
    tz = ZoneInfo(cfg["settings"].get("timezone", "America/New_York"))
    hl = top_highlights(buckets, cfg["settings"].get("highlights_count", 0))
    if hl:
        print("\nTOP READS")
        for a in hl:
            print(f"  • {a.title}  ({_datestr(a, tz)})")
    for section in cfg["sections"]:
        stories = buckets.get(section, [])
        if not stories:
            continue
        print(f"\n{section}  ({len(stories)})")
        print("-" * 70)
        for a in stories:
            meta = " · ".join(x for x in (a.source, _datestr(a, tz)) if x)
            print(f"  • {a.title}")
            print(f"      {meta}")
            print(f"      {a.url}")


# --------------------------------------------------------------------------- #
def main() -> int:
    ap = argparse.ArgumentParser(description="SenaHill weekly fintech digest")
    ap.add_argument("--dry-run", action="store_true",
                    help="build and print, but do not post to Slack")
    args = ap.parse_args()

    cfg = load_config(CONFIG_PATH)
    articles = fetch_all(cfg)
    print(f"\nFetched {len(articles)} raw items.")
    buckets = prepare(articles, cfg)
    total = sum(len(v) for v in buckets.values())
    print(f"{total} stories after filter/de-dupe/sort "
          f"({', '.join(f'{s.split()[-1]}:{len(v)}' for s, v in buckets.items())}).")

    if total == 0:
        print("Nothing in the lookback window — not posting.")
        return 0

    blocks = build_slack_blocks(buckets, cfg)

    if args.dry_run:
        print_preview(buckets, cfg)
        print(f"\n[dry-run] Built {len(blocks)} Slack blocks; not posting.")
        return 0

    webhook = os.environ.get("SLACK_WEBHOOK_URL")
    if not webhook:
        print("ERROR: SLACK_WEBHOOK_URL not set.", file=sys.stderr)
        return 2
    post_to_slack(blocks, webhook)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
