# TOKINDLE - Project Architecture & Development Plan

## 1. Project Vision
TOKINDLE is an automated toolchain that extracts, cleans, and converts WeChat public account articles into EPUB format. Generated EPUBs are saved locally; an external RPA agent (OpenClaw) handles upload to Amazon Kindle.

## 2. Core Architecture (Local Generation + RPA Upload)
- **Core Backend**: A Python `FastAPI` service. It fetches or accepts HTML, bypasses WeChat image anti-leeching, downloads images, and generates EPUB files. All EPUBs are written to a local `output/` directory. The API returns the absolute path to each saved file.
- **Upload**: OpenClaw (RPA) or other automation reads from `output/` and performs the actual upload to Amazon; the backend does not send email or communicate with Amazon directly.
- **Client 1 (iOS Shortcut)**: Sends a WeChat article URL to the backend; backend saves EPUB to `output/` and returns its path.
- **Client 2 (RSS Automation Job)**: A scheduled script that fetches RSS feeds and sends batch URLs to the backend.
- **Client 3 (Chrome Extension)**: Extracts raw HTML DOM from the active browser tab and sends it to the backend via `POST /parse-html` (no URL fetch).

## 3. Tech Stack Requirements
- **Language**: Python 3
- **Framework**: FastAPI + Uvicorn
- **Parsing**: `BeautifulSoup4` or `newspaper3k`
- **Ebook Generation**: `EbookLib` (Strictly output `.epub` format. DO NOT generate `.mobi`).
- **Dependency Management**: `requirements.txt`

## 4. Critical Technical Constraints (Cursor MUST Follow)
1. **WeChat Image Anti-Leeching**: WeChat article images use the `data-src` attribute instead of `src`. When fetching these images, the HTTP request MUST include the header `Referer: https://mp.weixin.qq.com/`. Images must be downloaded and embedded into the EPUB (local assets or Base64).
2. **API Endpoints**:
   - `POST /parse-url`: Accepts a URL. The backend fetches the page, parses HTML, generates an EPUB, saves it under `output/`, and returns a JSON response with success status and the **absolute path** to the saved `.epub` file.
   - `POST /parse-html`: Accepts a JSON body with `title` and `html_content`. The backend does NOT fetch any URL; it parses the provided HTML (e.g. from the Chrome Extension), applies the same image anti-leeching and EPUB generation logic, saves the EPUB to `output/`, and returns success status and the **absolute path** to the saved `.epub` file.

## 5. Development Phases (Current: Phase 1)
- [x] Phase 1: Build the core Python FastAPI backend (URL scraping, HTML parsing, local EPUB generation into `output/`, return absolute paths).
- [x] Phase 2: Build the Chrome Extension (Manifest V3). See `extension/` and `extension/README.md`.
- [x] Phase 3: Create the iOS Shortcut configuration. See `docs/SHORTCUT_IOS.md` (中文) or `docs/iOS_SHORTCUT_SETUP.md` (English, detailed).
- [ ] Phase 4: Integrate OpenClaw (or other RPA) to upload from `output/` to Amazon.

## 6. Testing (Backend)
Run backend tests (no network, mocked HTTP): `pytest tests/ -v`

## 7. Context for Later Development
See **CONTEXT.md** for a condensed summary of Phase 1 (APIs, code layout, constraints, gotchas) so new sessions or developers can restore context quickly.

## 8. Manual Verification (Phase 2 & 3)
See **VERIFICATION.md** for step-by-step instructions to test the Chrome Extension and iOS Shortcut yourself.
