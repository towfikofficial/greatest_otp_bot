import requests
from bs4 import BeautifulSoup
import time
import logging

# -----------------------------
# CONFIG
# -----------------------------
LOGIN_PAGE_URL = "http://94.23.120.156/ints/login"
DATA_URL_BASE = "http://94.23.120.156/ints/agent/res/data_smscdr.php"
USERNAME = "your_username"
PASSWORD = "your_password"

POLL_INTERVAL = 10  # seconds

# -----------------------------
# LOGGER SETUP
# -----------------------------
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s"
)

# -----------------------------
# HEADERS (to bypass 403)
# -----------------------------
HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                  "AppleWebKit/537.36 (KHTML, like Gecko) "
                  "Chrome/116.0 Safari/537.36",
    "Accept": "text/html,application/xhtml+xml,application/xml;"
              "q=0.9,image/webp,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.9",
    "Referer": LOGIN_PAGE_URL,
    "Connection": "keep-alive"
}

# -----------------------------
# SESSION
# -----------------------------
session = requests.Session()


def login():
    """Perform login to the site"""
    try:
        logging.info("🔑 Trying to login...")

        # Load login page
        resp = session.get(LOGIN_PAGE_URL, headers=HEADERS, timeout=15)

        if resp.status_code != 200:
            logging.error(f"❌ Login page load failed: {resp.status_code}")
            return False

        # Parse login form (example, update if needed)
        soup = BeautifulSoup(resp.text, "html.parser")
        form = soup.find("form")
        if not form:
            logging.error("❌ Login form not found")
            return False

        # Build payload
        payload = {
            "username": USERNAME,
            "password": PASSWORD
        }

        # Submit login form
        action_url = form.get("action")
        login_url = action_url if action_url.startswith("http") else LOGIN_PAGE_URL

        post_resp = session.post(login_url, data=payload, headers=HEADERS, timeout=15)

        if post_resp.status_code == 200:
            logging.info("✅ Login success")
            return True
        else:
            logging.error(f"❌ Login POST failed: {post_resp.status_code}")
            return False

    except Exception as e:
        logging.error(f"⚠️ Login error: {e}")
        return False


def fetch_data():
    """Fetch OTP data from the system"""
    try:
        params = {
            "fdate1": "2025-09-06 00:00:00",
            "fdate2": "2025-09-06 23:59:59",
            "sEcho": 1,
            "iColumns": 9,
            "iDisplayStart": 0,
            "iDisplayLength": 25
        }

        resp = session.get(DATA_URL_BASE, params=params, headers=HEADERS, timeout=15)

        if resp.status_code == 200:
            logging.info("📩 Data fetched successfully")
            logging.info(resp.text[:200])  # show preview
        else:
            logging.error(f"❌ Data fetch failed: {resp.status_code}")

    except Exception as e:
        logging.error(f"⚠️ Data fetch error: {e}")


if __name__ == "__main__":
    if login():
        while True:
            fetch_data()
            time.sleep(POLL_INTERVAL)
    else:
        logging.error("❌ Login failed. Stopping bot.")
