"""
TOKINDLE - Core FastAPI backend.
Extract WeChat articles (from URL or raw HTML), generate EPUB, save to output/.
An external RPA agent (e.g. OpenClaw) handles upload to Amazon.
"""

import html
import io
import re
import traceback
import uuid
from pathlib import Path
from typing import Optional

import requests
from bs4 import BeautifulSoup, Tag
from ebooklib import epub
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel

app = FastAPI(
    title="TOKINDLE",
    description="Convert WeChat articles to EPUB; save to output/ and return file paths",
    version="0.1.0",
)

OUTPUT_DIR = Path("output")

WECHAT_REFERER = "https://mp.weixin.qq.com/"
FETCH_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    ),
    "Referer": WECHAT_REFERER,
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
    "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
}
FETCH_TIMEOUT = (15, 60)  # (connect, read) seconds
IMAGE_TIMEOUT = (10, 45)

_EXT_BY_HINT = {".png": ".png", ".gif": ".gif", ".webp": ".webp"}

# ---------------------------------------------------------------------------
# Request / response models
# ---------------------------------------------------------------------------


class ParseUrlRequest(BaseModel):
    url: str


class ParseHtmlRequest(BaseModel):
    title: str
    html_content: str


# ---------------------------------------------------------------------------
# Output helpers
# ---------------------------------------------------------------------------


def _safe_filename(title: str) -> str:
    """Filesystem-safe basename (no extension), max 50 chars."""
    return re.sub(r"[^\w\s\-]", "", title, flags=re.UNICODE)[:50].strip() or "article"


def save_epub(epub_bytes: bytes, title: str) -> str:
    """Write EPUB to output/ and return its absolute path."""
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    path = OUTPUT_DIR.resolve() / f"{_safe_filename(title)}.epub"
    path.write_bytes(epub_bytes)
    return str(path)


# ---------------------------------------------------------------------------
# HTTP helpers
# ---------------------------------------------------------------------------


def fetch_wechat_article(url: str) -> str:
    resp = requests.get(url, headers=FETCH_HEADERS, timeout=FETCH_TIMEOUT)
    resp.raise_for_status()
    resp.encoding = resp.apparent_encoding or "utf-8"
    return resp.text


def download_image(url: str) -> bytes:
    resp = requests.get(
        url, headers={**FETCH_HEADERS, "Referer": WECHAT_REFERER}, timeout=IMAGE_TIMEOUT
    )
    resp.raise_for_status()
    return resp.content


# ---------------------------------------------------------------------------
# HTML parsing
# ---------------------------------------------------------------------------


def _strip_hidden_styles(root: Tag) -> None:
    """Remove visibility:hidden / opacity:0 / display:none from *root* and all descendants."""
    _HIDE_PATTERNS = (
        re.compile(r"visibility:\s*hidden", re.IGNORECASE),
        re.compile(r"opacity:\s*0\b", re.IGNORECASE),
        re.compile(r"display:\s*none", re.IGNORECASE),
    )
    _EMPTY_SEMI = re.compile(r";\s*;+")
    for el in [root, *root.find_all(True)]:
        style = el.get("style")
        if not style:
            continue
        for pat in _HIDE_PATTERNS:
            style = pat.sub("", style)
        style = _EMPTY_SEMI.sub(";", style).strip("; \t")
        if style:
            el["style"] = style
        else:
            del el["style"]


def _find_wechat_content_div(soup: BeautifulSoup) -> Optional[Tag]:
    """Locate the main article body across known WeChat template variants."""
    div = soup.find("div", class_="rich_media_content", id="js_content")
    if div:
        return div
    div = soup.find("div", id="js_content")
    if div:
        return div
    return soup.find(
        "div",
        class_=lambda c: c and "rich_media_content" in (c if isinstance(c, str) else " ".join(c)),
    )


def parse_wechat_html(raw_html: str) -> tuple[str, Tag]:
    """
    Extract (title, content_div) from a full WeChat article page.
    Raises ValueError when the content container is missing.
    """
    soup = BeautifulSoup(raw_html, "html.parser")

    og = soup.find("meta", property="og:title")
    title = og["content"].strip() if og and og.get("content") else None
    if not title:
        t = soup.find("title")
        title = t.get_text(strip=True) if t else "Untitled"

    div = _find_wechat_content_div(soup)
    if not div:
        raise ValueError(
            "Article content container not found "
            "(expected div#js_content or .rich_media_content)."
        )
    _strip_hidden_styles(div)
    return title, div


def parse_raw_html(html_content: str) -> Tag:
    """
    Parse arbitrary HTML (e.g. from Chrome Extension).
    Tries the WeChat content div; falls back to <body> or the whole document.
    """
    soup = BeautifulSoup(html_content, "html.parser")
    div = _find_wechat_content_div(soup)
    if not div:
        div = soup.find("body") or soup
    _strip_hidden_styles(div)
    return div


# ---------------------------------------------------------------------------
# EPUB generation (shared by both endpoints)
# ---------------------------------------------------------------------------


def _guess_ext(url: str) -> str:
    stem = url.split("?")[0].lower()
    for suffix, ext in _EXT_BY_HINT.items():
        if stem.endswith(suffix):
            return ext
    return ".jpg"


def build_epub(title: str, content: Tag) -> bytes:
    """Process images (data-src → download with Referer → embed) and return EPUB bytes."""
    book = epub.EpubBook()
    book.set_identifier(f"tokindle-{uuid.uuid4().hex[:12]}")
    book.set_title(title)
    book.set_language("en")

    seen: dict[str, str] = {}
    idx = 0
    for img in content.find_all("img"):
        image_url = (img.get("data-src") or img.get("src") or "").strip()
        if not image_url or image_url.startswith("data:"):
            continue
        if image_url in seen:
            img["src"] = seen[image_url]
            img.attrs.pop("data-src", None)
            continue
        try:
            data = download_image(image_url)
        except Exception:
            if img.get("data-src"):
                img["src"] = image_url
            img.attrs.pop("data-src", None)
            continue

        fname = f"images/img_{idx}{_guess_ext(image_url)}"
        idx += 1
        book.add_item(epub.EpubImage(uid=f"img-{idx}", file_name=fname, content=data))
        seen[image_url] = fname
        img["src"] = fname
        img.attrs.pop("data-src", None)

    # EbookLib rejects <?xml …?> in Unicode strings, so omit it.
    title_esc = html.escape(title, quote=True)
    chapter_html = (
        '<!DOCTYPE html>\n'
        '<html xmlns="http://www.w3.org/1999/xhtml"'
        ' xmlns:epub="http://www.idpf.org/2007/ops">\n'
        f"<head><meta charset=\"utf-8\"/><title>{title_esc}</title></head>\n"
        f"<body>\n{content}\n</body>\n</html>"
    )
    chapter = epub.EpubHtml(title=title, file_name="chapter.xhtml", content=chapter_html)
    book.add_item(chapter)
    book.toc = (chapter,)
    book.spine = ["nav", chapter]

    buf = io.BytesIO()
    epub.write_epub(buf, book, {})
    return buf.getvalue()


# ---------------------------------------------------------------------------
# High-level pipelines
# ---------------------------------------------------------------------------


def create_epub_from_url(url: str) -> tuple[str, bytes]:
    raw = fetch_wechat_article(url)
    title, content = parse_wechat_html(raw)
    return title, build_epub(title, content)


def create_epub_from_html(title: str, html_content: str) -> tuple[str, bytes]:
    content = parse_raw_html(html_content)
    return title, build_epub(title, content)


# ---------------------------------------------------------------------------
# API endpoints
# ---------------------------------------------------------------------------


@app.get("/ping")
def ping():
    return {"ping": "pong"}


@app.post("/parse-url")
def endpoint_parse_url(body: ParseUrlRequest):
    """Fetch WeChat article → EPUB → save to output/ → return path."""
    try:
        title, epub_bytes = create_epub_from_url(body.url)
    except requests.RequestException as e:
        raise HTTPException(status_code=502, detail=f"Failed to fetch URL: {e}")
    except ValueError as e:
        raise HTTPException(status_code=422, detail=str(e))
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Internal error: {type(e).__name__}: {e}\n\n{traceback.format_exc()}",
        )
    return {"success": True, "path": save_epub(epub_bytes, title), "title": title}


@app.post("/parse-html")
def endpoint_parse_html(body: ParseHtmlRequest):
    """Parse provided HTML (no fetch) → EPUB → save to output/ → return path."""
    try:
        _, epub_bytes = create_epub_from_html(body.title, body.html_content)
    except ValueError as e:
        raise HTTPException(status_code=422, detail=str(e))
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Internal error: {type(e).__name__}: {e}\n\n{traceback.format_exc()}",
        )
    return {"success": True, "path": save_epub(epub_bytes, body.title), "title": body.title}
