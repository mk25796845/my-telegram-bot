import telebot
from telebot import types

# آپ کا اصلی ٹوکن جو آپ کی تصویر میں موجود ہے
TOKEN = "9082925617:AAGc5BUJE8hYNaCyZ7UMfSoP2j8x2mY2aYk"

bot = telebot.TeleBot(TOKEN)


# جب کوئی صارف /start کہے گا تو خوبصورت بٹنز کے ساتھ جواب ملے گا
@bot.message_handler(commands=["start"])
def send_welcome(message):
  markup = types.InlineKeyboardMarkup(row_width=2)

  btn1 = types.InlineKeyboardButton(
      "🌐 Visit Website", url="https://google.com"
  )
  btn2 = types.InlineKeyboardButton(
      "📞 Contact Support", url="https://t.me/myhelper3620bot"
  )
  btn3 = types.InlineKeyboardButton(
      "ℹ️ About Bot", callback_data="about_us"
  )

  markup.add(btn1, btn2, btn3)

  bot.reply_to(
      message,
      "Hello! Welcome to my professional automated bot. Please select an"
      " option below:",
      reply_markup=markup,
  )


# جب کوئی 'About Bot' والے بٹن پر کلک کرے گا
@bot.callback_query_handler(func=lambda call: True)
def callback_query(call):
  if call.data == "about_us":
    bot.answer_callback_query(
        call.id,
        "This is a premium automated assistant created with Python!",
        show_alert=True,
    )


# جب کوئی عام تحریر بھیجے گا
@bot.message_handler(func=lambda message: True)
def echo_all(message):
  bot.reply_to(
      message,
      f"I have received your message: '{message.text}'. Our team will get back"
      " to you soon!",
  )


print("Bot is successfully running and online...")
bot.infinity_polling()
