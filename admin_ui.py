#!/usr/bin/env python3
"""
TOKINDLE — Admin Control Center (Streamlit Web UI).
Pure external wrapper: manages .env and feeds.json files, controls FastAPI /
RSS Worker via OS-level process management, shows live task progress.

Run:  streamlit run admin_ui.py
"""

import json
import os
import smtplib
import ssl
import subprocess
import sys
import time
from datetime import timedelta
from email.mime.text import MIMEText
from pathlib import Path
from typing import Optional, Tuple

import psutil
import requests
import streamlit as st
from dotenv import dotenv_values

# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------

BASE_DIR = Path(__file__).resolve().parent
ENV_PATH = BASE_DIR / ".env"
ENV_EXAMPLE_PATH = BASE_DIR / ".env.example"
FEEDS_PATH = BASE_DIR / "feeds.json"
LOGS_DIR = BASE_DIR / "logs"
PID_DIR = LOGS_DIR

_candidates = [BASE_DIR / "venv" / "bin" / "python3", BASE_DIR / "venv" / "bin" / "python"]
VENV_PYTHON = next((p for p in _candidates if p.exists()), Path(sys.executable))

BACKEND_URL = os.environ.get("TOKINDLE_BACKEND_URL", "http://127.0.0.1:8000").rstrip("/")

# ---------------------------------------------------------------------------
# PID-file based process management
# ---------------------------------------------------------------------------

FASTAPI_PID = PID_DIR / "fastapi.pid"
RSS_PID = PID_DIR / "rss_worker.pid"


def _read_pid(pid_path: Path) -> Optional[int]:
    if not pid_path.exists():
        return None
    try:
        pid = int(pid_path.read_text().strip())
        if psutil.pid_exists(pid):
            return pid
        pid_path.unlink(missing_ok=True)
    except (ValueError, OSError):
        pass
    return None


def _write_pid(pid_path: Path, pid: int) -> None:
    pid_path.parent.mkdir(parents=True, exist_ok=True)
    pid_path.write_text(str(pid), encoding="utf-8")


def _kill_pid(pid_path: Path) -> None:
    pid = _read_pid(pid_path)
    if not pid:
        return
    try:
        parent = psutil.Process(pid)
        children = parent.children(recursive=True)
        parent.terminate()
        for ch in children:
            ch.terminate()
        gone, alive = psutil.wait_procs([parent] + children, timeout=5)
        for p in alive:
            p.kill()
    except (psutil.NoSuchProcess, psutil.AccessDenied):
        pass
    finally:
        pid_path.unlink(missing_ok=True)


def _open_log(name: str):
    LOGS_DIR.mkdir(exist_ok=True)
    return open(LOGS_DIR / name, "a")


# --- FastAPI ---

def _fastapi_health() -> bool:
    """True only if /ping returns 200 (process alive AND responsive)."""
    try:
        r = requests.get(f"{BACKEND_URL}/ping", timeout=3)
        return r.status_code == 200
    except Exception:
        return False


def fastapi_status() -> Tuple[bool, Optional[int]]:
    pid = _read_pid(FASTAPI_PID)
    healthy = _fastapi_health() if pid else False
    return (healthy, pid) if pid else (False, None)


def start_fastapi() -> None:
    proc = subprocess.Popen(
        [str(VENV_PYTHON), "-m", "uvicorn", "main:app",
         "--host", "0.0.0.0", "--port", "8000"],
        cwd=str(BASE_DIR),
        stdout=_open_log("fastapi.out.log"),
        stderr=_open_log("fastapi.err.log"),
        start_new_session=True,
    )
    _write_pid(FASTAPI_PID, proc.pid)


def stop_fastapi() -> None:
    _kill_pid(FASTAPI_PID)


# --- RSS Worker ---

def rss_worker_status() -> Tuple[bool, Optional[int]]:
    pid = _read_pid(RSS_PID)
    return (True, pid) if pid else (False, None)


def start_rss_worker() -> None:
    proc = subprocess.Popen(
        [str(VENV_PYTHON), str(BASE_DIR / "rss_worker.py")],
        cwd=str(BASE_DIR),
        stdout=_open_log("rss_worker.out.log"),
        stderr=_open_log("rss_worker.err.log"),
        start_new_session=True,
    )
    _write_pid(RSS_PID, proc.pid)


def stop_rss_worker() -> None:
    _kill_pid(RSS_PID)


# ---------------------------------------------------------------------------
# .env helpers
# ---------------------------------------------------------------------------

ENV_KEYS = ["SMTP_SERVER", "SMTP_PORT", "SENDER_EMAIL", "SENDER_PASSWORD", "KINDLE_EMAIL"]
ENV_DEFAULTS = {"SMTP_SERVER": "smtp.gmail.com", "SMTP_PORT": "587"}

EMAIL_PROVIDERS = {
    "Gmail": {"SMTP_SERVER": "smtp.gmail.com", "SMTP_PORT": "587"},
    "Outlook / Hotmail": {"SMTP_SERVER": "smtp-mail.outlook.com", "SMTP_PORT": "587"},
    "Custom": {},
}


def load_env() -> dict:
    vals = dict(ENV_DEFAULTS)
    if ENV_PATH.exists():
        vals.update({k: v for k, v in dotenv_values(ENV_PATH).items() if v is not None})
    return vals


def save_env(values: dict) -> None:
    lines = [f"{k}={values.get(k, '')}" for k in ENV_KEYS]
    ENV_PATH.write_text("\n".join(lines) + "\n", encoding="utf-8")


def validate_env(values: dict) -> list:
    errors = []
    if not values.get("SENDER_EMAIL", "").strip():
        errors.append("Sender Email is required.")
    if not values.get("SENDER_PASSWORD", "").strip():
        errors.append("Sender Password is required.")
    if not values.get("KINDLE_EMAIL", "").strip():
        errors.append("Kindle Email is required.")
    port = values.get("SMTP_PORT", "")
    if port and not port.isdigit():
        errors.append("SMTP Port must be a number.")
    return errors


# ---------------------------------------------------------------------------
# feeds.json helpers
# ---------------------------------------------------------------------------


def load_feeds() -> dict:
    default = {"feeds": [], "interval_minutes": 60}
    if not FEEDS_PATH.exists():
        return default
    try:
        data = json.loads(FEEDS_PATH.read_text(encoding="utf-8"))
        data.setdefault("feeds", [])
        data.setdefault("interval_minutes", 60)
        return data
    except (json.JSONDecodeError, OSError):
        return default


def save_feeds(data: dict) -> None:
    FEEDS_PATH.write_text(
        json.dumps(data, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
    )


def validate_feed_url(url: str) -> Tuple[bool, str]:
    """Try fetching a feed URL and check if it has entries."""
    import feedparser
    try:
        parsed = feedparser.parse(url)
        entries = getattr(parsed, "entries", None) or []
        if entries:
            titles = [e.get("title", "(no title)") for e in entries[:3]]
            return True, f"Valid feed with {len(entries)} entries. Latest: {', '.join(titles)}"
        if parsed.get("bozo_exception"):
            return False, f"Parse error: {parsed.bozo_exception}"
        return False, "Feed parsed but contains 0 entries."
    except Exception as exc:
        return False, f"Fetch failed: {exc}"


# ---------------------------------------------------------------------------
# SMTP helpers (standalone — does NOT touch main.py)
# ---------------------------------------------------------------------------


def check_google_smtp(server: str, port: str, sender: str,
                      password: str) -> Tuple[bool, str]:
    """Test Gmail SMTP login only (no email sent)."""
    if not all([server, sender, password]):
        return False, "Missing SMTP server, sender email, or password."
    try:
        ctx = ssl.create_default_context()
        with smtplib.SMTP(server, int(port), timeout=10) as s:
            s.ehlo()
            s.starttls(context=ctx)
            s.ehlo()
            s.login(sender, password)
        return True, "Gmail SMTP login successful. Credentials are valid."
    except smtplib.SMTPAuthenticationError as exc:
        return False, f"Authentication failed: {exc}. Check your App Password."
    except Exception as exc:
        return False, f"SMTP connection check failed: {exc}"


def send_test_email(server: str, port: str, sender: str,
                    password: str, recipient: str) -> Tuple[bool, str]:
    """Send a plain-text test email to verify full delivery pipeline."""
    if not all([sender, password, recipient]):
        return False, "Missing required fields."
    try:
        msg = MIMEText(
            "This is a test email from the TOKINDLE Admin UI.\n"
            "If you see this, your SMTP credentials and Kindle email are correct.",
            "plain",
        )
        msg["Subject"] = "TOKINDLE SMTP Test"
        msg["From"] = sender
        msg["To"] = recipient
        ctx = ssl.create_default_context()
        with smtplib.SMTP(server, int(port)) as s:
            s.starttls(context=ctx)
            s.login(sender, password)
            s.sendmail(sender, [recipient], msg.as_string())
        return True, f"Test email sent to {recipient}."
    except Exception as exc:
        return False, f"Send failed: {exc}"


# ---------------------------------------------------------------------------
# Task fetching (from FastAPI /tasks endpoint)
# ---------------------------------------------------------------------------

STEP_LABELS = {
    "fetching_url": "Fetching URL",
    "parsing_html": "Parsing HTML",
    "generating_epub": "Generating EPUB",
    "saving_file": "Saving File",
    "sending_email": "Sending Email",
    "completed": "Completed",
}


def fetch_tasks(limit: int = 30) -> list:
    try:
        r = requests.get(f"{BACKEND_URL}/tasks", params={"limit": limit}, timeout=3)
        if r.status_code == 200:
            return r.json().get("tasks", [])
    except Exception:
        pass
    return []


# ---------------------------------------------------------------------------
# Log reader
# ---------------------------------------------------------------------------


def _tail(path: Path, n: int = 80) -> str:
    if not path.exists():
        return ""
    try:
        lines = path.read_text(encoding="utf-8", errors="replace").splitlines()
        return "\n".join(lines[-n:])
    except OSError:
        return "(cannot read log)"


def _log_size_mb(path: Path) -> float:
    if not path.exists():
        return 0.0
    return path.stat().st_size / (1024 * 1024)


def _rotate_log(path: Path, max_mb: float = 10.0) -> None:
    """Keep only the last half of lines if file exceeds max_mb."""
    if not path.exists() or _log_size_mb(path) <= max_mb:
        return
    try:
        lines = path.read_text(encoding="utf-8", errors="replace").splitlines()
        half = lines[len(lines) // 2:]
        path.write_text("\n".join(half) + "\n", encoding="utf-8")
    except OSError:
        pass


# =========================================================================
#  STREAMLIT  UI
# =========================================================================

st.set_page_config(page_title="TOKINDLE Control Center", page_icon="\U0001F4DA", layout="wide")
LOGS_DIR.mkdir(exist_ok=True)

# Rotate large logs on each page load
for lf in ["fastapi.out.log", "fastapi.err.log", "rss_worker.out.log", "rss_worker.err.log"]:
    _rotate_log(LOGS_DIR / lf)

# ---------------------------------------------------------------------------
# First-use guide
# ---------------------------------------------------------------------------

_env_missing = not ENV_PATH.exists() or not load_env().get("SENDER_EMAIL", "").strip()
_feeds_missing = not FEEDS_PATH.exists() or not load_feeds().get("feeds")

if _env_missing or _feeds_missing:
    st.info(
        "**Welcome to TOKINDLE!** It looks like this is your first time. Follow these steps:\n\n"
        "1. Go to the **Configuration** tab and fill in your Gmail SMTP and Kindle email, then **Save & Restart FastAPI**.\n"
        "2. Go to the **RSS Feeds** tab and add at least one RSS feed URL, then **Save & Restart Worker**.\n"
        "3. Use the **Testing** tab to verify your email credentials work.\n\n"
        "Alternatively, copy `.env.example` to `.env` and edit it manually."
    )

# ---------------------------------------------------------------------------
# Sidebar: live process status + controls
# ---------------------------------------------------------------------------

st.sidebar.title("\U0001F39B\uFE0F Control Center")

# -- FastAPI --
st.sidebar.markdown("---")
st.sidebar.subheader("FastAPI Backend")
api_healthy, api_pid = fastapi_status()
if api_pid and api_healthy:
    st.sidebar.markdown(f"\U0001F7E2 **Running** &nbsp; PID `{api_pid}`")
elif api_pid and not api_healthy:
    st.sidebar.markdown(f"\U0001F7E1 **Starting / Unhealthy** &nbsp; PID `{api_pid}`")
else:
    st.sidebar.markdown("\U0001F534 **Stopped**")

c1, c2, c3 = st.sidebar.columns(3)
with c1:
    if st.button("Start", key="btn_start_api", disabled=bool(api_pid)):
        start_fastapi()
        time.sleep(2)
        st.rerun()
with c2:
    if st.button("Stop", key="btn_stop_api", disabled=not api_pid):
        stop_fastapi()
        time.sleep(1)
        st.rerun()
with c3:
    if st.button("Restart", key="btn_restart_api"):
        stop_fastapi()
        time.sleep(1)
        start_fastapi()
        time.sleep(2)
        st.rerun()

# -- RSS Worker --
st.sidebar.markdown("---")
st.sidebar.subheader("RSS Worker")
rss_up, rss_pid = rss_worker_status()
if rss_up:
    st.sidebar.markdown(f"\U0001F7E2 **Running** &nbsp; PID `{rss_pid}`")
else:
    st.sidebar.markdown("\U0001F534 **Stopped**")

c1, c2 = st.sidebar.columns(2)
with c1:
    if st.button("Start", key="btn_start_rss", disabled=rss_up):
        start_rss_worker()
        time.sleep(1)
        st.rerun()
with c2:
    if st.button("Stop", key="btn_stop_rss", disabled=not rss_up):
        stop_rss_worker()
        time.sleep(1)
        st.rerun()

# ---------------------------------------------------------------------------
# Main area
# ---------------------------------------------------------------------------

st.title("\U0001F4DA TOKINDLE Control Center")

tab_dash, tab_cfg, tab_rss, tab_test = st.tabs([
    "\U0001F4CB  Dashboard",
    "\u2699\uFE0F  Configuration",
    "\U0001F4E1  RSS Feeds",
    "\U0001F9EA  Testing & Logs",
])

# ===================== Tab 1 — Live Task Dashboard ====================
with tab_dash:
    st.header("Live Task Progress")
    st.caption("Shows tasks submitted to the backend (via Chrome extension, iOS Shortcut, RSS, etc.).")

    if not api_healthy:
        st.warning("FastAPI backend is not running. Start it from the sidebar to see tasks.")
    else:
        @st.fragment(run_every=timedelta(seconds=3))
        def _task_dashboard():
            tasks = fetch_tasks(30)
            if not tasks:
                st.info("No tasks yet. Trigger one via the Chrome extension, iOS Shortcut, or the API.")
                return

            for task in tasks:
                tid = task.get("id", "?")
                source = task.get("source", "?")
                detail = task.get("detail", "")
                status = task.get("status", "running")
                current = task.get("current_step", "")
                total = task.get("total_steps", 1)
                finished = task.get("finished_steps", 0)
                error = task.get("error")
                all_steps = task.get("all_steps", [])

                if status == "completed":
                    icon = "\u2705"
                elif status == "failed":
                    icon = "\u274C"
                else:
                    icon = "\u23F3"

                with st.container(border=True):
                    col_info, col_prog = st.columns([3, 5])
                    with col_info:
                        st.markdown(f"{icon} **`{tid}`** &mdash; `{source}`")
                        if detail:
                            st.caption(detail)
                    with col_prog:
                        progress_val = finished / total if total else 0
                        step_label = STEP_LABELS.get(current, current)

                        if status == "completed":
                            st.progress(1.0, text="\u2705 Completed")
                        elif status == "failed":
                            st.progress(progress_val, text=f"\u274C Failed: {error or 'unknown'}")
                        else:
                            st.progress(progress_val, text=f"\u23F3 {step_label}...")

                    if all_steps and status != "completed":
                        step_cols = st.columns(len(all_steps))
                        for i, step_name in enumerate(all_steps):
                            label = STEP_LABELS.get(step_name, step_name)
                            if i < finished:
                                step_cols[i].markdown(f"\u2705 ~~{label}~~")
                            elif step_name == current and status == "running":
                                step_cols[i].markdown(f"\u23F3 **{label}**")
                            else:
                                step_cols[i].markdown(f"\u2B1C {label}")

        _task_dashboard()

# ===================== Tab 2 — .env Configuration =====================
with tab_cfg:
    st.header("SMTP / Kindle Configuration")
    st.caption(
        "Edit the `.env` values below. main.py reads `.env` on startup, "
        "so changes take effect after restarting FastAPI."
    )
    env = load_env()

    def _detect_provider(smtp_server: str) -> str:
        for name, preset in EMAIL_PROVIDERS.items():
            if preset.get("SMTP_SERVER") == smtp_server:
                return name
        return "Custom"

    with st.form("env_form"):
        provider = st.selectbox(
            "Email Provider",
            list(EMAIL_PROVIDERS.keys()),
            index=list(EMAIL_PROVIDERS.keys()).index(
                _detect_provider(env.get("SMTP_SERVER", ""))
            ),
        )
        preset = EMAIL_PROVIDERS.get(provider, {})
        smtp_server = st.text_input(
            "SMTP Server",
            value=preset.get("SMTP_SERVER", env.get("SMTP_SERVER", "")),
            disabled=provider != "Custom",
        )
        smtp_port = st.text_input(
            "SMTP Port",
            value=preset.get("SMTP_PORT", env.get("SMTP_PORT", "")),
            disabled=provider != "Custom",
        )
        sender_email = st.text_input("Sender Email", value=env.get("SENDER_EMAIL", ""))
        sender_password = st.text_input(
            "Sender Password (App Password)",
            value=env.get("SENDER_PASSWORD", ""),
            type="password",
        )
        kindle_email = st.text_input("Kindle Email", value=env.get("KINDLE_EMAIL", ""))

        submitted = st.form_submit_button("\U0001F4BE  Save & Restart FastAPI")
        if submitted:
            final_server = preset.get("SMTP_SERVER", smtp_server.strip())
            final_port = preset.get("SMTP_PORT", smtp_port.strip())
            new_env = {
                "SMTP_SERVER": final_server,
                "SMTP_PORT": final_port,
                "SENDER_EMAIL": sender_email.strip(),
                "SENDER_PASSWORD": sender_password.strip(),
                "KINDLE_EMAIL": kindle_email.strip(),
            }
            errors = validate_env(new_env)
            if errors:
                for err in errors:
                    st.error(err)
            else:
                save_env(new_env)
                stop_fastapi()
                time.sleep(1)
                start_fastapi()
                time.sleep(2)
                st.success(".env saved and FastAPI restarted.")
                st.rerun()

# ===================== Tab 3 — RSS Feed Manager =======================
with tab_rss:
    st.header("RSS Feed Manager")
    st.caption("Manage feeds in `feeds.json`. The RSS Worker re-reads this file every cycle.")

    feeds_data = load_feeds()
    feeds_list = feeds_data.get("feeds", [])

    interval = st.number_input(
        "Check interval (minutes)",
        min_value=1,
        max_value=1440,
        value=feeds_data.get("interval_minutes", 60),
        step=5,
    )

    st.subheader("Current Feeds")
    if not feeds_list:
        st.info("No feeds configured yet. Add one below.")
    indices_to_delete = []
    for i, feed in enumerate(feeds_list):
        col_url, col_name, col_del = st.columns([5, 3, 1])
        col_url.code(feed.get("url", ""), language=None)
        col_name.write(feed.get("name", "\u2014"))
        if col_del.button("\U0001F5D1\uFE0F", key=f"del_{i}"):
            indices_to_delete.append(i)

    if indices_to_delete:
        for idx in sorted(indices_to_delete, reverse=True):
            feeds_list.pop(idx)
        feeds_data["feeds"] = feeds_list
        save_feeds(feeds_data)
        st.rerun()

    st.subheader("Add Feed")
    with st.form("add_feed"):
        new_url = st.text_input("Feed URL")
        new_name = st.text_input("Label (optional)")
        do_validate = st.checkbox("Validate feed before adding", value=True)
        add_clicked = st.form_submit_button("\u2795  Add Feed")

        if add_clicked:
            url = new_url.strip()
            if not url:
                st.warning("Please enter a feed URL.")
            else:
                if do_validate:
                    with st.spinner("Validating feed..."):
                        ok, msg = validate_feed_url(url)
                    if not ok:
                        st.error(f"Feed validation failed: {msg}")
                    else:
                        st.success(msg)
                        feeds_list.append({"url": url, "name": new_name.strip() or url[:50]})
                        feeds_data["feeds"] = feeds_list
                        feeds_data["interval_minutes"] = interval
                        save_feeds(feeds_data)
                        st.rerun()
                else:
                    feeds_list.append({"url": url, "name": new_name.strip() or url[:50]})
                    feeds_data["feeds"] = feeds_list
                    feeds_data["interval_minutes"] = interval
                    save_feeds(feeds_data)
                    st.success(f"Added: {url}")
                    st.rerun()

    if st.button("\U0001F4BE  Save & Restart Worker"):
        feeds_data["interval_minutes"] = interval
        save_feeds(feeds_data)
        stop_rss_worker()
        time.sleep(1)
        start_rss_worker()
        time.sleep(1)
        st.success("feeds.json saved and RSS Worker restarted.")
        st.rerun()

# ===================== Tab 4 — Testing & Logs =========================
with tab_test:
    st.header("Testing & Diagnostics")

    col_check, col_send = st.columns(2)

    with col_check:
        st.subheader("\U0001F50C  Google SMTP Connection Check")
        st.caption("Tests SMTP login to Gmail (no email sent). Verifies credentials only.")
        if st.button("Check Gmail Connection", key="btn_smtp_check"):
            env = load_env()
            with st.spinner("Connecting to Gmail SMTP..."):
                ok, msg = check_google_smtp(
                    env.get("SMTP_SERVER", ""),
                    env.get("SMTP_PORT", "587"),
                    env.get("SENDER_EMAIL", ""),
                    env.get("SENDER_PASSWORD", ""),
                )
            if ok:
                st.success(msg)
            else:
                st.error(msg)

    with col_send:
        st.subheader("\U0001F4E7  Send Test Email")
        st.caption("Send a plain-text test email to your Kindle address to verify full delivery.")
        if st.button("Send Test Email", key="btn_test_email"):
            env = load_env()
            with st.spinner("Sending test email..."):
                ok, msg = send_test_email(
                    env.get("SMTP_SERVER", ""),
                    env.get("SMTP_PORT", "587"),
                    env.get("SENDER_EMAIL", ""),
                    env.get("SENDER_PASSWORD", ""),
                    env.get("KINDLE_EMAIL", ""),
                )
            if ok:
                st.success(msg)
            else:
                st.error(msg)

    st.markdown("---")

    st.subheader("\U0001F4DC  Logs")

    log_tab_api, log_tab_rss = st.tabs(["FastAPI", "RSS Worker"])

    with log_tab_api:
        err_log = _tail(LOGS_DIR / "fastapi.err.log")
        size = _log_size_mb(LOGS_DIR / "fastapi.err.log")
        st.caption(f"fastapi.err.log ({size:.1f} MB)")
        if err_log:
            st.code(err_log, language="text")
        else:
            st.info("No FastAPI logs yet. Start the server first.")

    with log_tab_rss:
        rss_log = _tail(LOGS_DIR / "rss_worker.err.log")
        size = _log_size_mb(LOGS_DIR / "rss_worker.err.log")
        st.caption(f"rss_worker.err.log ({size:.1f} MB)")
        if rss_log:
            st.code(rss_log, language="text")
        else:
            st.info("No RSS Worker logs yet. Start the worker first.")
