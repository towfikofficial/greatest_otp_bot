#!/usr/bin/env python3
"""
Seven1Tel login+fetch -> Telegram forwarder (env-driven)
Do NOT put credentials in this file. Set them as Railway Environment Variables.
Required env vars:
  BOT_TOKEN, CHAT_ID, USERNAME, PASSWORD, BASE_URL
Optional:
  POLL_INTERVAL (seconds) default 3
"""

import os
import time
import json
import re
import logging
from typing import Optional

import requests

# Optional country libs (install if you want): phonenumbers, pycountry
try:
    import phonenumbers, pycountry
    HAVE_PH = True
except Exception:
    HAVE_PH = False

# ---------------- Config from env ----------------
BOT_TOKEN = os.getenv("BOT_TOKEN")
CHAT_ID = os.getenv("CHAT_ID")          # target chat or group id (string)
USERNAME = os.getenv("USERNAME")
PASSWORD = os.getenv("PASSWORD")
BASE_URL = os.getenv("BASE_URL")        # e.g. http://94.23.120.156
POLL_INTERVAL = int(os.getenv("POLL_INTERVAL", "3"))

# Derived URLs
LOGIN_PAGE_URL = (BASE_URL.rstrip("/") + "/ints/login") if BASE_URL else None
LOGIN_POST_URL = (BASE_URL.rstrip("/") + "/ints/signin") if BASE_URL else None
DATA_URL = (BASE_URL.rstrip("/") + "/ints/agent/res/data_smscdr.php") if BASE_URL else None

ALREADY_FILE = "already_sent.json"

# ---------------- Logging ----------------
logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
log = logging.getLogger("seven1-forwarder")

# ---------------- HTTP session & Telegram ----------------
session = requests.Session()
session.headers.update({"User-Agent": "Mozilla/5.0"})

TELEGRAM_SEND_URL = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage" if BOT_TOKEN else None

# ---------------- Helpers ----------------
def load_already_sent(path: str):
    try:
        with open(path, "r", encoding="utf-8") as f:
            return set(json.load(f))
    except Exception:
        return set()

def save_already_sent(path: str, s: set):
    try:
        with open(path, "w", encoding="utf-8") as f:
            json.dump(list(s), f)
    except Exception as e:
        log.warning("Could not save already_sent: %s", e)

def escape_md_v2(text: str) -> str:
    if text is None:
        return ""
    return re.sub(r'([_*[\]()~`>#+=|{}.!-])', r'\\\1', str(text))

def get_country_info(phone_number: str):
    if not HAVE_PH or not phone_number:
        return "", ""
    try:
        num = "+" + phone_number.strip().lstrip("+")
        pn = phonenumbers.parse(num, None)
        if not phonenumbers.is_valid_number(pn):
            return "❓", "Invalid"
        region = phonenumbers.region_code_for_number(pn)
        country = pycountry.countries.get(alpha_2=region)
        country_name = country.name if country else "Unknown"
        flag = ''.join(chr(127397 + ord(c)) for c in region) if region else ""
        return flag, country_name
    except Exception:
        return "❓", "Unknown"

# Flexible OTP extractor
def extract_otp(message: str) -> Optional[str]:
    if not message:
        return None
    text = message.strip()
    normalized = re.sub(r'[\s\-]+', '', text)
    normalized = re.sub(r'(\d)\s+(\d)', r'\1\2', normalized)

    kw = re.compile(r'(?i)\b(?:code|otp|pin|passcode|verification|security code|your code|one-time)[^\d]{0,12}(\d{3,6})\b')
    m = kw.search(text)
    if m:
        return m.group(1)

    m2 = re.search(r'(?<!\d)(\d{3,6})(?!\d)', normalized)
    if m2:
        return m2.group(1)

    m3 = re.search(r'(?<!\d)(\d{3,6})(?!\d)', text)
    if m3:
        return m3.group(1)

    return None

# Send Telegram (simple POST via Bot API)
def send_telegram(chat_id: str, text: str) -> bool:
    if not TELEGRAM_SEND_URL:
        log.error("BOT_TOKEN not set, cannot send to Telegram.")
        return False
    payload = {
        "chat_id": chat_id,
        "text": text,
        "parse_mode": "MarkdownV2",
        "disable_web_page_preview": True
    }
    try:
        r = requests.post(TELEGRAM_SEND_URL, data=payload, timeout=12)
        if r.status_code != 200:
            log.warning("Telegram send failed %s: %s", r.status_code, r.text[:200])
            return False
        return True
    except Exception as e:
        log.exception("Telegram send exception: %s", e)
        return False

# ---------------- Login + Fetch ----------------
def login_and_fetch():
    """
    Login to panel and try to fetch JSON from DATA_URL.
    Returns parsed JSON (object) or None.
    """
    if not (LOGIN_PAGE_URL and LOGIN_POST_URL and USERNAME and PASSWORD and DATA_URL):
        log.error("Missing LOGIN_PAGE_URL/LOGIN_POST_URL/USERNAME/PASSWORD/DATA_URL in environment.")
        return None

    try:
        # get login page (to read captcha if exists)
        resp = session.get(LOGIN_PAGE_URL, timeout=10)
        if not resp.ok:
            log.warning("Login page GET returned %s", resp.status_code)

        # try simple arithmetic captcha detection
        m = re.search(r'(\d+)\s*\+\s*(\d+)', resp.text)
        payload = {"username": USERNAME, "password": PASSWORD}
        if m:
            try:
                payload["capt"] = int(m.group(1)) + int(m.group(2))
                log.info("Solved simple captcha: %s", payload["capt"])
            except Exception:
                pass

        headers = {"Content-Type": "application/x-www-form-urlencoded", "Referer": LOGIN_PAGE_URL}
        r2 = session.post(LOGIN_POST_URL, data=payload, headers=headers, timeout=10)
        log.info("Login POST status: %s", r2.status_code)

        if not r2.ok:
            log.warning("Login POST not OK, status %s", r2.status_code)
            return None

        # try fetch data
        r3 = session.get(DATA_URL, headers={"X-Requested-With": "XMLHttpRequest"}, timeout=12)
        log.info("Data URL GET status: %s", r3.status_code)
        if r3.ok:
            try:
                return r3.json()
            except Exception as e:
                log.warning("Data JSON decode failed: %s", e)
                return None
        else:
            log.warning("Data URL returned %s", r3.status_code)
            return None

    except Exception as e:
        log.exception("login_and_fetch error: %s", e)
        return None

# ---------------- Parse provider JSON ----------------
def parse_provider_data(data):
    out = []
    if not data:
        return out
    # datatables style aaData
    if isinstance(data, dict) and "aaData" in data and isinstance(data["aaData"], list):
        for row in data["aaData"]:
            try:
                date = str(row[0]) if len(row) > 0 else ""
                number = str(row[2]) if len(row) > 2 else ""
                service = str(row[3]) if len(row) > 3 else ""
                message = str(row[5]) if len(row) > 5 else ""
                out.append({"number": number, "message": message, "service": service, "date": date})
            except Exception:
                continue
        return out
    # list of dicts
    if isinstance(data, list):
        for item in data:
            if isinstance(item, dict):
                number = item.get("number") or item.get("from") or item.get("msisdn") or ""
                message = item.get("message") or item.get("text") or item.get("body") or ""
                service = item.get("service") or ""
                date = item.get("date") or item.get("time") or ""
                out.append({"number": str(number), "message": str(message), "service": service, "date": date})
        return out
    # wrapped dict
    if isinstance(data, dict):
        for key in ("messages", "data", "items"):
            if key in data and isinstance(data[key], list):
                for item in data[key]:
                    if isinstance(item, dict):
                        number = item.get("number") or item.get("from") or item.get("msisdn") or ""
                        message = item.get("message") or item.get("text") or item.get("body") or ""
                        service = item.get("service") or ""
                        date = item.get("date") or item.get("time") or ""
                        out.append({"number": str(number), "message": str(message), "service": service, "date": date})
                if out:
                    return out
    return out

# ---------------- Main loop ----------------
def main_loop():
    if not (BOT_TOKEN and CHAT_ID):
        log.error("BOT_TOKEN or CHAT_ID missing in environment. Set them in Railway variables.")
        return

    already = load_already_sent(ALREADY_FILE)
    log.info("Forwarder started. Poll interval: %s sec", POLL_INTERVAL)

    while True:
        try:
            data = login_and_fetch()
            if data is None:
                log.debug("No data returned from provider this round.")
            msgs = parse_provider_data(data)
            if not msgs:
                log.debug("No messages parsed from provider response.")

            for m in msgs:
                number = (m.get("number") or "").strip()
                message = (m.get("message") or "").strip()
                service = (m.get("service") or "").strip()
                date = (m.get("date") or "").strip()
                if not number or not message:
                    continue

                otp = extract_otp(message)
                if not otp:
                    log.debug("OTP not found in message: %s", message[:80])
                    continue

                key = f"{number}|{otp}"
                if key in already:
                    log.debug("Already forwarded: %s", key)
                    continue

                flag, country = get_country_info(number)
                now = date or time.strftime("%Y-%m-%d %H:%M:%S")
                text = (
                    f"✨ OTP FORWARDED ✨\n\n"
                    f"⏰ Time: {escape_md_v2(now)}\n"
                    f"📞 Number: {escape_md_v2(number)}\n"
                    f"🔑 OTP: {escape_md_v2(otp)}\n"
                    f"🌍 Country: {flag} {escape_md_v2(country)}\n"
                    f"📱 Service: {escape_md_v2(service)}\n"
                    f"💬 Message:\n{escape_md_v2(message)}"
                )

                ok = send_telegram(CHAT_ID, text)
                if ok:
                    already.add(key)
                    save_already_sent(ALREADY_FILE, already)
                    log.info("Forwarded OTP %s from %s", otp, number)
                else:
                    log.warning("Failed to forward OTP %s from %s", otp, number)

        except Exception as e:
            log.exception("Main loop error: %s", e)

        time.sleep(POLL_INTERVAL)

# ---------------- Entrypoint ----------------
if _name_ == "_main_":
    log.info("Starting Seven1Tel -> Telegram forwarder (login+fetch mode).")
    log.info("LOGIN_PAGE_URL=%s DATA_URL=%s", LOGIN_PAGE_URL, DATA_URL)
    main_loop()
