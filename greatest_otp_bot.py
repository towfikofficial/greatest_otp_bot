import os
import logging
import random
import time
from telegram import Update
from telegram.ext import ApplicationBuilder, CommandHandler, ContextTypes, MessageHandler, filters

# Logging setup
logging.basicConfig(
format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
level=logging.INFO
)
logger = logging.getLogger(__name__)

# Generate OTP
def generate_otp():
return random.randint(100000, 999999)

# /start command
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
user_first_name = update.effective_user.first_name if update.effective_user else "User"
welcome_message = f"Welcome {user_first_name}! Use /otp to get a new OTP code."
await update.message.reply_text(welcome_message)

# /otp command
async def otp_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
try:
otp = generate_otp()
await update.message.reply_text(f"Your new OTP code is: {otp}")
logger.info(f"OTP generated: {otp} for user {update.effective_user.id}")
except Exception as e:
logger.error(f"Error sending OTP: {e}", exc_info=True)
await update.message.reply_text("Error generating OTP.")

# /help command
async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
help_text = "Available commands:\n"
help_text += "/start - Start the bot\n"
help_text += "/otp - Generate a new OTP\n"
help_text += "/help - Show help message"
await update.message.reply_text(help_text)

# Handle text messages
async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
text = update.message.text.strip().lower()
if text == "otp":
otp = generate_otp()
await update.message.reply_text(f"Your OTP is: {otp}")
logger.info(f"OTP generated: {otp} for user {update.effective_user.id}")
else:
await update.message.reply_text("I didn't understand that. Type /help for options.")

# Error handler
async def error_handler(update: object, context: ContextTypes.DEFAULT_TYPE):
logger.error(f"Update caused error: {context.error}", exc_info=True)

def main():
TOKEN = os.getenv("BOT_TOKEN")
if not TOKEN:
logger.error("BOT_TOKEN not found in environment variables!")
return

application = ApplicationBuilder().token(TOKEN).build()

application.add_handler(CommandHandler("start", start))
application.add_handler(CommandHandler("otp", otp_command))
application.add_handler(CommandHandler("help", help_command))
application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
application.add_error_handler(error_handler)

logger.info("Bot started. Waiting for updates...")

while True:
try:
application.run_polling()
except Exception as e:
logger.error(f"Bot crashed: {e}", exc_info=True)
time.sleep(5)
logger.info("Restarting bot...")

if __name__ == "__main__":
main()
