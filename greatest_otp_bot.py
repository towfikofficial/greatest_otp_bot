
# OTP command
@bot.message_handler(commands=['otp'])
def send_otp(message):
    otp = random.randint(100000, 999999)
    bot.send_message(message.chat.id, f"🔑 Your OTP is: {otp}")
    print(f"OTP sent to {message.chat.id}: {otp}")  # log in Railway

# Start command
@bot.message_handler(commands=['start'])
def start(message):
    bot.send_message(message.chat.id, "🤖 Bot is running successfully!")

# Handle text messages
@bot.message_handler(func=lambda message: True)
def echo_message(message):
    cleaned = clean_text(message.text)
    bot.send_message(message.chat.id, f"You said: {cleaned}")
    print(f"Message from {message.chat.id}: {cleaned}")  # log in Railway

# Polling loop
bot.polling(none_stop=True)
