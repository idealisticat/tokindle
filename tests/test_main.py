"""
TOKINDLE backend tests.
All HTTP is mocked — no real network requests.
"""

import io
import zipfile
from unittest.mock import MagicMock, patch

import pytest
from bs4 import BeautifulSoup
from fastapi.testclient import TestClient

from main import (
    _find_wechat_content_div,
    _strip_hidden_styles,
    app,
    build_epub,
    create_epub_from_url,
    parse_raw_html,
    parse_wechat_html,
)
from tests.conftest import MINIMAL_JPEG


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _mock_get(html_text: str):
    """Return a side_effect for requests.get that serves *html_text* for pages and MINIMAL_JPEG for images."""
    def side_effect(url, **kwargs):
        resp = MagicMock()
        resp.raise_for_status = MagicMock()
        resp.apparent_encoding = "utf-8"
        if "mmbiz.qpic.cn" in url or url.endswith((".jpg", ".png", ".gif")):
            resp.content = MINIMAL_JPEG
        else:
            resp.text = html_text
        return resp
    return side_effect


def _epub_chapter_text(epub_bytes: bytes) -> str:
    """Extract the chapter.xhtml text from EPUB bytes."""
    z = zipfile.ZipFile(io.BytesIO(epub_bytes))
    name = next(n for n in z.namelist() if "chapter" in n and n.endswith(".xhtml"))
    return z.read(name).decode("utf-8")


# ---------------------------------------------------------------------------
# GET /ping
# ---------------------------------------------------------------------------

def test_ping():
    r = TestClient(app).get("/ping")
    assert r.status_code == 200
    assert r.json() == {"ping": "pong"}


# ---------------------------------------------------------------------------
# POST /parse-url
# ---------------------------------------------------------------------------

def test_parse_url_success(sample_wechat_html):
    """Returns JSON with success, path (.epub on disk), and title."""
    client = TestClient(app)
    with patch("main.requests.get", side_effect=_mock_get(sample_wechat_html)):
        r = client.post("/parse-url", json={"url": "https://mp.weixin.qq.com/s/abc"})
    assert r.status_code == 200
    data = r.json()
    assert data["success"] is True
    assert data["path"].endswith(".epub")
    assert data["title"] == "Test Article Title"
    with open(data["path"], "rb") as f:
        assert f.read(4) == b"PK\x03\x04"


def test_parse_url_epub_has_content(sample_wechat_html):
    """EPUB chapter contains article text and no hidden styles."""
    with patch("main.requests.get", side_effect=_mock_get(sample_wechat_html)):
        _, epub_bytes = create_epub_from_url("https://mp.weixin.qq.com/s/abc")
    text = _epub_chapter_text(epub_bytes)
    assert "Hello world" in text
    assert "visibility" not in text.lower() or "hidden" not in text.lower()


def test_parse_url_network_error():
    """502 when the page cannot be fetched."""
    with patch("main.requests.get", side_effect=requests.RequestException("timeout")):
        r = TestClient(app).post("/parse-url", json={"url": "https://mp.weixin.qq.com/s/x"})
    assert r.status_code == 502


def test_parse_url_no_content_div(sample_wechat_html_no_content):
    """422 when the HTML has no recognisable content container."""
    with patch("main.requests.get", side_effect=_mock_get(sample_wechat_html_no_content)):
        r = TestClient(app).post("/parse-url", json={"url": "https://mp.weixin.qq.com/s/x"})
    assert r.status_code == 422
    assert "not found" in r.json()["detail"].lower()


# ---------------------------------------------------------------------------
# POST /parse-html
# ---------------------------------------------------------------------------

def test_parse_html_success(sample_wechat_html):
    """Returns JSON with success, path, and title; EPUB is valid."""
    with patch("main.requests.get", side_effect=_mock_get("")):
        r = TestClient(app).post(
            "/parse-html",
            json={"title": "My Title", "html_content": sample_wechat_html},
        )
    assert r.status_code == 200
    data = r.json()
    assert data["success"] is True
    assert data["title"] == "My Title"
    assert data["path"].endswith(".epub")
    with open(data["path"], "rb") as f:
        assert f.read(4) == b"PK\x03\x04"


def test_parse_html_plain_body():
    """Accepts non-WeChat HTML; falls back to <body>."""
    plain = "<html><body><p>Simple paragraph.</p></body></html>"
    with patch("main.requests.get"):
        r = TestClient(app).post(
            "/parse-html", json={"title": "Plain", "html_content": plain}
        )
    assert r.status_code == 200
    assert r.json()["success"] is True


# ---------------------------------------------------------------------------
# parse_wechat_html
# ---------------------------------------------------------------------------

def test_parse_wechat_html_title_and_div(sample_wechat_html):
    title, div = parse_wechat_html(sample_wechat_html)
    assert title == "Test Article Title"
    assert "Hello world" in div.get_text()


def test_parse_wechat_html_strips_hidden(sample_wechat_html):
    _, div = parse_wechat_html(sample_wechat_html)
    assert "hidden" not in (div.get("style") or "")


def test_parse_wechat_html_missing_div(sample_wechat_html_no_content):
    with pytest.raises(ValueError, match="(?i)not found"):
        parse_wechat_html(sample_wechat_html_no_content)


def test_parse_wechat_html_alt_selector(sample_wechat_html_alt_selectors):
    title, div = parse_wechat_html(sample_wechat_html_alt_selectors)
    assert title == "Alt Selector Title"
    assert "without rich_media_content" in div.get_text()


# ---------------------------------------------------------------------------
# parse_raw_html
# ---------------------------------------------------------------------------

def test_parse_raw_html_wechat_div(sample_wechat_html):
    div = parse_raw_html(sample_wechat_html)
    assert "Hello world" in div.get_text()


def test_parse_raw_html_fallback():
    div = parse_raw_html("<html><body><p>Fallback</p></body></html>")
    assert "Fallback" in div.get_text()


# ---------------------------------------------------------------------------
# _find_wechat_content_div
# ---------------------------------------------------------------------------

def test_find_div_primary():
    soup = BeautifulSoup(
        '<div class="rich_media_content" id="js_content">ok</div>', "html.parser"
    )
    assert _find_wechat_content_div(soup) is not None


def test_find_div_id_only():
    soup = BeautifulSoup('<div id="js_content" class="x">ok</div>', "html.parser")
    assert _find_wechat_content_div(soup) is not None


def test_find_div_class_only():
    soup = BeautifulSoup('<div class="rich_media_content">ok</div>', "html.parser")
    assert _find_wechat_content_div(soup) is not None


def test_find_div_none():
    soup = BeautifulSoup("<div>nothing</div>", "html.parser")
    assert _find_wechat_content_div(soup) is None


# ---------------------------------------------------------------------------
# _strip_hidden_styles
# ---------------------------------------------------------------------------

def test_strip_hidden_styles_removes_hiding():
    soup = BeautifulSoup(
        '<div style="visibility: hidden; opacity: 0; color: red;">x</div>',
        "html.parser",
    )
    div = soup.find("div")
    _strip_hidden_styles(div)
    style = div.get("style", "")
    assert "hidden" not in style
    assert "red" in style


def test_strip_hidden_styles_display_none():
    soup = BeautifulSoup('<p style="display:none;">x</p>', "html.parser")
    _strip_hidden_styles(soup.find("p"))
    assert soup.find("p").get("style") is None


def test_strip_hidden_styles_no_style():
    soup = BeautifulSoup("<p>ok</p>", "html.parser")
    _strip_hidden_styles(soup.find("p"))  # should not raise


# ---------------------------------------------------------------------------
# import needed at module scope for the network-error test
# ---------------------------------------------------------------------------
import requests  # noqa: E402
