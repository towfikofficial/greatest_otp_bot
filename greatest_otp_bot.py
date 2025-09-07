import requests
from bs4 import BeautifulSoup
import time
import logging

# Logging setup
logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")

BASE_URL = "http://94.23.120.156/ints"
LOGIN_URL = BASE_URL + "/login"
DATA_URL = BASE_URL + "/agent/res/data_smscdr.php"

USERNAME = "your_username"
PASSWORD = "your_password"

# Browser-like headers
headers = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/117.0 Safari/537.36",
    "Referer": DATA_URL,
}

def login_and_fetch():
    with requests.Session() as session:
        logging.info("🔑 Trying to login...")

        # Step 1: Open login page (to get cookies + captcha if needed)
        resp = session.get(LOGIN_URL, headers=headers)
        if resp.status_code != 200:
            logging.error(f"❌ Login page load failed: {resp.status_code}")
            return

        # Step 2: Submit login form
        payload = {
            "username": USERNAME,
            "password": PASSWORD,
        }
        resp = session.post(LOGIN_URL, data=payload, headers=headers)

        if resp.status_code == 200 and "Dashboard" in resp.text:
            logging.info("✅ Login success")
        else:
            logging.error("❌ Login failed")
            return

        # Step 3: Fetch data
        logging.info("📥 Fetching data...")
        resp = session.get(DATA_URL, headers=headers)

        if resp.status_code == 200:
            if "Direct Script Access Not Allowed" in resp.text:
                logging.warning("⚠️ Server blocked script access (need cookies/headers fix).")
            else:
                logging.info("✅ Data fetched successfully")
                print(resp.text[:500])  # just preview
        else:
            logging.error(f"❌ Data fetch failed: {resp.status_code}")

if __name__ == "__main__":
    while True:
        login_and_fetch()
        time.sleep(60)  # wait 1 minute before next fetch
