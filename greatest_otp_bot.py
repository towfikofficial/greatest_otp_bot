#!/usr/bin/env python3
# otp_forwarder.py
# Seven1Tel login -> fetch -> forward raw data to Telegram

import os
import time
import json
import re
import logging
import requests

# ---------------- Config ----------------
BOT_TOKEN = os.getenv("TELEGRAM_TOKEN")
CHAT_ID = os.getenv("CHAT_ID")
USERNAME = os.getenv("PORTAL_USER")
PASSWORD = os.getenv("PORTAL_PASS")
LOGIN_URL = os.getenv("LOGIN_URL")        # যেমন: http://94.23.120.156/ints/login
DATA_URL = os.getenv("DATA_URL")          # যেমন: http://94.23.120.156/ints/agent/res/data_smscdr.php
POLL_INTERVAL = int(os.getenv("POLL_INTERVAL", "10"))
ALREADY_FILE = "already_sent.json"

# ---------------- Logging ----------------
logging.basicConfig(level=logging.INFO,
                    format="%(asctime)s - %(levelname)s - %(message)s")
log = logging.getLogger("otp_forwarder")

# ---------------- HTTP session ----------------
session = requests.Session()
session.headers.update({
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)",
    "Accept": "application/json, text/javascript, */*; q=0.01",
    "X-Requested-With": "XMLHttpRequest",
})

TELEGRAM_URL = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"

# ---------------- Helpers ----------------
def load_already_sent():
    try:
        with open(ALREADY_FILE, "r", encoding="utf-8") as f:
            return set(json.load(f))
    except FileNotFoundError:
        return set()
    except Exception as e:
        log.warning("Could not load already_sent file: %s", e)
        return set()

def save_already_sent(s: set):
    try:
        with open(ALREADY_FILE, "w", encoding="utf-8") as f:
            json.dump(list(s), f)
    except Exception as e:
        log.warning("Could not save already_sent file: %s", e)

def send_telegram(text: str) -> bool:
    if not BOT_TOKEN or not CHAT_ID:
        log.error("BOT_TOKEN or CHAT_ID missing.")
        return False
    try:
        r = requests.post(TELEGRAM_URL, data={
            "chat_id": CHAT_ID,
            "text": text
        }, timeout=15)
        if r.ok:
            return True
        log.warning("Telegram send failed: %s %s", r.status_code, r.text)
        return False
    except Exception as e:
        log.error("Telegram exception: %s", e)
        return False

# ---------------- Login & fetch ----------------
def login_and_fetch():
    try:
        # login page
        r = session.get(LOGIN_URL, timeout=12)

        payload = {"username": USERNAME, "password": PASSWORD}
        # captcha solver (যদি simple যোগফল থাকে)
        m = re.search(r'(\d+)\s*\+\s*(\d+)', r.text)
        if m:
            payload["capt"] = int(m.group(1)) + int(m.group(2))
            log.info("Solved captcha: %s", payload["capt"])

        # login submit
        r2 = session.post(LOGIN_URL.replace("login", "signin"),
                          data=payload, timeout=12)
        if not r2.ok:
            log.error("Login failed with %s", r2.status_code)
            return None

        # fetch data
        r3 = session.get(DATA_URL, timeout=15)
        if r3.ok:
            try:
                return r3.json()
            except Exception as e:
                log.error("JSON decode failed: %s", e)
                log.debug("Raw: %s", r3.text[:500])
        else:
            log.warning("Data fetch failed: %s", r3.status_code)
    except Exception as e:
        log.error("Login error: %s", e)
    return None

# ---------------- Parser ----------------
def parse_provider_data(data):
    out = []
    if isinstance(data, dict) and "aaData" in data:
        for row in data["aaData"]:
            try:
                out.append({
                    "date": str(row[0]),
                    "info": str(row[1]),
                    "number": str(row[2]),
                    "service": str(row[3]),
                    "user": str(row[4]),
                    "message": str(row[5]),
                })
            except:
                continue
    return out

# ---------------- Main loop ----------------
def main_loop():
    already = load_already_sent()
    log.info("Forwarder started. Poll interval: %s sec", POLL_INTERVAL)

    while True:
        data = login_and_fetch()
        msgs = parse_provider_data(data)
        for m in msgs:
            key = f"{m['date']}|{m['number']}|{m['message']}"
            if key in already:
                continue
            text = f"📩 RAW DATA\n\n🕒 {m['date']}\n📞 {m['number']}\n💬 {m['message']}\n⚙️ {m['service']}"
            if send_telegram(text):
                already.add(key)
                save_already_sent(already)
                log.info("Forwarded data from %s", m['number'])
        time.sleep(POLL_INTERVAL)

# ---------------- Entrypoint ----------------
if __name__ == "__main__":
    log.info("Starting OTP forwarder...")
    main_loop()
