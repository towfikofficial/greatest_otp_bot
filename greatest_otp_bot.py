#!/usr/bin/env python3
# otp_forwarder.py (final with telegram send)

import os
import time
import json
import re
import logging
import requests
from bs4 import BeautifulSoup

# ---------------- Config ----------------
BOT_TOKEN = os.getenv("BOT_TOKEN")
CHAT_ID = os.getenv("CHAT_ID")
USERNAME = os.getenv("USERNAME")
PASSWORD = os.getenv("PASSWORD")
BASE_URL = os.getenv("BASE_URL")  # http://94.23.120.156
DATA_URL = os.getenv("DATA_URL")  # full link with fdate1,fdate2 etc.
POLL_INTERVAL = int(os.getenv("POLL_INTERVAL", "15"))

LOGIN_PAGE_URL = f"{BASE_URL.rstrip('/')}/ints/login" if BASE_URL else None
LOGIN_POST_URL = f"{BASE_URL.rstrip('/')}/ints/signin" if BASE_URL else None

TELEGRAM_SEND_URL = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage" if BOT_TOKEN else None
ALREADY_FILE = "already_sent.json"

# ---------------- Logging ----------------
logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
log = logging.getLogger("otp_forwarder")

# ---------------- Helpers ----------------
def load_already_sent(path: str):
    try:
        with open(path, "r", encoding="utf-8") as f:
            return set(json.load(f))
    except:
        return set()

def save_already_sent(path: str, s: set):
    try:
        with open(path, "w", encoding="utf-8") as f:
            json.dump(list(s), f)
    except:
        pass

def escape_md(text: str) -> str:
    return re.sub(r'([_*[\]()~`>#+=|{}.!-])', r'\\\1', str(text or ""))

def extract_otp(message: str):
    if not message:
        return None
    m = re.search(r'(?i)(?:otp|code|pin|verification)[^\d]{0,10}(\d{3,8})', message)
    if m:
        return m.group(1)
    m2 = re.search(r'(?<!\d)(\d{3,8})(?!\d)', message)
    if m2:
        return m2.group(1)
    return None

def send_telegram(text: str):
    if not TELEGRAM_SEND_URL:
        log.error("❌ BOT_TOKEN missing")
        return False
    try:
        r = requests.post(TELEGRAM_SEND_URL, data={
            "chat_id": CHAT_ID,
            "text": text
        })
        return r.ok
    except Exception as e:
        log.error(f"⚠️ Telegram send failed: {e}")
        return False

# ---------------- Login & fetch ----------------
session = requests.Session()
session.headers.update({"User-Agent": "Mozilla/5.0"})

def login():
    try:
        r = session.get(LOGIN_PAGE_URL, timeout=10)
        if r.status_code != 200:
            log.error(f"❌ Login page load failed: {r.status_code}")
            return False

        payload = {"username": USERNAME, "password": PASSWORD}
        m = re.search(r'(\d+)\s*\+\s*(\d+)', r.text)
        if m:
            payload["capt"] = int(m.group(1)) + int(m.group(2))
            log.info(f"🧮 Captcha solved: {payload['capt']}")

        r2 = session.post(LOGIN_POST_URL, data=payload, timeout=10)
        if r2.ok and ("dashboard" in r2.text.lower() or "logout" in r2.text.lower()):
            log.info("✅ Login success")
            return True
        else:
            log.error("❌ Login failed")
            return False
    except Exception as e:
        log.error(f"⚠️ Login error: {e}")
        return False

def fetch_data():
    try:
        r = session.get(DATA_URL, headers={"X-Requested-With": "XMLHttpRequest"}, timeout=15)
        if r.status_code == 200:
            try:
                return r.json()
            except:
                log.warning("⚠️ Response not JSON, raw returned")
                return r.text
        else:
            log.error(f"❌ Data fetch failed: {r.status_code}")
    except Exception as e:
        log.error(f"⚠️ Fetch error: {e}")
    return None

def parse_messages(data):
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
    already = load_already_sent(ALREADY_FILE)
    while True:
        if not login():
            time.sleep(POLL_INTERVAL)
            continue

        data = fetch_data()
        msgs = parse_messages(data)
        for m in msgs:
            otp = extract_otp(m.get("message", ""))
            key = f"{m['number']}|{otp}"
            if key in already:
                continue
            text = f"🔑 OTP: {escape_md(otp)}\n📞 From: {escape_md(m['number'])}\n💬 {escape_md(m['message'])}"
            if send_telegram(text):
                already.add(key)
                save_already_sent(ALREADY_FILE, already)
                log.info(f"📩 OTP forwarded: {otp}")
        time.sleep(POLL_INTERVAL)

# ---------------- Entrypoint ----------------
if __name__ == "__main__":
    log.info("🚀 Starting OTP forwarder...")
    main_loop()
