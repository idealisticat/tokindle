# TOKINDLE - Project Architecture & Development Plan

## 1. Project Vision
TOKINDLE is an automated toolchain that extracts, cleans, and converts WeChat public account articles into EPUB format. The FastAPI backend generates EPUBs, saves them to a local `output/` directory, and **natively sends them to Kindle** via Gmail SMTP (Send to Kindle email). Email delivery is optional and configured via `.env`.

## 2. Core Architecture (Backend + Native SMTP)
- **Core Backend**: A Python `FastAPI` service with in-memory task tracking. It fetches or accepts HTML, bypasses WeChat image anti-leeching, downloads images (with retry), and generates EPUB files with timestamped filenames. When SMTP is configured in `.env`, the backend sends each EPUB to Kindle via Gmail/Outlook SMTP. The API returns the path, email status, and `task_id` for progress tracking.
- **Admin UI** (`streamlit run admin_ui.py`): Streamlit web dashboard for process management (FastAPI / RSS Worker start/stop via PID files), `.env` configuration with email provider dropdown (Gmail/Outlook/Custom), RSS feed management, live task progress, Gmail connection check, and test email. Reads `TOKINDLE_BACKEND_URL` from env for multi-machine setups.
- **Client 1 (iOS Shortcut)**: Sends a WeChat article URL to the backend.
- **Client 2 (RSS Worker / Job)**: `rss_worker.py` (daemon) or `scripts/rss_job.py` (cron) fetches RSS feeds and sends URLs to the backend, with seen-URL deduplication (auto-truncated to 2000 entries).
- **Client 3 (Chrome Extension)**: Extracts raw HTML DOM from the active browser tab and sends it to the backend via `POST /parse-html`.

## 3. Tech Stack Requirements
- **Language**: Python 3.9+
- **Framework**: FastAPI + Uvicorn
- **Parsing**: BeautifulSoup4
- **Ebook Generation**: EbookLib (Strictly output `.epub` format. DO NOT generate `.mobi`.)
- **Email**: Gmail / Outlook SMTP (smtplib); optional, configured via `.env` or Admin UI.
- **Admin UI**: Streamlit + psutil
- **Dependency Management**: `requirements.txt` (with upper-bound version constraints)

## 4. Critical Technical Constraints (Cursor MUST Follow)
1. **WeChat Image Anti-Leeching**: WeChat article images use the `data-src` attribute instead of `src`. When fetching these images, the HTTP request MUST include the header `Referer: https://mp.weixin.qq.com/`. Images must be downloaded and embedded into the EPUB (local assets or Base64).
2. **API Endpoints**:
   - `POST /parse-url`: Accepts a URL. The backend fetches the page, parses HTML, generates an EPUB, saves it under `output/`, optionally sends to Kindle via SMTP, and returns a JSON response with success status, the **absolute path** to the saved `.epub` file, and `email_sent` / `email_error`.
   - `POST /parse-html`: Accepts a JSON body with `title` and `html_content`. The backend does NOT fetch any URL; it parses the provided HTML (e.g. from the Chrome Extension), applies the same image anti-leeching and EPUB generation logic, saves the EPUB to `output/`, optionally sends to Kindle, and returns the same response shape.

## 5. Development Phases (Current: Phase 6 Complete)
- [x] Phase 1: Build the core Python FastAPI backend (URL scraping, HTML parsing, local EPUB generation into `output/`, return absolute paths).
- [x] Phase 2: Build the Chrome Extension (Manifest V3). See `extension/` and `extension/README.md`.
- [x] Phase 3: Create the iOS Shortcut configuration. See `docs/SHORTCUT_IOS.md` (中文) or `docs/iOS_SHORTCUT_SETUP.md` (English, detailed).
- [x] Phase 4: Native Gmail SMTP delivery to Kindle. Backend sends EPUBs to Send to Kindle email when `.env` is configured; no external automation required.
- [x] Phase 5: RSS automation. `rss_worker.py` (daemon) and `scripts/rss_job.py` (cron) fetch RSS feeds from `feeds.json` / `config/rss_feeds.txt`, post URLs to backend, with seen-URL deduplication. See `docs/RSS_SETUP.md`.
- [x] Phase 6: Admin UI (`admin_ui.py`), task progress tracking, `start.sh` one-click launcher, third-party code review polish (dynamic BACKEND_URL, email provider dropdown, state file truncation, test isolation with SMTP mock + tmp_path, `.env.example`, `.gitignore` hardening). See `DEPLOYMENT.md`, `DEPLOYABILITY_REVIEW.md`, `CODE_REVIEW_GUIDE.md`.

## 6. Testing (Backend)
Run backend tests (no network, no real emails, no disk pollution): `pytest tests/ -v`
- All HTTP mocked; SMTP mocked via `@patch("main.smtplib.SMTP")`; output redirected to `tmp_path`.
- 24 tests covering: ping, parse-url, parse-html, task tracking (GET /tasks, GET /tasks/{id}, failed tasks), parse functions, content div finders, hidden style stripping.

## 7. Context for Later Development
See **CONTEXT.md** for a condensed summary of Phase 1 (APIs, code layout, constraints, gotchas) so new sessions or developers can restore context quickly.

## 8. Manual Verification (Phase 2 & 3)
See **VERIFICATION.md** for step-by-step instructions to test the Chrome Extension and iOS Shortcut yourself.
