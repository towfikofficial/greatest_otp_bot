import os
import re
import requests
import phonenumbers
import pycountry
from telegram import Update
from telegram.ext import Application, CommandHandler, ContextTypes

# Load environment variables
BOT_TOKEN = os.getenv("BOT_TOKEN")
CHAT_ID = os.getenv("CHAT_ID")
USERNAME = os.getenv("USERNAME")
PASSWORD = os.getenv("PASSWORD")
BASE_URL = os.getenv("BASE_URL")


# Clean text helper
def clean_text(text: str) -> str:
return re.sub(r'[^a-zA-Z0-9@.+-_]', '', text)


# /start command
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
await update.message.reply_text("✅ Bot is running successfully on Railway!")


# /otp command
async def otp(update: Update, context: ContextTypes.DEFAULT_TYPE):
if not context.args:
await update.message.reply_text("❌ Please provide a phone number.\n\nExample: /otp +8801XXXXXXXXX")
return

raw_number = context.args[0]
try:
phone_number = phonenumbers.parse(raw_number, None)
country = pycountry.countries.get(alpha_2=phonenumbers.region_code_for_number(phone_number))
country_name = country.name if country else "Unknown"

# Send request to your API
payload = {"username": USERNAME, "password": PASSWORD, "phone": raw_number}
response = requests.post(BASE_URL, data=payload)

if response.status_code == 200:
await update.message.reply_text(
f"✅ OTP sent successfully to {raw_number} ({country_name})"
)
else:
await update.message.reply_text(
f"⚠️ Failed to send OTP.\nStatus: {response.status_code}\nResponse: {response.text}"
)

except Exception as e:
await update.message.reply_text(f"❌ Error: {str(e)}")


def main():
app = Application.builder().token(BOT_TOKEN).build()

app.add_handler(CommandHandler("start", start))
app.add_handler(CommandHandler("otp", otp))

print("🚀 Bot is running...")
app.run_polling()


if __name__ == "__main__":
main()
