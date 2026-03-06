"""
TOKINDLE - Core FastAPI backend.
Extract WeChat articles (from URL or raw HTML), generate EPUB, save to output/,
and send to Kindle via Gmail SMTP. All images are converted to JPEG to avoid Amazon E999.
"""

import html
import io
import logging
import os
import re
import smtplib
import ssl
import tempfile
import traceback
import uuid
from email.mime.application import MIMEApplication
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from pathlib import Path
from typing import Optional

import requests
from bs4 import BeautifulSoup, Tag
from dotenv import load_dotenv
from ebooklib import epub
from fastapi import FastAPI, File, HTTPException, UploadFile
from PIL import Image
from pydantic import BaseModel

load_dotenv()

logger = logging.getLogger(__name__)
_handler = logging.StreamHandler()
_handler.setFormatter(logging.Formatter("%(levelname)s [TOKINDLE] %(message)s"))
logger.addHandler(_handler)
logger.setLevel(logging.INFO)

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


def send_to_kindle(epub_path: str, title: str) -> tuple[bool, Optional[str]]:
    """
    Send EPUB to Kindle via Gmail SMTP. Subject must be "Convert" for Kindle conversion.
    Returns (success, error_message). Uses env: SMTP_SERVER, SMTP_PORT, SENDER_EMAIL,
    SENDER_PASSWORD (Gmail App Password), KINDLE_EMAIL.
    """
    server = os.environ.get("SMTP_SERVER", "smtp.gmail.com").strip()
    port = int(os.environ.get("SMTP_PORT", "587"))
    sender = os.environ.get("SENDER_EMAIL", "").strip()
    password = os.environ.get("SENDER_PASSWORD", "").strip()
    kindle_email = os.environ.get("KINDLE_EMAIL", "").strip()
    if not all([sender, password, kindle_email]):
        msg = "SMTP not configured: set SENDER_EMAIL, SENDER_PASSWORD, KINDLE_EMAIL in .env"
        logger.warning("TOKINDLE send skipped: %s", msg)
        return False, msg
    path = Path(epub_path)
    if not path.is_file():
        err = f"EPUB file not found: {epub_path}"
        logger.error(err)
        return False, err
    try:
        with open(path, "rb") as f:
            epub_data = f.read()
    except OSError as e:
        err = f"Cannot read EPUB: {e}"
        logger.error(err)
        return False, err
    msg = MIMEMultipart()
    msg["Subject"] = "Convert"
    msg["From"] = sender
    msg["To"] = kindle_email
    msg.attach(MIMEText("Sent from TOKINDLE.", "plain"))
    attachment_filename = _safe_filename(title) + ".epub"
    if attachment_filename == ".epub":
        attachment_filename = "article.epub"
    attachment = MIMEApplication(epub_data, _subtype="epub+zip")
    attachment.add_header(
        "Content-Disposition", "attachment", filename=attachment_filename
    )
    msg.attach(attachment)
    try:
        logger.info("TOKINDLE: Sending EPUB to Kindle (%s)...", kindle_email)
        ctx = ssl.create_default_context()
        with smtplib.SMTP(server, port) as smtp:
            smtp.starttls(context=ctx)
            smtp.login(sender, password)
            smtp.sendmail(sender, [kindle_email], msg.as_string())
        logger.info(
            "TOKINDLE: sendmail() OK — message handed to %s. Check Gmail Sent & Kindle.",
            server,
        )
        return True, None
    except smtplib.SMTPException as e:
        err = f"SMTP error: {e}"
        logger.exception(err)
        return False, err
    except Exception as e:
        err = f"Send to Kindle failed: {e}"
        logger.exception(err)
        return False, err


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


def _image_to_jpeg(raw_bytes: bytes) -> Optional[bytes]:
    """
    Convert any image (including WebP) to JPEG for EPUB. Kindle rejects WebP (E999).
    Returns None if conversion fails (e.g. corrupt data); caller should skip the image.
    """
    try:
        img = Image.open(io.BytesIO(raw_bytes))
        if img.mode in ("RGBA", "P", "LA"):
            img = img.convert("RGB")
        elif img.mode != "RGB":
            img = img.convert("RGB")
        buf = io.BytesIO()
        img.save(buf, format="JPEG", quality=90)
        return buf.getvalue()
    except Exception as e:
        logger.warning("Image to JPEG conversion failed: %s", e)
        return None


# ---------------------------------------------------------------------------
# HTML parsing
# ---------------------------------------------------------------------------


def _deep_clean_dom(root: Tag) -> None:
    """Remove elements that Kindle's parser rejects (E999): script, style, iframe, video, audio,
    noscript, svg, and WeChat custom elements (mp-*)."""
    to_remove = (
        "script", "style", "iframe", "video", "audio", "noscript", "svg",
    )
    for tag_name in to_remove:
        for tag in root.find_all(tag_name):
            tag.decompose()
    for tag in root.find_all(True):
        if tag.name and tag.name.startswith("mp-"):
            tag.decompose()


def _sanitize_links_and_styles(root: Tag) -> None:
    """Replace javascript: links and strip external url() from style to avoid Kindle E999."""
    for a in root.find_all("a", href=True):
        h = (a["href"] or "").strip().lower()
        if h in ("javascript:;", "javascript:"):
            a["href"] = "#"
    _URL_STYLE = re.compile(
        r"background-image:\s*url\s*\(\s*[\'\"]?https?://[^\)]*\)\s*;?",
        re.IGNORECASE,
    )
    for el in [root, *root.find_all(True)]:
        style = el.get("style")
        if not style:
            continue
        style = _URL_STYLE.sub("", style).strip().rstrip(";")
        if style:
            el["style"] = style
        else:
            del el["style"]


def _to_xhtml_string(tag: Tag) -> str:
    """Serialize tag to XHTML with self-closing img and br (Kindle E999 fix)."""
    raw = str(tag)
    # BeautifulSoup may output <img ...> and <br>; Amazon's parser requires <img ... /> and <br/>
    raw = re.sub(r"<img(\s*[^>]*?)(?<!/)>", r"<img\1/>", raw)
    raw = re.sub(r"<br(\s*[^>]*?)(?<!/)>", r"<br\1/>", raw)
    return raw


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


def build_epub(title: str, content: Tag) -> bytes:
    """
    Process images (data-src → download with Referer → convert to JPEG) and return EPUB bytes.
    All images are stored as .jpg to avoid Kindle E999 (WebP rejection).
    DOM is deep-cleaned and serialized as strict XHTML for Amazon's parser.
    """
    _deep_clean_dom(content)
    _sanitize_links_and_styles(content)

    book = epub.EpubBook()
    book.set_identifier(f"tokindle-{uuid.uuid4().hex[:12]}")
    book.set_title(title)
    book.set_language("en")

    seen: dict[str, str] = {}
    idx = 0
    for img in list(content.find_all("img")):
        image_url = (img.get("data-src") or img.get("src") or "").strip()
        if not image_url:
            continue
        if image_url.startswith("data:"):
            img.decompose()
            continue
        if image_url in seen:
            img["src"] = seen[image_url]
            img.attrs.pop("data-src", None)
            continue
        try:
            raw = download_image(image_url)
        except Exception:
            if img.get("data-src"):
                img["src"] = image_url
            img.attrs.pop("data-src", None)
            continue

        data = _image_to_jpeg(raw)
        if not data:
            if img.get("data-src"):
                img["src"] = image_url
            img.attrs.pop("data-src", None)
            continue

        fname = f"images/img_{idx}.jpg"
        idx += 1
        book.add_item(epub.EpubImage(uid=f"img-{idx}", file_name=fname, content=data))
        seen[image_url] = fname
        img["src"] = fname
        img.attrs.pop("data-src", None)

    # Strict XHTML: self-closing img/br so Amazon's parser does not E999.
    title_esc = html.escape(title, quote=True)
    body_inner = _to_xhtml_string(content)
    chapter_html = (
        '<!DOCTYPE html>\n'
        '<html xmlns="http://www.w3.org/1999/xhtml"'
        ' xmlns:epub="http://www.idpf.org/2007/ops">\n'
        f"<head><meta charset=\"utf-8\"/><title>{title_esc}</title></head>\n"
        f"<body>\n{body_inner}\n</body>\n</html>"
    )
    chapter = epub.EpubHtml(title=title, file_name="chapter.xhtml", content=chapter_html)
    book.add_item(chapter)
    book.toc = (chapter,)
    # Do not reference "nav" in spine — EbookLib may not add nav to manifest for single-chapter
    # books, and Kindle's parser (E999) fails when spine references a missing item.
    book.spine = [chapter]

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
    """Fetch WeChat article → EPUB → save to output/ → send to Kindle → return path."""
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
    path = save_epub(epub_bytes, title)
    email_ok, email_err = send_to_kindle(path, title)
    return {
        "success": True,
        "path": path,
        "title": title,
        "email_sent": email_ok,
        "email_error": email_err,
    }


@app.post("/parse-html")
def endpoint_parse_html(body: ParseHtmlRequest):
    """Parse provided HTML (no fetch) → EPUB → save to output/ → send to Kindle → return path."""
    try:
        _, epub_bytes = create_epub_from_html(body.title, body.html_content)
    except ValueError as e:
        raise HTTPException(status_code=422, detail=str(e))
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Internal error: {type(e).__name__}: {e}\n\n{traceback.format_exc()}",
        )
    path = save_epub(epub_bytes, body.title)
    email_ok, email_err = send_to_kindle(path, body.title)
    return {
        "success": True,
        "path": path,
        "title": body.title,
        "email_sent": email_ok,
        "email_error": email_err,
    }


@app.post("/test-send-epub")
async def endpoint_test_send_epub(file: UploadFile = File(...)):
    """
    Upload a known-good EPUB file and send it to Kindle via the same SMTP path.
    Use this to check whether E999 is caused by our generated EPUB or by SMTP/Amazon.
    """
    if not file.filename or not file.filename.lower().endswith(".epub"):
        raise HTTPException(status_code=422, detail="Please upload an .epub file")
    try:
        raw = await file.read()
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Failed to read file: {e}")
    if not raw:
        raise HTTPException(status_code=422, detail="File is empty")
    fd, path = tempfile.mkstemp(suffix=".epub")
    try:
        os.write(fd, raw)
        os.close(fd)
        title = (file.filename or "Test EPUB").replace(".epub", "").replace(".EPUB", "")
        email_ok, email_err = send_to_kindle(path, title)
        return {
            "success": True,
            "filename": file.filename,
            "email_sent": email_ok,
            "email_error": email_err,
        }
    finally:
        try:
            os.unlink(path)
        except OSError:
            pass
