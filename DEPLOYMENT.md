# TOKINDLE — Deployment Guide (Mac Server)

Step-by-step guide to run TOKINDLE on a new Mac (e.g. a personal server). Use this when you clone the repo on a new machine.

---

## Step 1: Clone the repository

```bash
cd ~  # or wherever you want the project
git clone https://github.com/YOUR_USERNAME/tokindle.git
cd tokindle
```

Replace `YOUR_USERNAME/tokindle` with your actual GitHub repo (e.g. `yourname/tokindle`).

---

## Step 2: Python virtual environment and dependencies

Create a virtual environment and install dependencies:

```bash
python3 -m venv venv
source venv/bin/activate
pip install --upgrade pip
pip install -r requirements.txt
```

Verify:

```bash
python -c "import fastapi, uvicorn, bs4, ebooklib, PIL; print('OK')"
```

---

## Step 2b (optional): Send to Kindle

If you want the server to email generated EPUBs to your Kindle:

1. Copy the env template: `cp .env.example .env`
2. Edit `.env` and set:
   - `SMTP_SERVER=smtp.gmail.com`, `SMTP_PORT=587`
   - `SENDER_EMAIL` = your Gmail address
   - `SENDER_PASSWORD` = Gmail **App Password** (not your normal password; create under Google Account → Security → 2-Step Verification → App passwords)
   - `KINDLE_EMAIL` = your Send-to-Kindle email (e.g. `you@kindle.com`)
3. If these are missing or empty, the server still runs and saves EPUBs to `output/`, but API responses will have `email_sent: false` and an `email_error` message.

---

## Step 3: Run the server (accessible on the local network)

From the project root (with `venv` activated):

```bash
uvicorn main:app --reload --host 0.0.0.0 --port 8000
```

- `--host 0.0.0.0` — listen on all interfaces so other devices on the LAN (e.g. iPhone, another computer) can reach the server.
- `--port 8000` — default port; change if 8000 is already in use.
- `--reload` — auto-restart on code changes (optional in production).

**Check the server IP** on this Mac (e.g. for the shortcut and extension):

```bash
ipconfig getifaddr en0
```

Or: System Settings → Network → Wi‑Fi → Details → IP address (e.g. `192.168.1.10`).

**Quick test:**

- On this Mac: open http://127.0.0.1:8000/ping → should show `{"ping":"pong"}`.
- From another device on the same network: open http://SERVER_IP:8000/ping (replace `SERVER_IP` with the Mac’s LAN IP).

---

## Step 4: Update client configuration to the new server

After the server runs on the new Mac, point your clients at its address:

1. **Chrome Extension**  
   - Click the extension icon → **Set backend URL** (or open extension Options).  
   - Set **Backend URL** to `http://NEW_SERVER_IP:8000` (e.g. `http://192.168.1.10:8000`).  
   - Save.

2. **iOS Shortcut**  
   - Edit the “Get contents of URL” action.  
   - Change the **URL** to `http://NEW_SERVER_IP:8000/parse-url` (same IP as above, include `/parse-url`).  
   - Save the shortcut.

Use the new Mac’s LAN IP from Step 3. If the server gets a different IP later (e.g. after reboot), repeat the above with the new IP.

---

## Optional: Run in the background (e.g. without a terminal)

- Use **tmux** or **screen** to keep `uvicorn` running after you close SSH.
- Or run as a service (e.g. **launchd** on macOS) or in a Docker container; see your preferred docs for that setup.

---

## Summary checklist

- [ ] Clone repo and `cd tokindle`
- [ ] `python3 -m venv venv && source venv/bin/activate`
- [ ] `pip install -r requirements.txt`
- [ ] (Optional) Copy `.env.example` to `.env` and set SMTP / `KINDLE_EMAIL` for Send to Kindle
- [ ] Run: `uvicorn main:app --reload --host 0.0.0.0 --port 8000`
- [ ] Note this Mac’s IP (e.g. `ipconfig getifaddr en0`)
- [ ] Update Chrome Extension Backend URL to `http://IP:8000`
- [ ] Update iOS Shortcut URL to `http://IP:8000/parse-url`
