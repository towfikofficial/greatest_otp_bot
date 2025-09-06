import os
import telebot
import requests

# Environment variables (Railway → Variables এ বসাতে হবে)
BOT_TOKEN = os.getenv("BOT_TOKEN")
CHAT_ID = os.getenv("CHAT_ID")   # optional, যদি fixed group/channel এ পাঠাতে চান
API_KEY = os.getenv("API_KEY")   # Seven1Tel manager যে দিয়েছে
BASE_URL = os.getenv("BASE_URL") # যেমনঃ https://api.seven1tel.com/send

bot = telebot.TeleBot(BOT_TOKEN)

print("✅ Bot started and running on Railway...")

# Function to send SMS
def send_sms(number, message):
    try:
        response = requests.post(
            BASE_URL,
            headers={"Authorization": f"Bearer {API_KEY}"},
            json={
                "to": number,
                "message": message
            }
        )
        return response.json()
    except Exception as e:
        return {"error": str(e)}

# /start command
@bot.message_handler(commands=['start'])
def start(message):
    bot.send_message(message.chat.id, "🤖 Bot is running! Use /sms <number> <text>")

# /sms command → Example: /sms +8801712345678 Hello
@bot.message_handler(commands=['sms'])
def sms(message):
    try:
        parts = message.text.split(" ", 2)  # /sms number text
        if len(parts) < 3:
            bot.send_message(message.chat.id, "❌ Usage: /sms <number> <text>")
            return
        
        number, text = parts[1], parts[2]
        result = send_sms(number, text)
        
        bot.send_message(message.chat.id, f"📩 SMS Sent: {result}")
        print(f"SMS sent to {number}: {text}")
    except Exception as e:
        bot.send_message(message.chat.id, f"⚠ Error: {e}")

# Polling loop
bot.polling(none_stop=True)
