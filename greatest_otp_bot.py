import os
import time
import requests
import logging
import json
import re
import asyncio
import phonenumbers
import pycountry
from telegram import Bot, InlineKeyboardMarkup, InlineKeyboardButton
from telegram.error import TimedOut

# === Load Railway Environment Variables ===
BOT_TOKEN = os.getenv("BOT_TOKEN")
CHAT_ID = os.getenv("CHAT_ID")
USERNAME = os.getenv("USERNAME")
PASSWORD = os.getenv("PASSWORD")
BASE_URL = os.getenv("BASE_URL")

LOGIN_PAGE_URL = BASE_URL + "/ints/login"
LOGIN_POST_URL = BASE_URL + "/ints/signin"
DATA_URL = BASE_URL + "/ints/agent/res/data_smscdr.php"

# === Logging setup ===
logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")

bot = Bot(token=BOT_TOKEN)
session = requests.Session()
session.headers.update({"User-Agent": "Mozilla/5.0"})

def escape_markdown(text: str) -> str:
return re.sub(r'([_*()~`>#+=|{}.!-])', r'\\\1', text)

def save_already_sent(already_sent):
with open("already_sent.json", "w", encoding="utf-8") as f:
json.dump(list(already_sent), f)

def load_already_sent():
try:
with open("already_sent.json", "r", encoding="utf-8") as f:
return set(json.load(f))
except FileNotFoundError:
return set()

def login():
try:
resp = session.get(LOGIN_PAGE_URL, timeout=10)
match = re.search(r'What is (\\d+) \\+ (\\d+)', resp.text)
if not match:
logging.error("❌ Captcha not found on login page")
return False
num1, num2 = int(match.group(1)), int(match.group(2))
captcha_answer = num1 + num2
logging.info(f"Solved captcha: {captcha_answer}")

payload = {"username": USERNAME, "password": PASSWORD, "capt": captcha_answer}
headers = {"Content-Type": "application/x-www-form-urlencoded", "Referer": LOGIN_PAGE_URL}

resp = session.post(LOGIN_POST_URL, data=payload, headers=headers, timeout=10)
if resp.ok and ("dashboard" in resp.text.lower() or "logout" in resp.text.lower()):
logging.info("✅ Login successful")
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
flag = ''.join(chr(127397 + ord(c)) for c in region_code)
return flag, country.name if country else "Unknown"
except Exception:
return "❓", "Unknown"

def build_api_url():
start_date = time.strftime("%Y-%m-%d", time.localtime(time.time() - 30*86400))
end_date = time.strftime("%Y-%m-%d")
return (
f"{DATA_URL}?fdate1={start_date}%2000:00:00&fdate2={end_date}%2023:59:59&"
"sEcho=1&iColumns=9&iDisplayStart=0&iDisplayLength=25&"
"iSortCol_0=0&sSortDir_0=desc&iSortingCols=1"
)

def fetch_data():
try:
response = session.get(build_api_url(), headers={"X-Requested-With": "XMLHttpRequest"}, timeout=10)
if response.status_code == 200:
return response.json()
elif response.status_code == 403 or "login" in response.text.lower():
logging.warning("⚠️ Session expired. Re-login...")
if login():
return fetch_data()
else:
logging.error(f"Unexpected error {response.status_code}")
return None
except Exception as e:
logging.error(f"Fetch error: {e}")
return None

already_sent = load_already_sent()

async def send_messages():
data = fetch_data()
if data and 'aaData' in data:
for row in data['aaData']:
number = str(row[2]).strip()
service = str(row[3]).strip()
message = str(row[5]).strip()
message = re.sub(r'[^\x00-\x7F]+', ' ', message)

otp_match = re.search(r'\\d{3}-\\d{3}|\\d{4,6}', message)
otp = otp_match.group().replace('-', '') if otp_match else None

if otp:
key = f"{number}|{otp}"
if key not in already_sent:
already_sent.add(key)
flag, country = get_country_info(number)
now = time.strftime("%Y-%m-%d %H:%M:%S")

text = (
f"🔥 OTP ALERT 🔥\n\n"
f"⏰ Time: `{now}`\n"
f"📞 Number: `{escape_markdown(number)}`\n"
f"🔑 OTP: `{escape_markdown(otp)}`\n"
f"🌍 Country: {flag} {escape_markdown(country)}\n"
f"📱 Service: {escape_markdown(service)}\n"
f"💬 Message: \n```{escape_markdown(message)}```"
)

keyboard = InlineKeyboardMarkup([
[InlineKeyboardButton("Telegram", url="https://t.me/otpmkearningbd")]
])

try:
await bot.send_message(chat_id=CHAT_ID, text=text, parse_mode="MarkdownV2", reply_markup=keyboard)
save_already_sent(already_sent)
logging.info(f"Sent OTP {otp}")
except TimedOut:
logging.warning("Telegram timed out")
except Exception as e:
logging.error(f"Telegram error: {e}")
else:
logging.info("No data received")

async def main():
if login():
logging.info("Bot started 🚀")
while True:
await send_messages()
await asyncio.sleep(3)
else:
logging.error("Login failed. Exiting...")

if __name__ == "__main__":
asyncio.run(main())
