import os
import time
import requests
from bs4 import BeautifulSoup
from datetime import datetime

# 🔑 Railway / Local Environment Variables
BASE_URL = os.getenv("BASE_URL")           # যেমন: http://94.23.120.156/ints/agent
LOGIN_URL = f"{BASE_URL}/login"
DATA_URL = f"{BASE_URL}/res/data_smscdr.php"
USERNAME = os.getenv("USERNAME")
PASSWORD = os.getenv("PASSWORD")

TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
CHAT_ID = os.getenv("CHAT_ID")

SESSION = requests.Session()

def login():
    """Login to the portal"""
    try:
        resp = SESSION.post(LOGIN_URL, data={"username": USERNAME, "password": PASSWORD})
        if resp.status_code == 200 and "logout" in resp.text.lower():
            print("✅ Login success")
            return True
        else:
            print("❌ Login failed")
            return False
    except Exception as e:
        print("⚠️ Login error:", e)
        return False

def fetch_data():
    """Fetch OTP data from the site"""
    try:
        params = {
            "fdate1": datetime.now().strftime("%Y-%m-%d 00:00:00"),
            "fdate2": datetime.now().strftime("%Y-%m-%d 23:59:59"),
            "iDisplayStart": 0,
            "iDisplayLength": 5
        }
        resp = SESSION.get(DATA_URL, params=params)
        if resp.status_code == 200:
            return resp.json()
        else:
            print("⚠️ Data fetch failed:", resp.status_code)
            return None
    except Exception as e:
        print("⚠️ Fetch error:", e)
        return None

def send_otp_to_telegram(phone, country, service, otp):
    """Send OTP message to Telegram"""
    message = f"""
⚡️ OTP প্রাপ্তি সফল হয়েছে 🎉  

⏰ সময়: {datetime.now().strftime("%d/%m/%Y, %H:%M:%S")}
📱 নাম্বার: {phone}
🌍 দেশ: {country}
🔧 সার্ভিস: {service}

🔑 OTP কোড: {otp}
"""
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    payload = {"chat_id": CHAT_ID, "text": message}
    requests.post(url, data=payload)
    print("📤 OTP sent to Telegram")

def main():
    if not login():
        return

    print("🚀 OTP Forwarder started...")
    while True:
        data = fetch_data()
        if data and "aaData" in data:
            for row in data["aaData"]:
                phone = row[1]
                service = row[2]
                otp = row[3]  # ধরছি OTP এই কলামে থাকে
                country = row[4] if len(row) > 4 else "N/A"

                if otp and otp.isdigit():
                    send_otp_to_telegram(phone, country, service, otp)
        time.sleep(10)

if __name__ == "__main__":
    main()
