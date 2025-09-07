#!/usr/bin/env python3
# otp_forwarder.py (auto date version)

import os
import time
import json
import re
import logging
import requests
from typing import Optional
from datetime import datetime

# ---------------- Config ----------------
BOT_TOKEN = os.getenv("BOT_TOKEN")
CHAT_ID = os.getenv("CHAT_ID")
USERNAME = os.getenv("USERNAME")
PASSWORD = os.getenv("PASSWORD")
BASE_URL = os.getenv("BASE_URL")  # e.g. http://94.23.120.156
POLL_INTERVAL = int(os.getenv("POLL_INTERVAL", "15"))
ALREADY_FILE = os.getenv("ALREADY_SENT_FILE", "already_sent.json")

LOGIN_PAGE_URL = f"{BASE_URL.rstrip('/')}/ints/login" if BASE_URL else None
LOGIN_POST_URL = f"{BASE_URL.rstrip('/')}/ints/signin" if BASE_URL else None
DATA_URL_BASE = f"{BASE_URL.rstrip('/')}/ints/agent/res/data_smscdr.php" if BASE_URL else None

# ---------------- Logging ----------------
logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
log = logging.getLogger("otp_forwarder")

# ---------------- HTTP session ----------------
session = requests.Session()
session.headers.update({
    "User-Agent": "Mozilla/5.0",
    "Accept": "application/json, text/javascript, */*; q=0.01",
    "X-Requested-With": "XMLHttpRequest",
})

TELEGRAM_SEND_URL = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage" if BOT_TOKEN else None

# ---------------- Helpers ----------------
def load_already_sent(path: str):
    try:
        with open(path, "r", encoding="utf-8") as f:
            return set(json.load(f))
    except FileNotFoundError:
        return set()
    except Exception as e:
        log.warning("Could not load already_sent file: %s", e)
        return set()

def save_already_sent(path: str, s: set):
    try:
        with open(path, "w", encoding="utf-8") as f:
            json.dump(list(s), f)
    except Exception as e:
        log.warning("Could not save already_sent file: %s", e)

def escape_md_v2(text: str) -> str:
    return re.sub(r'([_*[\]()~`>#+=|{}.!-])', r'\\\1', str(text or ""))

def extract_otp(message: str) -> Optional[str]:
    if not message:
        return None
    m = re.search(r'(?i)(?:otp|code|pin|passcode|verification)[^\d]{0,10}(\d{3,8})', message)
    if m:
        return m.group(1)
    m2 = re.search(r'(?<!\d)(\d{3,8})(?!\d)', message)
    if m2:
        return m2.group(1)
    return None

def send_telegram(chat_id: str, text: str) -> bool:
    if not TELEGRAM_SEND_URL:
        log.error("BOT_TOKEN not set.")
        return False
    try:
        r = requests.post(TELEGRAM_SEND_URL, data={
            "chat_id": chat_id,
            "text": text,
            "parse_mode": "MarkdownV2"
        }, timeout=15)
        if r.ok:
            return True
        log.warning("Telegram send failed: %s %s", r.status_code, r.text)
        return False
    except Exception as e:
        log.error("Telegram exception: %s", e)
        return False

# ---------------- Login & fetch ----------------
def build_data_url():
    today = datetime.now().strftime("%Y-%m-%d")
    fdate1 = f"{today} 00:00:00"
    fdate2 = f"{today} 23:59:59"
    return f"{DATA_URL_BASE}?fdate1={fdate1}&fdate2={fdate2}&sEcho=1&iColumns=9&iDisplayStart=0&iDisplayLength=25"

def login_and_fetch():
    try:
        log.info("GET login page: %s", LOGIN_PAGE_URL)
        r = session.get(LOGIN_PAGE_URL, timeout=12)

        payload = {"username": USERNAME, "password": PASSWORD}
        m = re.search(r'(\d+)\s*\+\s*(\d+)', r.text)
        if m:
            payload["capt"] = int(m.group(1)) + int(m.group(2))
            log.info("Solved captcha: %s", payload["capt"])

        r2 = session.post(LOGIN_POST_URL, data=payload, timeout=12)
        log.info("Login POST status: %s", r2.status_code)

        if r2.ok and ("dashboard" in r2.text.lower() or "logout" in r2.text.lower()):
            log.info("Login success ✅ fetching data…")
            data_url = build_data_url()
            log.info("Fetching: %s", data_url)
            r3 = session.get(data_url, headers={"X-Requested-With": "XMLHttpRequest"}, timeout=15)

            if r3.ok:
                try:
                    return r3.json()
                except Exception as e:
                    log.error("Data JSON decode failed: %s", e)
                    log.debug("Raw response: %s", r3.text[:500])
            else:
                log.warning("Data fetch failed with status %s", r3.status_code)
                log.debug("Raw response: %s", r3.text[:500])
        else:
            log.warning("Login failed or unexpected response.")
    except Exception as e:
        log.error("Login error: %s", e)
    return None

def parse_provider_data(data):
    out = []
    if isinstance(data, dict) and "aaData" in data:
        for row in data["aaData"]:
            try:
                out.append({
                    "date": str(row[0]),
                    "number": str(row[2]),
                    "service": str(row[3]),
                    "message": str(row[5]),
                })
            except:
                continue
    return out

# ---------------- Main loop ----------------
def main_loop():
    if not BOT_TOKEN or not CHAT_ID:
        log.error("BOT_TOKEN or CHAT_ID missing.")
        return

    already = load_already_sent(ALREADY_FILE)
    log.info("Forwarder started. Poll interval: %s sec", POLL_INTERVAL)

    while True:
        data = login_and_fetch()
        msgs = parse_provider_data(data)
        for m in msgs:
            otp = extract_otp(m.get("message", ""))
            if not otp:
                continue
            key = f"{m['number']}|{otp}"
            if key in already:
                continue
            text = f"🔑 OTP: `{escape_md_v2(otp)}`\n📞 From: `{escape_md_v2(m['number'])}`\n💬 `{escape_md_v2(m['message'])}`"
            if send_telegram(CHAT_ID, text):
                already.add(key)
                save_already_sent(ALREADY_FILE, already)
                log.info("Forwarded OTP %s from %s", otp, m['number'])
        time.sleep(POLL_INTERVAL)

# ---------------- Entrypoint ----------------
if __name__ == "__main__":
    log.info("Starting otp_forwarder (auto-date).")
    log.info("LOGIN_PAGE_URL=%s DATA_URL_BASE=%s", LOGIN_PAGE_URL, DATA_URL_BASE)
    main_loop()
