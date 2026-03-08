#!/usr/bin/env python3
"""
RSS automation for TOKINDLE: fetch RSS feeds, send article URLs to the backend /parse-url.
Run via cron or launchd. Backend must be running (e.g. uvicorn main:app --host 0.0.0.0 --port 8000).

Usage:
  python scripts/rss_job.py [--config CONFIG] [--state STATE] [--max-per-feed N]
  TOKINDLE_BACKEND_URL=http://127.0.0.1:8000 python scripts/rss_job.py

Config file: one feed URL per line; lines starting with # are ignored.
State file: stores already-processed URLs (one per line) so we don't re-send.
"""

import argparse
import logging
import os
import sys
from pathlib import Path

import feedparser
import requests

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [RSS] %(levelname)s %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger(__name__)

DEFAULT_BACKEND = "http://127.0.0.1:8000"
REQUEST_TIMEOUT = (10, 120)  # connect, read


def load_lines(path: Path, allow_missing: bool = True) -> list[str]:
    if not path.exists():
        if allow_missing:
            return []
        raise FileNotFoundError(path)
    return [line.strip() for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def load_feed_urls(config_path: Path) -> list[str]:
    lines = load_lines(config_path, allow_missing=False)
    return [line for line in lines if not line.startswith("#")]


def load_seen(state_path: Path) -> set[str]:
    return set(load_lines(state_path))


def append_seen(state_path: Path, url: str) -> None:
    state_path.parent.mkdir(parents=True, exist_ok=True)
    with open(state_path, "a", encoding="utf-8") as f:
        f.write(url.strip() + "\n")


def get_entry_links(entry) -> list[str]:
    """Get link(s) from a feed entry. Prefer 'link', then 'links'."""
    if getattr(entry, "link", None):
        return [entry.link]
    links = getattr(entry, "links", []) or []
    return [l.get("href") for l in links if l.get("href")]


def run(
    backend_url: str,
    config_path: Path,
    state_path: Path,
    max_per_feed: int,
) -> None:
    backend_url = backend_url.rstrip("/")
    feed_urls = load_feed_urls(config_path)
    if not feed_urls:
        logger.warning("No feed URLs in %s", config_path)
        return

    seen = load_seen(state_path)
    sent = 0
    failed = 0

    for feed_url in feed_urls:
        try:
            parsed = feedparser.parse(feed_url)
        except Exception as e:
            logger.exception("Failed to fetch feed %s: %s", feed_url, e)
            continue

        entries = getattr(parsed, "entries", []) or []
        # Process newest first, up to max_per_feed per feed
        for entry in entries[:max_per_feed]:
            for link in get_entry_links(entry):
                if link in seen:
                    break  # one link per entry
                try:
                    r = requests.post(
                        f"{backend_url}/parse-url",
                        json={"url": link},
                        timeout=REQUEST_TIMEOUT,
                    )
                    r.raise_for_status()
                    data = r.json()
                    logger.info("OK %s -> %s", link[:60], data.get("path", "")[:50])
                    seen.add(link)
                    append_seen(state_path, link)
                    sent += 1
                except requests.RequestException as e:
                    logger.warning("Backend error for %s: %s", link[:50], e)
                    failed += 1
                except Exception as e:
                    logger.exception("Unexpected error for %s: %s", link[:50], e)
                    failed += 1
                break  # one link per entry

    logger.info("Done: %d sent, %d failed", sent, failed)


def main() -> None:
    base = Path(__file__).resolve().parent.parent
    default_config = base / "config" / "rss_feeds.txt"
    default_state = base / "config" / "rss_seen.txt"

    p = argparse.ArgumentParser(description="TOKINDLE RSS job: fetch feeds, POST URLs to backend.")
    p.add_argument("--config", type=Path, default=default_config, help="Feed list (one URL per line)")
    p.add_argument("--state", type=Path, default=default_state, help="Seen-URLs state file")
    p.add_argument("--max-per-feed", type=int, default=10, help="Max entries to process per feed per run")
    args = p.parse_args()

    backend = os.environ.get("TOKINDLE_BACKEND_URL", DEFAULT_BACKEND)
    if not args.config.exists():
        logger.error("Config not found: %s. Copy config/rss_feeds.txt.example to config/rss_feeds.txt and add feed URLs.", args.config)
        sys.exit(1)

    run(backend, args.config, args.state, args.max_per_feed)


if __name__ == "__main__":
    main()
