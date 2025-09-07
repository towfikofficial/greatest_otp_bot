import requests
import time
import datetime
import logging
import re
from bs4 import BeautifulSoup

# ------------------------
# CONFIG
# ------------------------
BASE_URL = "http://94.23.120.156/ints"
LOGIN_URL = BASE_URL + "/login"
DATA_URL = BASE_URL + "/agent/res/data_smscdr.php"

USERNAME = "your_username"
PASSWORD = "your_password"

BOT_TOKEN = "your_telegram_bot_token"
CHAT_ID = "your_chat_id"

POLL_INTERVAL = 10   # কত সেকেন্ড পর পর নতুন ডাটা আনবে

# ------------------------
# LOGGING
# ------------------------
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s"
)

# ------------------------
# TELEGRAM FUNCTION
# ------------------------
def send_telegram(text):
    url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"
    payload = {"chat_id": CHAT_ID, "text": text}
    try:
        r = requests.post(url, data=payload, timeout=10)
        if r.status_code == 200:
            logging.info("📤 Sent to Telegram")
        else:
            logging.warning(f"⚠️ Telegram send failed: {r.text}")
    except Exception as e:
        logging.error(f"❌ Telegram error: {e}")

# ------------------------
# OTP EXTRACT FUNCTION
# ------------------------
def extract_otp(message):
    if not message:
        return None
    m = re.search(r"(\d{4,8})", message)
    return m.group(1) if m else None

# ------------------------
# LOGIN FUNCTION
# ------------------------
def login(session):
    logging.info("🔑 Trying to login...")

    resp = session.get(LOGIN_URL)
    if resp.status_code != 200:
        logging.error(f"❌ Login page load failed: {resp.status_code}")
        return False

    # --- Captcha Solve Logic ---
    soup = BeautifulSoup(resp.text, "html.parser")
    # এখানে captcha logic বসাও (এখন static ধরা হচ্ছে)
    captcha = "12"

    payload = {
        "username": USERNAME,
        "password": PASSWORD,
        "captcha": captcha
    }

    r = session.post(LOGIN_URL, data=payload)
    if r.status_code == 200 and ("Dashboard" in r.text or "Logout" in r.text):
        logging.info("✅ Login success")
        return True
    else:
        logging.error(f"❌ Login failed: {r.status_code}")
        return False

# ------------------------
# FETCH DATA FUNCTION
# ------------------------
def fetch_data(session):
    today = datetime.date.today()
    fdate1 = today.strftime("%Y-%m-%d 00:00:00")
    fdate2 = today.strftime("%Y-%m-%d 23:59:59")

    params = {
        "fdate1": fdate1,
        "fdate2": fdate2,
        "sEcho": 1,
        "iColumns": 9,
        "iDisplayStart": 0,
        "iDisplayLength": 25,
    }

    for attempt in range(5):  # retry max 5 times
        r = session.get(DATA_URL, params=params)
        if r.status_code == 200:
            try:
                return r.json()
            except Exception as e:
                logging.error(f"❌ JSON parse error: {e}")
                return None
        else:
            logging.warning(f"⚠️ Data fetch failed (status {r.status_code}), retry {attempt+1}/5")
            time.sleep(3)

    logging.error("❌ Data fetch failed after retries")
    return None

# ------------------------
# MAIN LOOP
# ------------------------
def main():
    session = requests.Session()

    if not login(session):
        return

    already_sent = set()

    while True:
        data = fetch_data(session)
        if data and "aaData" in data:
            for row in data["aaData"]:
                try:
                    date = row[0]
                    number = row[2]
                    service = row[3]
                    message = row[5]

                    otp = extract_otp(message)
                    key = f"{number}|{otp}"

                    if otp and key not in already_sent:
                        text = f"🔑 OTP: {otp}\n📞 From: {number}\n💬 {message}"
                        send_telegram(text)
                        already_sent.add(key)
                        logging.info(f"✅ Forwarded OTP {otp} from {number}")
                except Exception as e:
                    logging.error(f"Parse error: {e}")

        time.sleep(POLL_INTERVAL)

if __name__ == "__main__":
    main()
