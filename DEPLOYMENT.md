# TOKINDLE — Deployment Guide

Guide for your future self: run the TOKINDLE stack (FastAPI backend, optional RSS Worker, optional Admin UI) on a Mac or Linux server so it stays up and is reachable by the Chrome extension and iOS Shortcut.

---

## 1. Prerequisites

- **macOS** (Intel or Apple Silicon) or **Linux**
- **Python 3.9+** (check with `python3 --version`)
- **Git** (to clone/update the repo)

Optional: **Xcode Command Line Tools** (macOS, for some Python builds):

```bash
xcode-select --install
```

---

## 2. Quick Start (recommended)

```bash
git clone https://github.com/YOUR_USERNAME/tokindle.git
cd tokindle
./start.sh
```

`start.sh` will: check for Python 3, create a venv if missing, install dependencies, create `.env` from `.env.example` if needed, and launch the Admin UI. From the browser sidebar you can then start FastAPI and the RSS Worker with one click.

## 3. Manual Setup (alternative)

```bash
cd /path/where/you/want/tokindle
git clone https://github.com/YOUR_USERNAME/tokindle.git
cd tokindle

python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

---

## 4. Environment Configuration

Create a `.env` file in the project root (never commit this; it’s in `.gitignore`):

```bash
cp .env.example .env
# Edit .env with your values (SMTP_*, SENDER_*, KINDLE_EMAIL)
```

- **SENDER_PASSWORD**: Use a [Gmail App Password](https://support.google.com/accounts/answer/185833), not your normal password.
- **KINDLE_EMAIL**: Your “Send to Kindle” email from Amazon (Manage Your Content and Devices → Preferences → Send to Kindle).

If you skip `.env`, the app still runs; it just won’t send EPUBs to Kindle You can also edit `.env` from the Admin UI (Configuration tab).

---

## 5. Run the Stack

**Option A — Admin UI (recommended for first-time and daily use)**

```bash
source venv/bin/activate
streamlit run admin_ui.py
```

Then in the browser: use the sidebar to **Start** the FastAPI backend (and optionally the RSS Worker). The Admin UI provides:

- **Dashboard**: live task progress for jobs triggered by the Chrome extension, iOS Shortcut, or RSS.
- **Configuration**: edit `.env` and save + restart FastAPI.
- **RSS Feeds**: manage `feeds.json` and restart the RSS Worker.
- **Testing & Logs**: Gmail connection check, send test email, view logs.

**Option B — Backend only (e.g. for automation or headless)**

```bash
source venv/bin/activate
uvicorn main:app --host 0.0.0.0 --port 8000
```

Optional, in another terminal:

```bash
python rss_worker.py   # long-running RSS daemon; reads feeds.json
```

- `--host 0.0.0.0` allows access from other devices on the same network (e.g. iPhone for the iOS Shortcut).
- Default URL: `http://<host-IP>:8000`. Find IP: `ipconfig getifaddr en0` (macOS Wi‑Fi) or `hostname -I` (Linux).

---

## 6. Keep It Running (launchd on Mac)

To have TOKINDLE start on boot and restart on crash, use **launchd**.

1. Create a plist (replace `YOUR_USERNAME` and `/path/to/tokindle` with your actual user and project path):

```bash
nano ~/Library/LaunchAgents/com.tokindle.backend.plist
```

2. Paste (adjust paths and user):

```xml
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
  <key>Label</key>
  <string>com.tokindle.backend</string>
  <key>ProgramArguments</key>
  <array>
    <string>/path/to/tokindle/venv/bin/uvicorn</string>
    <string>main:app</string>
    <string>--host</string>
    <string>0.0.0.0</string>
    <string>--port</string>
    <string>8000</string>
  </array>
  <key>WorkingDirectory</key>
  <string>/path/to/tokindle</string>
  <key>RunAtLoad</key>
  <true/>
  <key>KeepAlive</key>
  <true/>
  <key>StandardOutPath</key>
  <string>/path/to/tokindle/logs/fastapi.out.log</string>
  <key>StandardErrorPath</key>
  <string>/path/to/tokindle/logs/fastapi.err.log</string>
</dict>
</plist>
```

3. Create logs directory and load the job:

```bash
mkdir -p /path/to/tokindle/logs
launchctl load ~/Library/LaunchAgents/com.tokindle.backend.plist
```

4. Useful commands:

```bash
launchctl list | grep tokindle
launchctl unload ~/Library/LaunchAgents/com.tokindle.backend.plist
launchctl load ~/Library/LaunchAgents/com.tokindle.backend.plist
tail -f /path/to/tokindle/logs/fastapi.err.log
```

To run the **RSS Worker** under launchd as well, add a second plist (e.g. `com.tokindle.rss.plist`) with `ProgramArguments`: `["/path/to/tokindle/venv/bin/python", "/path/to/tokindle/rss_worker.py"]`, same `WorkingDirectory`, and `KeepAlive`/log paths. See `docs/RSS_SETUP.md` for a full example.

`logs/` is in `.gitignore`; do not commit log files.

---

## 7. Linux: systemd (optional)

On Linux, use systemd instead of launchd. Example unit for the FastAPI backend (`/etc/systemd/system/tokindle-api.service`):

```ini
[Unit]
Description=TOKINDLE FastAPI
After=network.target

[Service]
Type=simple
User=YOUR_USER
WorkingDirectory=/path/to/tokindle
ExecStart=/path/to/tokindle/venv/bin/uvicorn main:app --host 0.0.0.0 --port 8000
Restart=always
RestartSec=5

[Install]
WantedBy=multi-user.target
```

Then:

```bash
sudo systemctl daemon-reload
sudo systemctl enable tokindle-api
sudo systemctl start tokindle-api
sudo systemctl status tokindle-api
```

A second unit can be added for `rss_worker.py` (ExecStart: `venv/bin/python rss_worker.py`). The Admin UI is typically run manually or behind a separate process manager if you need it on the server.

---

## 8. Optional: Reverse Proxy (HTTPS / custom port)

If you want HTTPS or to serve on port 80/443, put **nginx** or **Caddy** in front of the app and proxy to `http://127.0.0.1:8000`. Example nginx location:

```nginx
location / {
    proxy_pass http://127.0.0.1:8000;
    proxy_set_header Host $host;
    proxy_set_header X-Real-IP $remote_addr;
    proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
    proxy_set_header X-Forwarded-Proto $scheme;
}
```

Then point the Chrome extension and iOS Shortcut at `https://your-domain.com` (or your Mac’s hostname) instead of `http://IP:8000`.

---

## 9. Security Warning

**Neither the Admin UI nor the FastAPI backend have built-in authentication.** If the server is reachable from the public internet, anyone can:

- Trigger article conversions and consume your resources
- Read and modify your `.env` (including SMTP passwords) via the Admin UI
- Start, stop, or restart backend services

**You MUST either:**

1. **Run TOKINDLE on a trusted network only** (home LAN, VPN), or
2. **Put it behind a reverse proxy with authentication** (e.g. nginx Basic Auth, Caddy with `basicauth`, Cloudflare Access).

See **DEPLOYABILITY_REVIEW.md** for detailed security recommendations.

---

## 10. Updating the App

```bash
cd /path/to/tokindle
git pull
source venv/bin/activate
pip install -r requirements.txt
# If using launchd:
launchctl unload ~/Library/LaunchAgents/com.tokindle.backend.plist
launchctl load ~/Library/LaunchAgents/com.tokindle.backend.plist
```

---

## 11. Quick Checklist

- [ ] Python 3.9+ and `venv` created
- [ ] `pip install -r requirements.txt` run
- [ ] `.env` created (e.g. `cp .env.example .env`) with Gmail SMTP and Kindle email if you want Send to Kindle
- [ ] FastAPI runs (via `streamlit run admin_ui.py` → Start, or `uvicorn main:app --host 0.0.0.0 --port 8000`)
- [ ] From another device: `http://<host-IP>:8000/ping` returns `{"ping":"pong"}`
- [ ] Chrome extension options: Backend URL = `http://<host-IP>:8000`
- [ ] iOS Shortcut: POST URL = `http://<host-IP>:8000/parse-url`
- [ ] Optional: launchd (Mac) or systemd (Linux) so backend/RSS worker run after reboot
- [ ] Optional: Admin UI at `streamlit run admin_ui.py` for task dashboard, config, and RSS management

For API details and constraints, see **CONTEXT.md** and **project_plan.md**. For deployability on other servers, see **DEPLOYABILITY_REVIEW.md**.
