import telebot
from telebot import types
import sqlite3
import time

# ==========================================
# 1. فائنل سیٹنگز (آپ کا ٹوکن اور ایڈمن آئی ڈی درج ہے)
# ==========================================
API_TOKEN = '9082925617:AAGc5BUJE8hYNaCyZ7UMfSoP2j8x2mY2ayK'  # آپ کا بوٹ ٹوکن[span_3](start_span)[span_3](end_span)
ADMIN_ID = 7499911678                                     # آپ کی اصلی ٹیلیگرام آئی ڈی[span_4](start_span)[span_4](end_span)

# کاروباری اور پریمیم برانڈنگ
BUSINESS_NAME = "پریمیم آٹومیشن سروسز"
CHANNEL_USERNAME = "@YourChannelUsername" # اگر چینل جوائن کروانا ہو تو یہاں یوزر نیم لکھیں
FORCE_SUB_ENABLED = False                  # اگر زبردستی چینل جوائن کروانا ہو تو اسے True کر دیں

bot = telebot.TeleBot(API_TOKEN)

# ==========================================
# 2. ڈیٹا بیس سیٹ اپ (خودکار ریکارڈ کے لیے)
# ==========================================
def init_db():
    conn = sqlite3.connect('bot_database.db', check_same_thread=False)
    cursor = conn.cursor()
    cursor.execute('''CREATE TABLE IF NOT EXISTS users (
                        user_id INTEGER PRIMARY KEY,
                        first_name TEXT,
                        username TEXT,
                        joined_date TEXT
                    )''')
    cursor.execute('''CREATE TABLE IF NOT EXISTS orders (
                        order_id INTEGER PRIMARY KEY AUTOINCREMENT,
                        user_id INTEGER,
                        details TEXT,
                        status TEXT
                    )''')
    conn.commit()
    return conn, cursor

conn, cursor = init_db()

user_states = {}
admin_states = {}
MAINTENANCE_MODE = False

def register_user(user):
    cursor.execute("SELECT user_id FROM users WHERE user_id = ?", (user.id,))
    if cursor.fetchone() is None:
        date_str = time.strftime("%Y-%m-%d %H:%M:%S")
        cursor.execute("INSERT INTO users (user_id, first_name, username, joined_date) VALUES (?, ?, ?, ?)",
                       (user.id, user.first_name, user.username, date_str))
        conn.commit()

def check_subscription(user_id):
    if not FORCE_SUB_ENABLED:
        return True
    try:
        member = bot.get_chat_member(CHANNEL_USERNAME, user_id)
        return member.status in ['member', 'administrator', 'creator']
    except Exception:
        return True

# ==========================================
# 3. مینیو اور کی بورڈز
# ==========================================
def main_menu_keyboard():
    markup = types.InlineKeyboardMarkup(row_width=2)
    btn1 = types.InlineKeyboardButton("🛍️ ہماری سروسز", callback_data="services")
    btn2 = types.InlineKeyboardButton("📝 آرڈر / بکنگ کریں", callback_data="new_order")
    btn3 = types.InlineKeyboardButton("❓ اکثر پوچھے گئے سوالات", callback_data="faq")
    btn4 = types.InlineKeyboardButton("📞 کسٹمر سپورٹ", callback_data="support")
    markup.add(btn1, btn2, btn3, btn4)
    return markup

def admin_menu_keyboard():
    markup = types.InlineKeyboardMarkup(row_width=2)
    status_text = "🟢 بوٹ آن ہے" if not MAINTENANCE_MODE else "🔴 مینٹیننس موڈ"
    btn1 = types.InlineKeyboardButton("📊 لائیو اعداد و شمار", callback_data="admin_stats")
    btn2 = types.InlineKeyboardButton("📢 سب کو پیغام بھیجیں", callback_data="admin_broadcast")
    btn3 = types.InlineKeyboardButton(status_text, callback_data="admin_toggle_maint")
    btn4 = types.InlineKeyboardButton("📋 حالیہ آرڈرز دیکھیں", callback_data="admin_orders")
    markup.add(btn1, btn2, btn3, btn4)
    return markup

# ==========================================
# 4. بوٹ کی کمانڈز (/start اور /admin)
# ==========================================
@bot.message_handler(commands=['start'])
def send_welcome(message):
    user = message.from_user
    register_user(user)
    
    if MAINTENANCE_MODE and user.id != ADMIN_ID:
        bot.send_message(message.chat.id, "⚠️ معذرت! اس وقت سسٹم اپ ڈیٹ ہو رہا ہے۔ براہ کرم تھوڑی دیر بعد کوشش کریں۔")
        return

    if not check_subscription(user.id):
        markup = types.InlineKeyboardMarkup()
        markup.add(types.InlineKeyboardButton("📢 چینل جوائن کریں", url=f"https://t.me/{CHANNEL_USERNAME.replace('@', '')}"))
        markup.add(types.InlineKeyboardButton("✅ جوائن کر لیا ہے", callback_data="check_sub"))
        bot.send_message(message.chat.id, f"خوش آمدید {user.first_name}! بوٹ استعمال کرنے کے لیے پہلے ہمارا چینل جوائن کریں:", reply_markup=markup)
        return

    welcome_text = (
        f"السلام علیکم *{user.first_name}*! 🌟\n\n"
        f"*{BUSINESS_NAME}* کے آفیشل آٹومیشن سسٹم میں خوش آمدید۔\n"
        "نیچے دیے گئے بٹنز میں سے اپنی ضرورت کا انتخاب کریں:"
    )
    bot.send_message(message.chat.id, welcome_text, parse_mode="Markdown", reply_markup=main_menu_keyboard())

@bot.message_handler(commands=['admin'])
def open_admin_panel(message):
    if message.from_user.id == ADMIN_ID:
        bot.send_message(message.chat.id, "🔐 *پریمیم ایڈمن کنٹرول پینل*\nیہاں سے آپ پورے بوٹ کو کنٹرول کر سکتے ہیں:", parse_mode="Markdown", reply_markup=admin_menu_keyboard())
    else:
        bot.send_message(message.chat.id, "⛔ معذرت، یہ کمانڈ صرف ایڈمن کے لیے ہے۔")

# ==========================================
# 5. بٹنز (Callbacks) کی ہینڈلنگ
# ==========================================
@bot.callback_query_handler(func=lambda call: True)
def handle_callbacks(call):
    global MAINTENANCE_MODE
    chat_id = call.message.chat.id
    user_id = call.from_user.id

    if call.data == "check_sub":
        if check_subscription(user_id):
            bot.delete_message(chat_id, call.message.message_id)
            bot.send_message(chat_id, "✅ تصدیق مکمل! اب آپ بوٹ استعمال کر سکتے ہیں:", reply_markup=main_menu_keyboard())
        else:
            bot.answer_callback_query(call.id, "❌ آپ نے ابھی تک چینل جوائن نہیں کیا!", show_alert=True)

    elif call.data == "back_main":
        bot.edit_message_text("مین مینیو میں خوش آمدید 👇", chat_id, call.message.message_id, reply_markup=main_menu_keyboard())

    elif call.data == "services":
        text = (
            "🛍️ *ہماری دستیاب سروسز اور پیکجز:*\n\n"
            "1️⃣ **بیسک پیکج:** مکمل معلومات اور آٹومیشن\n"
            "2️⃣ **پریمیم پیکج:** 24/7 وی آئی پی سپورٹ\n"
            "3️⃣ **کسٹم سروس:** آپ کی مرضی کے مطابق حل\n\n"
            "آرڈر بک کرنے کے لیے نیچے 'آرڈر کریں' پر کلک کریں۔"
        )
        markup = types.InlineKeyboardMarkup()
        markup.add(types.InlineKeyboardButton("📝 ابھی آرڈر کریں", callback_data="new_order"))
        markup.add(types.InlineKeyboardButton("🔙 واپس مین مینیو", callback_data="back_main"))
        bot.edit_message_text(text, chat_id, call.message.message_id, parse_mode="Markdown", reply_markup=markup)

    elif call.data == "faq":
        text = (
            "❓ *اکثر پوچھے گئے سوالات (FAQs):*\n\n"
            "🔸 **سوال:** آرڈر کتنے وقت میں مکمل ہوتا ہے؟\n"
            "🔹 **جواب:** آرڈر کنفرم ہونے کے فوراً بعد کام شروع کر دیا جاتا ہے۔\n\n"
            "🔸 **سوال:** ادائیگی کا طریقہ کیا ہے؟\n"
            "🔹 **جواب:** ایزی پیسہ، جاز کیش اور بینک ٹرانسفر دستیاب ہیں۔"
        )
        markup = types.InlineKeyboardMarkup()
        markup.add(types.InlineKeyboardButton("🔙 واپس مین مینیو", callback_data="back_main"))
        bot.edit_message_text(text, chat_id, call.message.message_id, parse_mode="Markdown", reply_markup=markup)

    elif call.data == "support":
        text = "📞 *کسٹمر سپورٹ:*\nکسی بھی سوال یا مدد کے لیے براہ راست اپنا پیغام یہاں لکھ کر भेज دیں، ہماری ٹیم جلد رابطہ کرے گی۔"
        user_states[user_id] = "awaiting_support"
        markup = types.InlineKeyboardMarkup()
        markup.add(types.InlineKeyboardButton("❌ منسوخ کریں", callback_data="cancel_action"))
        bot.edit_message_text(text, chat_id, call.message.message_id, parse_mode="Markdown", reply_markup=markup)

    elif call.data == "new_order":
        text = "📝 *نیا آرڈر / بکنگ:*\nبراہ کرم اپنا **نام، فون نمبر اور مطلوبہ سروس کی تفصیل** ایک ہی میسج میں لکھ کر بھیجیں:"
        user_states[user_id] = "awaiting_order"
        markup = types.InlineKeyboardMarkup()
        markup.add(types.InlineKeyboardButton("❌ منسوخ کریں", callback_data="cancel_action"))
        bot.edit_message_text(text, chat_id, call.message.message_id, parse_mode="Markdown", reply_markup=markup)

    elif call.data == "cancel_action":
        user_states.pop(user_id, None)
        admin_states.pop(user_id, None)
        bot.edit_message_text("عمل منسوخ کر دیا گیا۔ مین مینیو:", chat_id, call.message.message_id, reply_markup=main_menu_keyboard())

    # --- ایڈمن کنٹرولز ---
    elif call.data == "admin_stats" and user_id == ADMIN_ID:
        cursor.execute("SELECT COUNT(*) FROM users")
        total_users = cursor.fetchone()[0]
        cursor.execute("SELECT COUNT(*) FROM orders")
        total_orders = cursor.fetchone()[0]
        stats_text = (
            "📊 *بوٹ کی لائیو کارکردگی:*\n\n"
            f"👥 کل صارفین: `{total_users}`\n"
            f"📦 کل موصول شدہ آرڈرز: `{total_orders}`\n"
            f"⚙️ سسٹم اسٹیٹس: `{'مینٹیننس' if MAINTENANCE_MODE else 'آن لائن'}`"
        )
        bot.answer_callback_query(call.id)
        bot.send_message(chat_id, stats_text, parse_mode="Markdown")

    elif call.data == "admin_broadcast" and user_id == ADMIN_ID:
        admin_states[user_id] = "awaiting_broadcast"
        bot.send_message(chat_id, "📢 وہ پیغام (یا تصویر/لنک) لکھ کر بھیجیں جو آپ تمام صارفین کو ایک ساتھ بھیجنا چاہتے ہیں:")

    elif call.data == "admin_toggle_maint" and user_id == ADMIN_ID:
        MAINTENANCE_MODE = not MAINTENANCE_MODE
        bot.edit_message_reply_markup(chat_id, call.message.message_id, reply_markup=admin_menu_keyboard())
        bot.answer_callback_query(call.id, "اسٹیٹس تبدیل کر دیا گیا!")

    elif call.data == "admin_orders" and user_id == ADMIN_ID:
        cursor.execute("SELECT order_id, user_id, details FROM orders ORDER BY order_id DESC LIMIT 5")
        rows = cursor.fetchall()
        if not rows:
            bot.send_message(chat_id, "ابھی تک کوئی آرڈر موصول نہیں ہوا۔")
        else:
            msg = "📋 *آخری 5 آرڈرز کی تفصیل:*\n\n"
            for r in rows:
                msg += f"🔹 **آرڈر #{r[0]}** (ID: `{r[1]}`):\n{r[2]}\n\n"
            bot.send_message(chat_id, msg, parse_mode="Markdown")

# ==========================================
# 6. میسجز کی پروسیسنگ (آرڈرز اور براڈکاسٹ)
# ==========================================
@bot.message_handler(func=lambda message: True, content_types=['text'])
def handle_all_messages(message):
    user_id = message.from_user.id
    text = message.text

    if user_id == ADMIN_ID and admin_states.get(user_id) == "awaiting_broadcast":
        admin_states.pop(user_id, None)
        cursor.execute("SELECT user_id FROM users")
        all_users = cursor.fetchall()
        sent_count = 0
        bot.send_message(user_id, "⏳ پیغام بھیجا جا رہا ہے، براہ کرم انتظار کریں...")
        for u in all_users:
            try:
                bot.send_message(u[0], f"📢 *اہم اعلان:*\n\n{text}", parse_mode="Markdown")
                sent_count += 1
                time.sleep(0.05)
            except Exception:
                pass
        bot.send_message(user_id, f"✅ پیغام کامیابی سے `{sent_count}` صارفین کو بھیج دیا گیا!", parse_mode="Markdown")
        return

    if user_states.get(user_id) == "awaiting_order":
        user_states.pop(user_id, None)
        cursor.execute("INSERT INTO orders (user_id, details, status) VALUES (?, ?, ?)", (user_id, text, "Pending"))
        conn.commit()
        
        bot.send_message(user_id, "✅ آپ کا آرڈر کامیابی سے درج کر لیا گیا ہے! ہماری ٹیم جلد آپ سے رابطہ کرے گی۔", reply_markup=main_menu_keyboard())
        
        admin_alert = (
            f"🔔 *نیا آرڈر موصول ہوا ہے!*\n\n"
            f"👤 صارف: {message.from_user.first_name} (@{message.from_user.username})\n"
            f"🆔 آئی ڈی: `{user_id}`\n"
            f"📝 تفصیل:\n{text}"
        )
        bot.send_message(ADMIN_ID, admin_alert, parse_mode="Markdown")
        return

    if user_states.get(user_id) == "awaiting_support":
        user_states.pop(user_id, None)
        bot.send_message(user_id, "✅ آپ کا پیغام سپورٹ ٹیم کو بھیج دیا گیا ہے۔", reply_markup=main_menu_keyboard())
        bot.send_message(ADMIN_ID, f"📩 *نیا سپورٹ میسج:*\nصارف: {message.from_user.first_name} (`{user_id}`)\nپیغام: {text}", parse_mode="Markdown")
        return

    bot.send_message(message.chat.id, "براہ کرم نیچے دیے گئے مینیو بٹنز کا استعمال کریں 👇", reply_markup=main_menu_keyboard())

print("Premium Bot is running...")
bot.infinity_polling()
