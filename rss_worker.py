#!/usr/bin/env python3
"""
TOKINDLE — RSS Worker (long-running daemon).
Periodically fetches RSS feeds from feeds.json, POSTs new article URLs to
the FastAPI backend /parse-url. Managed by admin_ui.py or run standalone.
Handles SIGTERM gracefully for clean shutdown.

Usage:
  python rss_worker.py
  TOKINDLE_BACKEND_URL=http://127.0.0.1:8000 python rss_worker.py
"""

import json
import logging
import os
import signal
import sys
import time
from pathlib import Path
from typing import Optional

import feedparser
import requests

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [RSS-WORKER] %(levelname)s %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger(__name__)

BASE_DIR = Path(__file__).resolve().parent
FEEDS_PATH = BASE_DIR / "feeds.json"
SEEN_PATH = BASE_DIR / "config" / "rss_seen.txt"
PID_PATH = BASE_DIR / "logs" / "rss_worker.pid"
DEFAULT_BACKEND = "http://127.0.0.1:8000"
REQUEST_TIMEOUT = (10, 120)
DEFAULT_INTERVAL = 60

_shutdown = False


def _handle_signal(signum, frame):
    global _shutdown
    logger.info("Received signal %s — shutting down after current cycle.", signum)
    _shutdown = True


signal.signal(signal.SIGTERM, _handle_signal)
signal.signal(signal.SIGINT, _handle_signal)


def _write_pid():
    PID_PATH.parent.mkdir(parents=True, exist_ok=True)
    PID_PATH.write_text(str(os.getpid()), encoding="utf-8")


def _remove_pid():
    try:
        PID_PATH.unlink(missing_ok=True)
    except OSError:
        pass


def load_feeds() -> dict:
    if not FEEDS_PATH.exists():
        return {"feeds": [], "interval_minutes": DEFAULT_INTERVAL}
    try:
        data = json.loads(FEEDS_PATH.read_text(encoding="utf-8"))
        data.setdefault("feeds", [])
        data.setdefault("interval_minutes", DEFAULT_INTERVAL)
        return data
    except (json.JSONDecodeError, OSError) as exc:
        logger.warning("Cannot read feeds.json: %s", exc)
        return {"feeds": [], "interval_minutes": DEFAULT_INTERVAL}


def load_seen() -> set:
    if not SEEN_PATH.exists():
        return set()
    return {
        line.strip()
        for line in SEEN_PATH.read_text(encoding="utf-8").splitlines()
        if line.strip()
    }


_MAX_SEEN_LINES = 2000


def append_seen(url: str) -> None:
    SEEN_PATH.parent.mkdir(parents=True, exist_ok=True)
    with open(SEEN_PATH, "a", encoding="utf-8") as fh:
        fh.write(url.strip() + "\n")
    _truncate_seen()


def _truncate_seen() -> None:
    """Keep only the most recent _MAX_SEEN_LINES entries to prevent unbounded growth."""
    try:
        lines = SEEN_PATH.read_text(encoding="utf-8").splitlines()
        if len(lines) > _MAX_SEEN_LINES:
            SEEN_PATH.write_text("\n".join(lines[-_MAX_SEEN_LINES:]) + "\n", encoding="utf-8")
    except OSError:
        pass


def _entry_link(entry) -> Optional[str]:
    if getattr(entry, "link", None):
        return entry.link
    for lnk in getattr(entry, "links", []) or []:
        if lnk.get("href"):
            return lnk["href"]
    return None


def _post_with_retry(url: str, payload: dict, retries: int = 2) -> requests.Response:
    for attempt in range(retries + 1):
        try:
            resp = requests.post(url, json=payload, timeout=REQUEST_TIMEOUT)
            resp.raise_for_status()
            return resp
        except requests.RequestException:
            if attempt >= retries:
                raise
            time.sleep(2 * (attempt + 1))


def run_once(backend_url: str, max_per_feed: int = 10) -> None:
    data = load_feeds()
    feeds = data.get("feeds", [])
    if not feeds:
        logger.info("No feeds in feeds.json — nothing to do.")
        return

    seen = load_seen()
    sent, failed = 0, 0

    for feed_cfg in feeds:
        if _shutdown:
            break
        feed_url = feed_cfg.get("url", "").strip()
        feed_name = feed_cfg.get("name", feed_url[:40])
        if not feed_url:
            continue
        try:
            parsed = feedparser.parse(feed_url)
        except Exception as exc:
            logger.exception("Feed fetch failed '%s': %s", feed_name, exc)
            continue

        for entry in (getattr(parsed, "entries", None) or [])[:max_per_feed]:
            if _shutdown:
                break
            link = _entry_link(entry)
            if not link or link in seen:
                continue
            try:
                resp = _post_with_retry(f"{backend_url}/parse-url", {"url": link})
                result = resp.json()
                logger.info("[%s] OK %s -> %s", feed_name, link[:60], result.get("path", "")[:50])
                seen.add(link)
                append_seen(link)
                sent += 1
            except requests.RequestException as exc:
                logger.warning("[%s] Backend error for %s: %s", feed_name, link[:60], exc)
                failed += 1
            except Exception as exc:
                logger.exception("[%s] Unexpected error for %s: %s", feed_name, link[:60], exc)
                failed += 1

    logger.info("Cycle done: %d sent, %d failed.", sent, failed)


def main() -> None:
    backend = os.environ.get("TOKINDLE_BACKEND_URL", DEFAULT_BACKEND).rstrip("/")
    logger.info("RSS Worker starting. PID=%d  Backend=%s  feeds=%s", os.getpid(), backend, FEEDS_PATH)
    _write_pid()

    try:
        while not _shutdown:
            data = load_feeds()
            interval = max(data.get("interval_minutes", DEFAULT_INTERVAL), 1)
            logger.info("Running RSS check (next in %d min)...", interval)
            try:
                run_once(backend)
            except Exception as exc:
                logger.exception("Unhandled error: %s", exc)

            for _ in range(interval * 60):
                if _shutdown:
                    break
                time.sleep(1)
    finally:
        _remove_pid()
        logger.info("RSS Worker stopped.")


if __name__ == "__main__":
    main()
