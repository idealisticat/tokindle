"""
TOKINDLE - Core FastAPI backend.
Extract, clean, and convert WeChat articles to EPUB and push to Kindle via SMTP.
"""

import io
import re
import uuid
from typing import Optional

import requests
from bs4 import BeautifulSoup
from dotenv import load_dotenv
from ebooklib import epub
from fastapi import FastAPI, HTTPException
from fastapi.responses import Response
from pydantic import BaseModel

load_dotenv()

app = FastAPI(
    title="TOKINDLE",
    description="Convert WeChat articles to EPUB and send to Kindle via SMTP",
    version="0.1.0",
)

# HTTP headers for WeChat and image anti-leeching
WECHAT_REFERER = "https://mp.weixin.qq.com/"
FETCH_HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Referer": WECHAT_REFERER,
}


class ParseUrlRequest(BaseModel):
    """Request body for POST /parse-url."""

    url: str
    send_to_kindle: Optional[bool] = False


def fetch_wechat_article(url: str) -> str:
    """Fetch raw HTML of a WeChat article."""
    resp = requests.get(url, headers=FETCH_HEADERS, timeout=30)
    resp.raise_for_status()
    resp.encoding = resp.apparent_encoding or "utf-8"
    return resp.text


def parse_wechat_article(html: str) -> tuple[str, BeautifulSoup]:
    """
    Extract article title and main content div from WeChat article HTML.
    Returns (title, soup of content div).
    """
    soup = BeautifulSoup(html, "html.parser")

    # Title: prefer og:title, then <title>
    title_tag = soup.find("meta", property="og:title")
    title = title_tag["content"].strip() if title_tag and title_tag.get("content") else None
    if not title:
        title_el = soup.find("title")
        title = title_el.get_text(strip=True) if title_el else "Untitled"

    # Main content: WeChat uses this container
    content_div = soup.find("div", class_="rich_media_content", id="js_content")
    if not content_div:
        raise ValueError("Article content container (div.rich_media_content#js_content) not found")

    return title, content_div


def download_image(url: str) -> bytes:
    """Download image with WeChat Referer to bypass anti-leeching."""
    headers = {**FETCH_HEADERS, "Referer": WECHAT_REFERER}
    resp = requests.get(url, headers=headers, timeout=30)
    resp.raise_for_status()
    return resp.content


def guess_image_extension(url: str, content_type: Optional[str]) -> str:
    """Guess image file extension from URL or Content-Type."""
    if content_type:
        if "png" in content_type:
            return ".png"
        if "gif" in content_type:
            return ".gif"
        if "webp" in content_type:
            return ".webp"
    path = url.split("?")[0].lower()
    if path.endswith(".png"):
        return ".png"
    if path.endswith(".gif"):
        return ".gif"
    if path.endswith(".webp"):
        return ".webp"
    return ".jpg"


def process_images_and_build_epub(
    title: str, content_soup: BeautifulSoup
) -> bytes:
    """
    Find all <img> with data-src, download with Referer, add to EPUB,
    replace img src with local paths, and return EPUB bytes.
    """
    book = epub.EpubBook()
    book.set_identifier(f"tokindle-{uuid.uuid4().hex[:12]}")
    book.set_title(title)
    book.set_language("zh")

    images_dir = "images"
    img_tags = content_soup.find_all("img")
    seen_urls: dict[str, str] = {}  # url -> epub path (avoid duplicate downloads)
    index = 0

    for img in img_tags:
        # WeChat uses data-src for real image URL; src may be placeholder
        image_url = img.get("data-src") or img.get("src")
        if not image_url or not image_url.strip():
            continue
        image_url = image_url.strip()
        if image_url.startswith("data:"):
            # Skip inline data URLs; could embed as-is if needed
            continue

        if image_url in seen_urls:
            img["src"] = seen_urls[image_url]
            if img.get("data-src"):
                del img["data-src"]
            continue

        try:
            content = download_image(image_url)
        except Exception:
            # Keep original src if download fails so the EPUB still renders something
            if img.get("data-src"):
                img["src"] = image_url
                del img["data-src"]
            continue

        ext = guess_image_extension(image_url, None)
        file_name = f"{images_dir}/img_{index}{ext}"
        index += 1

        item = epub.EpubImage(
            uid=f"img-{index}",
            file_name=file_name,
            content=content,
        )
        book.add_item(item)
        seen_urls[image_url] = file_name

        img["src"] = file_name
        if img.get("data-src"):
            del img["data-src"]

    # Build HTML for the single chapter
    body_html = str(content_soup)
    # Wrap in minimal HTML document for the spine
    chapter_html = f"""<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE html>
<html xmlns="http://www.w3.org/1999/xhtml" xmlns:epub="http://www.idpf.org/2007/ops">
<head><meta charset="utf-8"/><title>{title}</title></head>
<body>
{body_html}
</body>
</html>"""

    chapter = epub.EpubHtml(
        title=title,
        file_name="chapter.xhtml",
        content=chapter_html,
    )
    book.add_item(chapter)
    book.toc = (chapter,)
    book.spine = ["nav", chapter]

    buf = io.BytesIO()
    epub.write_epub(buf, book, {})
    buf.seek(0)
    return buf.read()


def create_epub_from_url(url: str) -> tuple[str, bytes]:
    """
    Fetch WeChat article, parse, process images, generate EPUB.
    Returns (title, epub_bytes).
    """
    html = fetch_wechat_article(url)
    title, content_soup = parse_wechat_article(html)
    epub_bytes = process_images_and_build_epub(title, content_soup)
    return title, epub_bytes


def send_epub_to_kindle(epub_bytes: bytes, filename: str = "article.epub") -> None:
    """
    Send the EPUB file as an email attachment to the Kindle address.
    Uses env: SMTP_SERVER, SMTP_PORT, SENDER_EMAIL, SENDER_PASSWORD, KINDLE_EMAIL.
    Subject must be "Convert" per Kindle rules.
    """
    import os
    import smtplib
    from email.mime.application import MIMEApplication
    from email.mime.multipart import MIMEMultipart
    from email.mime.text import MIMEText

    server = os.getenv("SMTP_SERVER")
    port = os.getenv("SMTP_PORT")
    sender = os.getenv("SENDER_EMAIL")
    password = os.getenv("SENDER_PASSWORD")
    kindle_email = os.getenv("KINDLE_EMAIL")

    missing = []
    if not server:
        missing.append("SMTP_SERVER")
    if not port:
        missing.append("SMTP_PORT")
    if not sender:
        missing.append("SENDER_EMAIL")
    if not password:
        missing.append("SENDER_PASSWORD")
    if not kindle_email:
        missing.append("KINDLE_EMAIL")
    if missing:
        raise ValueError(
            f"Missing environment variables: {', '.join(missing)}. "
            "Set them in .env (e.g. SMTP_SERVER, SMTP_PORT, SENDER_EMAIL, SENDER_PASSWORD, KINDLE_EMAIL)."
        )

    port = int(port)
    msg = MIMEMultipart()
    msg["Subject"] = "Convert"
    msg["From"] = sender
    msg["To"] = kindle_email

    msg.attach(MIMEText("TOKINDLE: WeChat article converted to EPUB.", "plain"))
    attachment = MIMEApplication(epub_bytes, _subtype="epub")
    attachment.add_header("Content-Disposition", "attachment", filename=filename)
    msg.attach(attachment)

    with smtplib.SMTP(server, port) as smtp:
        smtp.starttls()
        smtp.login(sender, password)
        smtp.sendmail(sender, kindle_email, msg.as_string())


@app.get("/ping")
def ping():
    """Health check endpoint to verify the service is running."""
    return {"ping": "pong"}


@app.post("/parse-url")
def parse_url(body: ParseUrlRequest):
    """
    Fetch WeChat article from URL, extract title and content, process images
    (data-src + Referer), generate EPUB. Optionally send to Kindle.
    """
    try:
        title, epub_bytes = create_epub_from_url(body.url)
    except requests.RequestException as e:
        raise HTTPException(status_code=502, detail=f"Failed to fetch URL: {e}")
    except ValueError as e:
        raise HTTPException(status_code=422, detail=str(e))

    safe_title = re.sub(r"[^\w\s-]", "", title)[:50].strip() or "article"
    filename = f"{safe_title}.epub"

    if body.send_to_kindle:
        try:
            send_epub_to_kindle(epub_bytes, filename)
        except ValueError as e:
            raise HTTPException(status_code=500, detail=str(e))
        except Exception as e:
            raise HTTPException(
                status_code=500,
                detail=f"Failed to send email to Kindle: {e}",
            )
        return {
            "status": "ok",
            "message": "EPUB generated and sent to Kindle.",
            "title": title,
        }

    return Response(
        content=epub_bytes,
        media_type="application/epub+zip",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )
