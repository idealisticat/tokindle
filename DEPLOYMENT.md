# TOKINDLE — Deployment Guide (Mac Server)

Guide for your future self: run the TOKINDLE FastAPI backend on a Mac (local or headless server) so it stays up and is reachable by the Chrome extension and iOS Shortcut.

---

## 1. Prerequisites

- **macOS** (Intel or Apple Silicon)
- **Python 3.10+** (check with `python3 --version`)
- **Git** (to clone/update the repo)

Optional: **Xcode Command Line Tools** (for some Python builds):

```bash
xcode-select --install
```

---

## 2. Clone and One-Time Setup

```bash
# Clone (or pull if already cloned)
cd /path/where/you/want/tokindle
git clone https://github.com/YOUR_USERNAME/tokindle.git
cd tokindle

# Create virtual environment
python3 -m venv venv
source venv/bin/activate

# Install dependencies
pip install -r requirements.txt
```

---

## 3. Environment Configuration

Create a `.env` file in the project root (never commit this; it’s in `.gitignore`):

```bash
# Required for Send to Kindle via Gmail SMTP
SMTP_SERVER=smtp.gmail.com
SMTP_PORT=587
SENDER_EMAIL=your@gmail.com
SENDER_PASSWORD=your_app_password
KINDLE_EMAIL=your_kindle@kindle.com
```

- **SENDER_PASSWORD**: Use a [Gmail App Password](https://support.google.com/accounts/answer/185833), not your normal password.
- **KINDLE_EMAIL**: Your “Send to Kindle” email from Amazon (Manage Your Content and Devices → Preferences → Send to Kindle).

If you skip `.env`, the app still runs; it just won’t send EPUBs to Kindle (`email_sent: false` in API responses).

---

## 4. Run the Server

**Development (with auto-reload):**

```bash
source venv/bin/activate
uvicorn main:app --reload --host 0.0.0.0 --port 8000
```

**Production (no reload, bind to all interfaces):**

```bash
source venv/bin/activate
uvicorn main:app --host 0.0.0.0 --port 8000
```

- `--host 0.0.0.0` allows access from other devices on the same network (e.g. iPhone for the iOS Shortcut).
- Default URL: `http://<Mac-IP>:8000` (e.g. `http://192.168.1.100:8000`). Find your IP with `ipconfig getifaddr en0` (Wi‑Fi) or `ifconfig`.

---

## 5. Keep It Running (launchd on Mac)

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
  <string>/path/to/tokindle/logs/tokindle.out.log</string>
  <key>StandardErrorPath</key>
  <string>/path/to/tokindle/logs/tokindle.err.log</string>
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
# Check status
launchctl list | grep tokindle

# Stop
launchctl unload ~/Library/LaunchAgents/com.tokindle.backend.plist

# Start again
launchctl load ~/Library/LaunchAgents/com.tokindle.backend.plist

# View logs
tail -f /path/to/tokindle/logs/tokindle.out.log
tail -f /path/to/tokindle/logs/tokindle.err.log
```

Add `logs/` to `.gitignore` if you don’t want to commit log files.

---

## 6. Optional: Reverse Proxy (HTTPS / custom port)

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

## 7. Updating the App

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

## 8. Quick Checklist

- [ ] Python 3.10+ and `venv` created
- [ ] `pip install -r requirements.txt` run
- [ ] `.env` created with Gmail SMTP and Kindle email (if you want Send to Kindle)
- [ ] Server runs with `uvicorn main:app --host 0.0.0.0 --port 8000`
- [ ] From another device: `http://<Mac-IP>:8000/ping` returns `{"ping":"pong"}`
- [ ] Chrome extension options: Backend URL = `http://<Mac-IP>:8000`
- [ ] iOS Shortcut: POST URL = `http://<Mac-IP>:8000/parse-url`
- [ ] Optional: launchd plist installed and loaded so it runs after reboot

For API details and constraints, see **CONTEXT.md** and **project_plan.md**.
