# TOKINDLE - Project Architecture & Development Plan

## 1. Project Vision
TOKINDLE is an automated toolchain designed to extract, clean, and convert WeChat public account articles into EPUB format, and seamlessly push them to an Amazon Kindle device via SMTP email.

## 2. Core Architecture (Unified Backend)
To support multiple use cases efficiently, this project uses a "Unified Backend + Multi-Client" architecture:
- **Core Backend**: A Python `FastAPI` service. It handles the heavy lifting: bypassing WeChat's anti-leeching mechanisms, downloading images, generating the `EPUB` file, and sending emails via `smtplib`.
- **Client 1 (iOS Shortcut)**: Sends a WeChat article URL to the backend from mobile.
- **Client 2 (RSS Automation Job)**: A scheduled script that fetches RSS feeds and sends batch URLs to the backend.
- **Client 3 (Chrome Extension)**: Extracts raw HTML DOM from the active desktop browser tab and sends it directly to the backend (bypassing server-side scraping blocks).

## 3. Tech Stack Requirements
- **Language**: Python 3
- **Framework**: FastAPI + Uvicorn
- **Parsing**: `BeautifulSoup4` or `newspaper3k`
- **Ebook Generation**: `EbookLib` (Strictly output `.epub` format. DO NOT generate `.mobi`).
- **Dependency Management**: `requirements.txt`

## 4. Critical Technical Constraints (Cursor MUST Follow)
1. **WeChat Image Anti-Leeching**: WeChat article images use the `data-src` attribute instead of `src`. When fetching these images backend, the HTTP request MUST include the header `Referer: https://mp.weixin.qq.com/`. Images must be downloaded and embedded into the EPUB (either as local assets or Base64).
2. **Kindle SMTP Rules**: The email attachment must have a `.epub` extension. The email subject should be "Convert".
3. **API Endpoints**: 
   - `POST /parse-url`: Accepts a URL. The backend will fetch and parse the HTML.
   - `POST /parse-html`: Accepts raw HTML string. The backend will NOT fetch the page, but parse the provided DOM directly (for Client 3).

## 5. Development Phases (Current: Phase 1)
- [ ] Phase 1: Build the core Python FastAPI backend (URL scraping, EPUB generation, SMTP delivery).
- [ ] Phase 2: Build the Chrome Extension (Manifest V3).
- [ ] Phase 3: Create the iOS Shortcut configuration.