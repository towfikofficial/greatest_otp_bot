#!/usr/bin/env python3
# greatest_otp_bot.py
# Seven1Tel login+fetch -> Telegram OTP forwarder
# DO NOT put secrets in this file. Use Railway environment variables.

import os
import time
import json
import re
import logging
import requests
from typing import Optional

# optional niceties (if installed)
try:
    import phonenumbers
    import pycountry
    HAVE_PH = True
except Exception:
    HAVE_PH = False

# ---------------- Config (from env) ----------------
BOT_TOKEN = os.getenv("BOT_TOKEN")
CHAT_ID = os.getenv("CHAT_ID")
USERNAME = os.getenv("USERNAME")
PASSWORD = os.getenv("PASSWORD")
BASE_URL = os.getenv("BASE_URL")  # e.g. http://94.23.120.156
POLL_INTERVAL = int(os.getenv("POLL_INTERVAL", "3"))
ALREADY_FILE = os.getenv("ALREADY_SENT_FILE", "already_sent.json")

LOGIN_PAGE_URL = (BASE_URL.rstrip("/") + "/ints/login") if BASE_URL else None
LOGIN_POST_URL = (BASE_URL.rstrip("/") + "/ints/signin") if BASE_URL else None
DATA_URL = (BASE_URL.rstrip("/") + "/ints/agent/res/data_smscdr.php") if BASE_URL else None

# ---------------- Logging ----------------
logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
log = logging.getLogger("greatest_otp_bot")

# ---------------- HTTP session & Telegram helper ----------------
session = requests.Session()
session.headers.update({"User-Agent": "Mozilla/5.0 (seven1-forwarder)"})

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

    # normalize separators/spaces: "12-34-56" -> "123456", "6 9 4 6" -> "6946"
    normalized = re.sub(r'[\s\-]+', '', text)
    normalized = re.sub(r'(\d)\s+(\d)', r'\1\2', normalized)

    # 1) keyword-based: code/otp/pin near digits
    kw = re.compile(r'(?i)\b(?:code|otp|pin|passcode|verification|security code|your code|one-time|verification code)[^\d]{0,12}(\d{3,6})\b')
    m = kw.search(text)
    if m:
        return m.group(1)

    # 2) normalized search for 3-6 digits
    m2 = re.search(r'(?<!\d)(\d{3,6})(?!\d)', normalized)
    if m2:
        return m2.group(1)

    # 3) fallback: any 3-6 digit sequence in original
    m3 = re.search(r'(?<!\d)(\d{3,6})(?!\d)', text)
    if m3:
        return m3.group(1)

    return None

# ---------------- Telegram sender ----------------
def send_telegram(chat_id: str, text: str) -> bool:
    if not TELEGRAM_SEND_URL:
        log.error("BOT_TOKEN not set. Cannot send to Telegram.")
        return False
    payload = {
        "chat_id": chat_id,
        "text": text,
        "parse_mode": "MarkdownV2",
        "disable_web_page_preview": True
    }
    try:
        r = requests.post(TELEGRAM_SEND_URL, data=payload, timeout=15)
        if r.status_code != 200:
            log.warning("Telegram send failed: %s %s", r.status_code, r.text[:200])
            return False
        return True
    except Exception as e:
        log.exception("Telegram send exception: %s", e)
        return False

# ---------------- Provider: login + fetch ----------------
def login_and_fetch():
    """
    Login to the panel and fetch DATA_URL JSON.
    Returns JSON object or None.
    """
    if not (LOGIN_PAGE_URL and LOGIN_POST_URL and USERNAME and PASSWORD and DATA_URL):
        log.error("Missing LOGIN_PAGE_URL/LOGIN_POST_URL/USERNAME/PASSWORD/DATA_URL")
        return None

    try:
        log.info("GET login page: %s", LOGIN_PAGE_URL)
        r = session.get(LOGIN_PAGE_URL, timeout=12)
        if not r.ok:
            log.warning("Login page returned: %s", r.status_code)

        # try to auto-solve simple arithmetic captcha shown like "What is 3 + 4"
        m = re.search(r'(\d+)\s*\+\s*(\d+)', r.text)
        payload = {"username": USERNAME, "password": PASSWORD}
        if m:
            try:
                payload["capt"] = int(m.group(1)) + int(m.group(2))
                log.info("Solved simple captcha: %s", payload["capt"])
            except Exception:
                pass

        headers = {"Content-Type": "application/x-www-form-urlencoded", "Referer": LOGIN_PAGE_URL}
        r2 = session.post(LOGIN_POST_URL, data=payload, headers=headers, timeout=12)
        log.info("Login POST status: %s", r2.status_code)

        # Heuristics for success: 200 + "dashboard" or "logout" in response
        if r2.ok and ("dashboard" in r2.text.lower() or "logout" in r2.text.lower() or r2.status_code == 200):
            log.info("Login seems ok, fetching DATA_URL: %s", DATA_URL)
            r3 = session.get(DATA_URL, headers={"X-Requested-With":"XMLHttpRequest"}, timeout=15)
            log.info("Data URL status: %s", r3.status_code)
            if r3.ok:
                try:
                    return r3.json()
                except Exception as e:
                    log.warning("Data endpoint JSON decode failed: %s", e)
                    return None
        else:
            log.warning("Login likely failed or unexpected response content.")
            return None

    except Exception as e:
        log.exception("login_and_fetch exception: %s", e)
        return None

# ---------------- Parse provider JSON to normalized messages ----------------
def parse_provider_data(data):
    out = []
    if not data:
        return out

    # datatables style aaData (common)
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

    # wrapped dict with messages/data/items
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

    log.debug("Provider response format not recognized.")
    return out

# ---------------- Main loop ----------------
def main_loop():
    if not BOT_TOKEN or not CHAT_ID:
        log.error("BOT_TOKEN or CHAT_ID missing in environment. Set them in Railway variables.")
        return

    already = load_already_sent(ALREADY_FILE)
    log.info("Forwarder started. Poll interval: %s seconds", POLL_INTERVAL)
    while True:
        try:
            data = login_and_fetch()
            if not data:
                log.debug("No data returned from provider.")
            msgs = parse_provider_data(data)
            if not msgs:
                log.debug("No messages parsed this tick.")

            for m in msgs:
                number = (m.get("number") or "").strip()
                message = (m.get("message") or "").strip()
                service = (m.get("service") or "").strip()
                date = (m.get("date") or "").strip()

                if not number or not message:
                    continue

                otp = extract_otp(message)
                if not otp:
                    log.debug("No OTP in message: %s", message[:80])
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
                    f"📱 Service: {escape_md_v2(service)}`\n"
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
    log.info("Starting greatest_otp_bot forwarder (login+fetch).")
    log.info("LOGIN_PAGE_URL=%s DATA_URL=%s", LOGIN_PAGE_URL, DATA_URL)
    main_loop()
