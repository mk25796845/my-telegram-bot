import os
import sqlite3
import logging
import threading
import html
from datetime import datetime

import telebot
from telebot import types


# ==========================================
# CONFIGURATION
# ==========================================

BOT_TOKEN = '9082925617:AAHqHW1njLyOJBmRngmWagi9cGbve83d1LM'  # آپ کا تازہ ترین ٹوکن[span_0](start_span)[span_0](end_span)
ADMIN_ID = 7499911678                                     # آپ کی اصلی ایڈمن آئی ڈی[span_1](start_span)[span_1](end_span)
DB_NAME = "business_bot.db"

bot = telebot.TeleBot(BOT_TOKEN, parse_mode="HTML")

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s"
)

logger = logging.getLogger(__name__)

db_lock = threading.RLock()
state_lock = threading.RLock()

# Temporary conversation states
user_states = {}


# ==========================================
# DATABASE
# ==========================================

def get_db():
    conn = sqlite3.connect(
        DB_NAME,
        timeout=30,
        check_same_thread=False
    )
    conn.row_factory = sqlite3.Row
    return conn


def init_database():
    with db_lock:
        conn = get_db()

        conn.execute("PRAGMA journal_mode=WAL")

        conn.execute("""
            CREATE TABLE IF NOT EXISTS users (
                user_id INTEGER PRIMARY KEY,
                username TEXT,
                first_name TEXT,
                created_at TEXT
            )
        """)

        conn.execute("""
            CREATE TABLE IF NOT EXISTS orders (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                service TEXT NOT NULL,
                details TEXT,
                status TEXT DEFAULT 'Pending',
                created_at TEXT
            )
        """)

        conn.execute("""
            CREATE TABLE IF NOT EXISTS settings (
                key TEXT PRIMARY KEY,
                value TEXT
            )
        """)

        conn.execute("""
            INSERT OR IGNORE INTO settings (key, value)
            VALUES ('maintenance', '0')
        """)

        conn.commit()
        conn.close()

    logger.info("Database initialized successfully.")


def register_user(user):
    with db_lock:
        conn = get_db()

        conn.execute("""
            INSERT INTO users (
                user_id, username, first_name, created_at
            )
            VALUES (?, ?, ?, ?)

            ON CONFLICT(user_id) DO UPDATE SET
                username = excluded.username,
                first_name = excluded.first_name
        """, (
            user.id,
            user.username or "",
            user.first_name or "",
            datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        ))

        conn.commit()
        conn.close()


def save_order(user_id, service, details):
    with db_lock:
        conn = get_db()

        cursor = conn.execute("""
            INSERT INTO orders (
                user_id, service, details,
                status, created_at
            )
            VALUES (?, ?, ?, ?, ?)
        """, (
            user_id,
            service,
            details,
            "Pending",
            datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        ))

        order_id = cursor.lastrowid

        conn.commit()
        conn.close()

    return order_id


def get_maintenance():
    with db_lock:
        conn = get_db()

        row = conn.execute("""
            SELECT value FROM settings
            WHERE key = 'maintenance'
        """).fetchone()

        conn.close()

    return row["value"] == "1" if row else False


def set_maintenance(enabled):
    with db_lock:
        conn = get_db()

        conn.execute("""
            UPDATE settings
            SET value = ?
            WHERE key = 'maintenance'
        """, ("1" if enabled else "0",))

        conn.commit()
        conn.close()


# ==========================================
# KEYBOARDS
# ==========================================

def main_keyboard():
    markup = types.InlineKeyboardMarkup(row_width=2)

    markup.add(
        types.InlineKeyboardButton(
            "🛍 Our Services",
            callback_data="services"
        ),
        types.InlineKeyboardButton(
            "📦 Book an Order",
            callback_data="book"
        )
    )

    markup.add(
        types.InlineKeyboardButton(
            "❓ FAQs",
            callback_data="faqs"
        ),
        types.InlineKeyboardButton(
            "💬 Customer Support",
            callback_data="support"
        )
    )

    return markup


def admin_keyboard():
    markup = types.InlineKeyboardMarkup(row_width=2)

    markup.add(
        types.InlineKeyboardButton(
            "📊 Statistics",
            callback_data="admin:stats"
        ),
        types.InlineKeyboardButton(
            "📢 Broadcast",
            callback_data="admin:broadcast"
        )
    )

    markup.add(
        types.InlineKeyboardButton(
            "🛠 Maintenance",
            callback_data="admin:maintenance"
        ),
        types.InlineKeyboardButton(
            "📦 Recent Orders",
            callback_data="admin:orders"
        )
    )

    markup.add(
        types.InlineKeyboardButton(
            "🔄 Refresh Panel",
            callback_data="admin:home"
        )
    )

    return markup


# ==========================================
# ADMIN CHECK
# ==========================================

def is_admin(user_id):
    return user_id == ADMIN_ID


def show_admin_panel(chat_id):
    status = (
        "🔴 ON"
        if get_maintenance()
        else "🟢 OFF"
    )

    text = (
        "👑 <b>ADMIN CONTROL PANEL</b>\n\n"
        "━━━━━━━━━━━━━━━━━━\n"
        "⚙️ System Status: Active\n"
        f"🛠 Maintenance: {status}\n"
        "━━━━━━━━━━━━━━━━━━\n\n"
        "Select an option below:"
    )

    bot.send_message(
        chat_id,
        text,
        reply_markup=admin_keyboard()
    )


# ==========================================
# START COMMAND
# ==========================================

@bot.message_handler(commands=["start"])
def start_command(message):
    register_user(message.from_user)

    if get_maintenance() and not is_admin(message.from_user.id):
        bot.reply_to(
            message,
            "🛠 <b>We are currently under maintenance.</b>\n\n"
            "Please try again later."
        )
        return

    text = (
        "✨ <b>WELCOME TO OUR BUSINESS BOT</b>\n\n"
        "Your trusted business automation platform.\n\n"
        "━━━━━━━━━━━━━━━━━━\n"
        "🛍 Explore our services\n"
        "📦 Place your order\n"
        "❓ Get answers to your questions\n"
        "💬 Contact customer support\n"
        "━━━━━━━━━━━━━━━━━━\n\n"
        "Please select an option:"
    )

    bot.send_message(
        message.chat.id,
        text,
        reply_markup=main_keyboard()
    )


# ==========================================
# ADMIN COMMAND
# ==========================================

@bot.message_handler(commands=["admin"])
def admin_command(message):
    if not is_admin(message.from_user.id):
        bot.reply_to(message, "⛔ Access denied.")
        return

    show_admin_panel(message.chat.id)


@bot.message_handler(commands=["cancel"])
def cancel_command(message):
    with state_lock:
        user_states.pop(message.from_user.id, None)

    bot.reply_to(
        message,
        "❌ Operation cancelled.",
        reply_markup=main_keyboard()
    )


# ==========================================
# CALLBACK HANDLER
# ==========================================

@bot.callback_query_handler(func=lambda call: True)
def callback_handler(call):
    user_id = call.from_user.id
    register_user(call.from_user)

    data = call.data

    if get_maintenance() and not is_admin(user_id):
        bot.answer_callback_query(
            call.id,
            "System is under maintenance.",
            show_alert=True
        )
        return

    bot.answer_callback_query(call.id)

    # ADMIN CONTROLS
    if data.startswith("admin:"):

        if not is_admin(user_id):
            bot.send_message(call.message.chat.id, "⛔ Unauthorized.")
            return

        action = data.split(":", 1)[1]

        if action == "home":
            show_admin_panel(call.message.chat.id)

        elif action == "stats":
            with db_lock:
                conn = get_db()

                users = conn.execute(
                    "SELECT COUNT(*) FROM users"
                ).fetchone()[0]

                orders = conn.execute(
                    "SELECT COUNT(*) FROM orders"
                ).fetchone()[0]

                pending = conn.execute(
                    "SELECT COUNT(*) FROM orders WHERE status = 'Pending'"
                ).fetchone()[0]

                conn.close()

            text = (
                "📊 <b>LIVE BUSINESS STATISTICS</b>\n\n"
                f"👥 Total Users: <b>{users}</b>\n"
                f"📦 Total Orders: <b>{orders}</b>\n"
                f"⏳ Pending Orders: <b>{pending}</b>\n"
            )

            bot.send_message(
                call.message.chat.id,
                text,
                reply_markup=admin_keyboard()
            )

        elif action == "broadcast":
            with state_lock:
                user_states[user_id] = {
                    "step": "broadcast"
                }

            bot.send_message(
                call.message.chat.id,
                "📢 <b>BROADCAST SYSTEM</b>\n\n"
                "Send the message you want to deliver "
                "to all registered users.\n\n"
                "Use /cancel to cancel."
            )

        elif action == "maintenance":
            new_status = not get_maintenance()
            set_maintenance(new_status)

            status = "ENABLED 🔴" if new_status else "DISABLED 🟢"

            bot.send_message(
                call.message.chat.id,
                f"🛠 Maintenance mode is now <b>{status}</b>."
            )

            show_admin_panel(call.message.chat.id)

        elif action == "orders":
            with db_lock:
                conn = get_db()

                rows = conn.execute("""
                    SELECT id, user_id, service,
                           details, status, created_at
                    FROM orders
                    ORDER BY id DESC
                    LIMIT 10
                """).fetchall()

                conn.close()

            if not rows:
                bot.send_message(
                    call.message.chat.id,
                    "📦 No orders have been received yet."
                )
                return

            text = "📦 <b>RECENT ORDERS</b>\n\n"

            for order in rows:
                text += (
                    f"🆔 Order: <b>#{order['id']}</b>\n"
                    f"👤 User: <code>{order['user_id']}</code>\n"
                    f"🛍 Service: {html.escape(order['service'])}\n"
                    f"📝 Details: {html.escape(order['details'] or '')}\n"
                    f"📌 Status: {html.escape(order['status'])}\n"
                    f"🕒 {html.escape(order['created_at'])}\n"
                    "━━━━━━━━━━━━━━━━━━\n"
                )

            bot.send_message(
                call.message.chat.id,
                text,
                reply_markup=admin_keyboard()
            )

        return

    # USER MENU

    if data == "home":
        bot.send_message(
            call.message.chat.id,
            "🏠 <b>Main Menu</b>",
            reply_markup=main_keyboard()
        )

    elif data == "services":
        markup = types.InlineKeyboardMarkup()

        markup.add(
            types.InlineKeyboardButton(
                "🤖 AI Automation",
                callback_data="service:AI Automation"
            )
        )

        markup.add(
            types.InlineKeyboardButton(
                "🎨 Digital Services",
                callback_data="service:Digital Services"
            )
        )

        markup.add(
            types.InlineKeyboardButton(
                "💻 Custom Solutions",
                callback_data="service:Custom Solutions"
            )
        )

        markup.add(
            types.InlineKeyboardButton(
                "🔙 Back",
                callback_data="home"
            )
        )

        bot.send_message(
            call.message.chat.id,
            "🛍 <b>OUR SERVICES</b>\n\n"
            "Explore our available business services:",
            reply_markup=markup
        )

    elif data.startswith("service:"):
        service = data.split(":", 1)[1]

        markup = types.InlineKeyboardMarkup()

        markup.add(
            types.InlineKeyboardButton(
                "📦 Order This Service",
                callback_data="order:" + service
            )
        )

        bot.send_message(
            call.message.chat.id,
            f"✨ <b>{html.escape(service)}</b>\n\n"
            "Professional solutions tailored to your needs.\n\n"
            "Click below to book this service.",
            reply_markup=markup
        )

    elif data == "book":
        markup = types.InlineKeyboardMarkup(row_width=1)

        for service in [
            "AI Automation",
            "Digital Services",
            "Custom Solutions"
        ]:
            markup.add(
                types.InlineKeyboardButton(
                    "📦 " + service,
                    callback_data="order:" + service
                )
            )

        bot.send_message(
            call.message.chat.id,
            "📦 <b>SELECT A SERVICE TO ORDER</b>",
            reply_markup=markup
        )

    elif data.startswith("order:"):
        service = data.split(":", 1)[1]

        with state_lock:
            user_states[user_id] = {
                "step": "order",
                "service": service
            }

        bot.send_message(
            call.message.chat.id,
            f"📦 <b>New Order: {html.escape(service)}</b>\n\n"
            "Please send your order requirements and "
            "any important details in one message.\n\n"
            "Use /cancel to cancel."
        )

    elif data == "faqs":
        bot.send_message(
            call.message.chat.id,
            "❓ <b>FREQUENTLY ASKED QUESTIONS</b>\n\n"
            "1️⃣ How can I place an order?\n"
            "Select Book an Order and choose a service.\n\n"
            "2️⃣ How can I contact support?\n"
            "Use the Customer Support button.\n\n"
            "3️⃣ How do I know my order was received?\n"
            "The bot will send you an order confirmation.\n\n"
            "4️⃣ How can I check pricing?\n"
            "Contact our support team for a quotation.",
            reply_markup=main_keyboard()
        )

    elif data == "support":
        with state_lock:
            user_states[user_id] = {
                "step": "support"
            }

        bot.send_message(
            call.message.chat.id,
            "💬 <b>CUSTOMER SUPPORT</b>\n\n"
            "Please send your question or message.\n"
            "Our administrator will receive it.\n\n"
            "Use /cancel to cancel."
        )


# ==========================================
# MESSAGE HANDLER
# ==========================================

@bot.message_handler(content_types=[
    "text", "photo", "document",
    "video", "voice", "audio"
])
def message_handler(message):
    user = message.from_user
    user_id = user.id

    register_user(user)

    if message.text and message.text.startswith("/"):
        return

    if get_maintenance() and not is_admin(user_id):
        bot.reply_to(
            message,
            "🛠 We are currently under maintenance."
        )
        return

    with state_lock:
        state = user_states.get(user_id)

    if not state:
        if message.content_type == "text":
            bot.reply_to(
                message,
                "Please select an option from the main menu.",
                reply_markup=main_keyboard()
            )
        return

    step = state.get("step")

    # ORDER PROCESSING
    if step == "order":

        if message.content_type != "text":
            bot.reply_to(
                message,
                "Please send your order details as text."
            )
            return

        details = message.text.strip()

        if len(details) < 3:
            bot.reply_to(message, "Please provide more details.")
            return

        service = state["service"]

        order_id = save_order(
            user_id,
            service,
            details
        )

        with state_lock:
            user_states.pop(user_id, None)

        bot.reply_to(
            message,
            "✅ <b>ORDER RECEIVED SUCCESSFULLY!</b>\n\n"
            f"🆔 Order ID: <b>#{order_id}</b>\n"
            f"🛍 Service: {html.escape(service)}\n"
            "📌 Status: Pending\n\n"
            "Thank you for choosing our business!"
        )

        admin_text = (
            "🔔 <b>NEW ORDER RECEIVED</b>\n\n"
            f"🆔 Order: #{order_id}\n"
            f"👤 User: <code>{user_id}</code>\n"
            f"📛 Name: {html.escape(user.first_name or '')}\n"
            f"🛍 Service: {html.escape(service)}\n"
            f"📝 Details: {html.escape(details)}"
        )

        try:
            bot.send_message(ADMIN_ID, admin_text)
        except Exception:
            logger.exception("Could not notify admin about order.")

    # CUSTOMER SUPPORT
    elif step == "support":

        with state_lock:
            user_states.pop(user_id, None)

        support_caption = (
            "💬 <b>NEW CUSTOMER SUPPORT MESSAGE</b>\n\n"
            f"👤 Name: {html.escape(user.first_name or '')}\n"
            f"🆔 User ID: <code>{user_id}</code>\n"
            f"Username: @{html.escape(user.username or 'N/A')}"
        )

        try:
            bot.send_message(ADMIN_ID, support_caption)

            bot.copy_message(
                ADMIN_ID,
                message.chat.id,
                message.message_id
            )

            bot.reply_to(
                message,
                "✅ Your message has been delivered to our support team."
            )

        except Exception:
            logger.exception("Support message delivery failed.")

            bot.reply_to(
                message,
                "⚠️ Message delivery failed. Please try again later."
            )

    # ADMIN BROADCAST
    elif step == "broadcast" and is_admin(user_id):

        with state_lock:
            user_states.pop(user_id, None)

        with db_lock:
            conn = get_db()

            users = conn.execute(
                "SELECT user_id FROM users"
            ).fetchall()

            conn.close()

        bot.reply_to(
            message,
            f"📢 Starting broadcast to {len(users)} users..."
        )

        sent = 0
        failed = 0

        for row in users:
            target_id = row["user_id"]

            try:
                bot.copy_message(
                    target_id,
                    message.chat.id,
                    message.message_id
                )
                sent += 1

            except Exception:
                failed += 1
                logger.warning(
                    "Broadcast failed for user %s",
                    target_id
                )

        bot.send_message(
            message.chat.id,
            "📊 <b>BROADCAST COMPLETED</b>\n\n"
            f"✅ Successfully sent: {sent}\n"
            f"❌ Failed: {failed}\n"
            f"👥 Total targets: {len(users)}",
            reply_markup=admin_keyboard()
        )


# ==========================================
# START BOT
# ==========================================

if __name__ == "__main__":

    init_database()

    logger.info("Business Automation Bot is starting...")

    try:
        bot.infinity_polling(
            timeout=30,
            long_polling_timeout=30,
            skip)
