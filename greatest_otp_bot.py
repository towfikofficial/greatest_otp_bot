#!/usr/bin/env python3
# otp_forwarder.py (simple Railway-ready version)

import os
import time
import json
import re
import logging
import requests

# ---------------- Config ----------------
BOT_TOKEN = os.getenv("BOT_TOKEN")
CHAT_ID = os.getenv("CHAT_ID")
USERNAME = os.getenv("USERNAME")
PASSWORD = os.getenv("PASSWORD")
BASE_URL = os.getenv("BASE_URL")  # e.g. http://94.23.120.156
POLL_INTERVAL = int(os.getenv("POLL_INTERVAL", "10"))

LOGIN_PAGE_URL = f"{BASE_URL.rstrip('/')}/ints/login"
LOGIN_POST_URL = f"{BASE_URL.rstrip('/')}/ints/signin"
DATA_URL = f"{BASE_URL.rstrip('/')}/ints/agent/res/data_smscdr.php"

TELEGRAM_URL = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(message)s")
log = logging.getLogger("otp-bot")

session = requests.Session()
session.headers.update({"User-Agent": "Mozilla/5.0 (otp-bot)"})

# ---------------- Helpers ----------------
def escape(text):
    return re.sub(r'([_*[\]()~`>#+=|{}.!-])', r'\\\1', text or "")

def extract_otp(msg: str):
    if not msg:
        return None
    m = re.search(r'(?<!\d)(\d{4,8})(?!\d)', msg)
    return m.group(1) if m else None

def send_telegram(msg: str):
    try:
        r = requests.post(TELEGRAM_URL, data={
            "chat_id": CHAT_ID,
            "text": msg,
            "parse_mode": "MarkdownV2"
        })
        return r.ok
    except Exception as e:
        log.error("Telegram error: %s", e)
        return False

# ---------------- Login + Fetch ----------------
def fetch_data():
    try:
        # login
        r = session.get(LOGIN_PAGE_URL, timeout=10)
        payload = {"username": USERNAME, "password": PASSWORD}

        m = re.search(r'(\d+)\s*\+\s*(\d+)', r.text)
        if m:
            payload["capt"] = int(m.group(1)) + int(m.group(2))

        r2 = session.post(LOGIN_POST_URL, data=payload, timeout=10)
        if not r2.ok:
            log.warning("Login failed")
            return []

        # fetch sms
        r3 = session.get(DATA_URL, headers={"X-Requested-With": "XMLHttpRequest"}, timeout=10)
        data = r3.json()
        return data.get("aaData", [])
    except Exception as e:
        log.error("Fetch error: %s", e)
        return []

# ---------------- Main Loop ----------------
def main():
    seen = set()
    log.info("OTP Forwarder started…")

    while True:
        rows = fetch_data()
        for row in rows:
            try:
                msg = str(row[5])
                number = str(row[2])
                otp = extract_otp(msg)
                if not otp:
                    continue
                key = f"{number}|{otp}"
                if key in seen:
                    continue

                text = f"🔑 OTP: `{escape(otp)}`\n📞 From: `{escape(number)}`\n💬 `{escape(msg)}`"
                if send_telegram(text):
                    seen.add(key)
                    log.info("Forwarded OTP %s from %s", otp, number)
            except Exception:
                continue
        time.sleep(POLL_INTERVAL)

if __name__ == "__main__":
    main()
