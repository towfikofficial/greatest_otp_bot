import os
import re
import json
import time
import asyncio
import logging
import requests
import phonenumbers
import pycountry
from telegram import Bot, InlineKeyboardMarkup, InlineKeyboardButton
from telegram.error import TimedOut

# === CONFIG (from Railway Variables) ===
BOT_TOKEN = os.getenv("BOT_TOKEN")
CHAT_ID = os.getenv("CHAT_ID")
USERNAME = os.getenv("USERNAME")
PASSWORD = os.getenv("PASSWORD")
BASE_URL = os.getenv("BASE_URL")
POLL_INTERVAL = int(os.getenv("POLL_INTERVAL", "5"))

LOGIN_PAGE_URL = BASE_URL + "/ints/login"
LOGIN_POST_URL = BASE_URL + "/ints/signin"
DATA_URL = BASE_URL + "/ints/agent/res/data_smscdr.php"

bot = Bot(token=BOT_TOKEN)
session = requests.Session()
session.headers.update({"User-Agent": "Mozilla/5.0"})

logging.basicConfig(level=logging.INFO, format="%(message)s")

def escape_markdown(text: str) -> str:
    return re.sub(r'([_*()~`>#+=|{}.!-])', r'\\\1', text)

def save_already_sent(already_sent):
    with open("already_sent.json", "w", encoding="utf-8") as f:
        json.dump(list(already_sent), f)

def load_already_sent():
    if os.path.exists("already_sent.json"):
        with open("already_sent.json", "r", encoding="utf-8") as f:
            return set(json.load(f))
    return set()

def login():
    try:
        resp = session.get(LOGIN_PAGE_URL, timeout=10)
        match = re.search(r'What is (\d+) \+ (\d+)', resp.text)
        if not match:
            logging.error("Captcha not found")
            return False
        captcha_answer = int(match.group(1)) + int(match.group(2))

        payload = {
            "username": USERNAME,
            "password": PASSWORD,
            "capt": captcha_answer
        }
        resp = session.post(LOGIN_POST_URL, data=payload, timeout=10)

        if resp.ok and ("dashboard" in resp.text.lower() or "logout" in resp.text.lower()):
            logging.info("✅ Login success")
            return True
        else:
            logging.error("❌ Login failed")
            return False
    except Exception as e:
        logging.error(f"Login error: {e}")
        return False

def get_country_info(phone_number: str):
    try:
        number = "+" + phone_number.strip().lstrip("+")
        parsed = phonenumbers.parse(number, None)
        if not phonenumbers.is_valid_number(parsed):
            return "❓", "Invalid"
        region_code = phonenumbers.region_code_for_number(parsed)
        country = pycountry.countries.get(alpha_2=region_code)
        country_name = country.name if country else "Unknown"
        country_flag = ''.join(chr(127397 + ord(c)) for c in region_code)
        return country_flag, country_name
    except Exception:
        return "❓", "Unknown"

def build_api_url():
    start_date = time.strftime("%Y-%m-%d", time.localtime(time.time() - 30*86400))
    end_date = time.strftime("%Y-%m-%d")
    return (
        f"{DATA_URL}?fdate1={start_date}%2000:00:00&fdate2={end_date}%2023:59:59&"
        "frange=&fclient=&fnum=&fcli=&fgdate=&fgmonth=&fgrange=&fgclient=&fgnumber=&fgcli=&fg=0&"
        "sEcho=1&iColumns=9&sColumns=%2C%2C%2C%2C%2C%2C%2C%2C&iDisplayStart=0&iDisplayLength=25&"
        "mDataProp_0=0&sSearch_0=&bRegex_0=false&bSearchable_0=true&bSortable_0=true&"
        "mDataProp_1=1&sSearch_1=&bRegex_1=false&bSearchable_1=true&bSortable_1=true&"
        "mDataProp_2=2&sSearch_2=&bRegex_2=false&bSearchable_2=true&bSortable_2=true&"
        "mDataProp_3=3&sSearch_3=&bRegex_3=false&bSearchable_3=true&bSortable_3=true&"
        "mDataProp_4=4&sSearch_4=&bRegex_4=false&bSearchable_4=true&bSortable_4=true&"
        "mDataProp_5=5&sSearch_5=&bRegex_5=false&bSearchable_5=true&bSortable_5=true&"
        "mDataProp_6=6&sSearch_6=&bRegex_6=false&bSearchable_6=true&bSortable_6=true&"
        "mDataProp_7=7&sSearch_7=&bRegex_7=false&bSearchable_7=true&bSortable_7=true&"
        "mDataProp_8=8&sSearch_8=&bRegex_8=false&bSearchable_8=true&bSortable_8=false&"
        "sSearch=&bRegex=false&iSortCol_0=0&sSortDir_0=desc&iSortingCols=1"
    )

def fetch_data():
    url = build_api_url()
    try:
        resp = session.get(url, headers={"X-Requested-With": "XMLHttpRequest"}, timeout=10)
        if resp.status_code == 200:
            return resp.json()
        elif resp.status_code == 403 or "login" in resp.text.lower():
            logging.warning("Session expired. Re-login...")
            if login():
                return fetch_data()
            return None
        else:
            logging.error(f"Unexpected {resp.status_code}")
            return None
    except Exception as e:
        logging.error(f"Fetch error: {e}")
        return None

already_sent = load_already_sent()

async def sent_messages():
    data = fetch_data()
    if data and "aaData" in data:
        for row in data["aaData"]:
            date, number, service, message = str(row[0]).strip(), str(row[2]).strip(), str(row[3]).strip(), str(row[5]).strip()
            otp_match = re.search(r"\d{3}-\d{3}|\d{4,6}", message)
            otp = otp_match.group().replace("-", "") if otp_match else None

            if otp:
                unique_key = f"{number}|{otp}"
                if unique_key not in already_sent:
                    already_sent.add(unique_key)

                    country_flag, country_name = get_country_info(number)
                    current_time = time.strftime("%Y-%m-%d %H:%M:%S")

                    text = (
                        f"✨🔥 OTP ALERT\n\n"
                        f"⏰ Time: `{current_time}`\n"
                        f"📞 Number: `{escape_markdown(number)}`\n"
                        f"🔑 OTP: `{escape_markdown(otp)}`\n"
                        f"🌍 Country: {country_flag} {escape_markdown(country_name)}\n"
                        f"📱 Service: {escape_markdown(service)}\n"
                        f"💌 Message:\n```{escape_markdown(message)}```\n"
                    )

                    keyboard = InlineKeyboardMarkup([
                        [InlineKeyboardButton("🚀 CHANNEL 🚀", url="https://t.me/otpmkearningbd")]
                    ])

                    try:
                        await bot.send_message(chat_id=CHAT_ID, text=text, parse_mode="MarkdownV2", reply_markup=keyboard)
                        save_already_sent(already_sent)
                        logging.info(f"[+] Sent OTP {otp}")
                    except TimedOut:
                        logging.error("Telegram Timeout")
                    except Exception as e:
                        logging.error(f"Telegram error: {e}")

async def main():
    if login():
        while True:
            await sent_messages()
            await asyncio.sleep(POLL_INTERVAL)
    else:
        logging.error("Initial login failed.")

if __name__ == "__main__":
    asyncio.run(main())
