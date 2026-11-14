import os
import time
import html
import sqlite3
import logging
import threading
from datetime import datetime, timezone

import telebot
from telebot import types


# ============================================================
# 1. CONFIGURATION
# ============================================================

# Local/Pydroid: paste your NEW BotFather token between quotes.
# Railway: set the BOT_TOKEN environment variable instead.
BOT_TOKEN = os.getenv("BOT_TOKEN", "9082925617:AAGdDLmBdFbWgNM0sOdjJXFViQPyJFZyJE0")

ADMIN_ID = 7499911678
BOT_NAME = "Premium Business Assistant"
DB_NAME = os.getenv("DB_PATH", "business_bot.db")
SUPPORT_USERNAME = ""  # Example: "your_support_username"

SERVICES = [
    ("🌐 Website Development", "Professional website development."),
    ("🤖 AI Automation", "AI-powered business automation."),
    ("🎨 Graphic Design", "Premium graphic design services."),
    ("📱 Social Media Management", "Social media management services."),
    ("💻 Custom Software", "Custom software solutions."),
]

MAX_ORDER_DETAILS = 2500
BROADCAST_DELAY_SECONDS = 0.05


# ============================================================
# 2. LOGGING AND BOT INITIALIZATION
# ============================================================

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(message)s"
)
logger = logging.getLogger("BusinessBot")

if (
    not BOT_TOKEN
    or BOT_TOKEN == "PASTE_YOUR_NEW_BOT_TOKEN_HERE"
    or ":" not in BOT_TOKEN
):
    raise ValueError(
        "Set your NEW Telegram BotFather token in BOT_TOKEN "
        "or configure the BOT_TOKEN environment variable."
    )

bot = telebot.TeleBot(BOT_TOKEN, threaded=True)


# ============================================================
# 3. DATABASE
# ============================================================

db_lock = threading.RLock()


def get_db():
    conn = sqlite3.connect(
        DB_NAME,
        timeout=30,
        check_same_thread=False
    )
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    conn.execute("PRAGMA busy_timeout = 30000")
    return conn


def init_database():
    with db_lock:
        conn = get_db()
        try:
            conn.execute("PRAGMA journal_mode=WAL")

            conn.execute("""
                CREATE TABLE IF NOT EXISTS users (
                    user_id INTEGER PRIMARY KEY,
                    username TEXT NOT NULL DEFAULT '',
                    first_name TEXT NOT NULL DEFAULT '',
                    joined_at TEXT NOT NULL,
                    last_seen TEXT NOT NULL
                )
            """)

            conn.execute("""
                CREATE TABLE IF NOT EXISTS orders (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id INTEGER NOT NULL,
                    service TEXT NOT NULL,
                    customer_name TEXT NOT NULL,
                    details TEXT NOT NULL,
                    status TEXT NOT NULL DEFAULT 'Pending',
                    created_at TEXT NOT NULL,
                    FOREIGN KEY (user_id)
                        REFERENCES users(user_id)
                )
            """)

            conn.execute("""
                CREATE TABLE IF NOT EXISTS settings (
                    key TEXT PRIMARY KEY,
                    value TEXT NOT NULL
                )
            """)

            conn.execute("""
                INSERT OR IGNORE INTO settings (key, value)
                VALUES ('maintenance', '0')
            """)

            conn.commit()
            logger.info("Database initialized.")
        finally:
            conn.close()


def now_text():
    return datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")


def save_user(user):
    timestamp = now_text()
    with db_lock:
        conn = get_db()
        try:
            conn.execute("""
                INSERT INTO users (
                    user_id, username, first_name, joined_at, last_seen
                )
                VALUES (?, ?, ?, ?, ?)
                ON CONFLICT(user_id) DO UPDATE SET
                    username = excluded.username,
                    first_name = excluded.first_name,
                    last_seen = excluded.last_seen
            """, (
                user.id,
                user.username or "",
                user.first_name or "",
                timestamp,
                timestamp
            ))
            conn.commit()
        finally:
            conn.close()


def save_order(user_id, service, customer_name, details):
    with db_lock:
        conn = get_db()
        try:
            cursor = conn.execute("""
                INSERT INTO orders (
                    user_id, service, customer_name,
                    details, status, created_at
                )
                VALUES (?, ?, ?, ?, 'Pending', ?)
            """, (
                user_id,
                service,
                customer_name,
                details,
                now_text()
            ))
            order_id = cursor.lastrowid
            conn.commit()
            return order_id
        finally:
            conn.close()


def get_setting(key, default="0"):
    with db_lock:
        conn = get_db()
        try:
            row = conn.execute(
                "SELECT value FROM settings WHERE key = ?",
                (key,)
            ).fetchone()
            return row["value"] if row else default
        finally:
            conn.close()


def set_setting(key, value):
    with db_lock:
        conn = get_db()
        try:
            conn.execute("""
                INSERT INTO settings (key, value)
                VALUES (?, ?)
                ON CONFLICT(key) DO UPDATE SET value = excluded.value
            """, (key, str(value)))
            conn.commit()
        finally:
            conn.close()


def get_statistics():
    with db_lock:
        conn = get_db()
        try:
            users = conn.execute(
                "SELECT COUNT(*) AS n FROM users"
            ).fetchone()["n"]

            orders = conn.execute(
                "SELECT COUNT(*) AS n FROM orders"
            ).fetchone()["n"]

            pending = conn.execute("""
                SELECT COUNT(*) AS n FROM orders
                WHERE status = 'Pending'
            """).fetchone()["n"]

            return users, orders, pending
        finally:
            conn.close()


def get_recent_orders(limit=10):
    with db_lock:
        conn = get_db()
        try:
            return conn.execute("""
                SELECT id, user_id, service, customer_name,
                       details, status, created_at
                FROM orders
                ORDER BY id DESC
                LIMIT ?
            """, (limit,)).fetchall()
        finally:
            conn.close()


def get_all_user_ids():
    with db_lock:
        conn = get_db()
        try:
            rows = conn.execute(
                "SELECT user_id FROM users ORDER BY user_id"
            ).fetchall()
            return [row["user_id"] for row in rows]
        finally:
            conn.close()


# ============================================================
# 4. IN-MEMORY USER SESSIONS
# ============================================================

user_states = {}
user_data = {}
session_lock = threading.RLock()


def set_state(user_id, state):
    with session_lock:
        user_states[user_id] = state


def get_state(user_id):
    with session_lock:
        return user_states.get(user_id)


def set_data(user_id, key, value):
    with session_lock:
        user_data.setdefault(user_id, {})
        user_data[user_id][key] = value


def get_data(user_id, key, default=None):
    with session_lock:
        return user_data.get(user_id, {}).get(key, default)


def clear_session(user_id):
    with session_lock:
        user_states.pop(user_id, None)
        user_data.pop(user_id, None)


# ============================================================
# 5. KEYBOARDS
# ============================================================

def main_keyboard():
    markup = types.InlineKeyboardMarkup(row_width=2)
    markup.add(
        types.InlineKeyboardButton(
            "🛍 Our Services", callback_data="services"
        ),
        types.InlineKeyboardButton(
            "📦 Book an Order", callback_data="new_order"
        )
    )
    markup.add(
        types.InlineKeyboardButton(
            "❓ FAQs", callback_data="faqs"
        ),
        types.InlineKeyboardButton(
            "💬 Customer Support", callback_data="support"
        )
    )
    return markup


def admin_keyboard():
    markup = types.InlineKeyboardMarkup(row_width=2)
    markup.add(
        types.InlineKeyboardButton(
            "📊 Statistics", callback_data="admin_stats"
        ),
        types.InlineKeyboardButton(
            "📦 Recent Orders", callback_data="admin_orders"
        )
    )
    markup.add(
        types.InlineKeyboardButton(
            "📢 Broadcast", callback_data="admin_broadcast"
        ),
        types.InlineKeyboardButton(
            "🔧 Maintenance", callback_data="admin_maintenance"
        )
    )
    markup.add(
        types.InlineKeyboardButton(
            "🔄 Refresh Panel", callback_data="admin_home"
        )
    )
    return markup


def back_keyboard():
    markup = types.InlineKeyboardMarkup()
    markup.add(
        types.InlineKeyboardButton(
            "⬅️ Main Menu", callback_data="home"
        )
    )
    return markup


def order_confirmation_keyboard():
    markup = types.InlineKeyboardMarkup(row_width=2)
    markup.add(
        types.InlineKeyboardButton(
            "✅ Confirm Order", callback_data="confirm_order"
        ),
        types.InlineKeyboardButton(
            "❌ Cancel", callback_data="cancel_order"
        )
    )
    return markup


# ============================================================
# 6. HELPERS AND ACCESS CONTROL
# ============================================================

def is_admin(user_id):
    return user_id == ADMIN_ID


def maintenance_enabled():
    return get_setting("maintenance", "0") == "1"


def maintenance_message():
    return (
        "🔧 <b>Temporary Maintenance</b>\n\n"
        "Our service is currently under maintenance. "
        "Please try again later. Thank you for your patience."
    )


def send_main_menu(chat_id):
    bot.send_message(
        chat_id,
        f"🏠 <b>{html.escape(BOT_NAME)}</b>\n\n"
        "Please choose an option:",
        reply_markup=main_keyboard(),
        parse_mode="HTML"
    )


def send_admin_panel(chat_id):
    users, orders, pending = get_statistics()
    maintenance = "ON 🔴" if maintenance_enabled() else "OFF 🟢"

    text = (
        "👑 <b>PREMIUM ADMIN PANEL</b>\n\n"
        f"👥 Users: <b>{users}</b>\n"
        f"📦 Orders: <b>{orders}</b>\n"
        f"⏳ Pending: <b>{pending}</b>\n"
        f"🔧 Maintenance: <b>{maintenance}</b>\n\n"
        "Select an administrative action:"
    )
    bot.send_message(
        chat_id,
        text,
        reply_markup=admin_keyboard(),
        parse_mode="HTML"
    )


# ============================================================
# 7. USER-FACING PAGES
# ============================================================

def show_services(chat_id):
    lines = ["🛍 <b>OUR PROFESSIONAL SERVICES</b>\n"]
    for number, (name, description) in enumerate(SERVICES, start=1):
        lines.append(
            f"<b>{number}. {html.escape(name)}</b>\n"
            f"{html.escape(description)}\n"
        )

    bot.send_message(
        chat_id,
        "\n".join(lines),
        reply_markup=back_keyboard(),
        parse_mode="HTML"
    )


def show_faq(chat_id):
    text = (
        "❓ <b>FREQUENTLY ASKED QUESTIONS</b>\n\n"
        "<b>Q1. How can I place an order?</b>\n"
        "Choose Book an Order from the main menu.\n\n"
        "<b>Q2. How will I know my order was received?</b>\n"
        "The bot will send you an order ID after confirmation.\n\n"
        "<b>Q3. How can I contact support?</b>\n"
        "Use the Customer Support option.\n\n"
        "<b>Q4. How long does an order take?</b>\n"
        "Delivery time depends on the selected service.\n\n"
        "<b>Q5. Can I request a custom service?</b>\n"
        "Yes. Describe your requirements in the order details."
    )
    bot.send_message(
        chat_id,
        text,
        reply_markup=back_keyboard(),
        parse_mode="HTML"
    )


def show_support(chat_id):
    username = SUPPORT_USERNAME.strip().lstrip("@")
    if username:
        contact = f"\n\nSupport: @{html.escape(username)}"
    else:
        contact = (
            "\n\nSupport contact has not been configured yet. "
            "Please try again later."
        )

    bot.send_message(
        chat_id,
        "💬 <b>CUSTOMER SUPPORT</b>\n\n"
        "Need assistance? We are here to help."
        + contact,
        reply_markup=back_keyboard(),
        parse_mode="HTML"
    )


# ============================================================
# 8. ORDER BOOKING FLOW
# ============================================================

def begin_order(user_id):
    if maintenance_enabled() and not is_admin(user_id):
        bot.send_message(
            user_id, maintenance_message(), parse_mode="HTML"
        )
        return

    clear_session(user_id)
    set_state(user_id, "order_service")

    markup = types.InlineKeyboardMarkup(row_width=1)
    for index, (name, _description) in enumerate(SERVICES):
        markup.add(
            types.InlineKeyboardButton(
                name,
                callback_data=f"select_service:{index}"
            )
        )

    markup.add(
        types.InlineKeyboardButton(
            "❌ Cancel", callback_data="home"
        )
    )

    bot.send_message(
        user_id,
        "📦 <b>NEW ORDER</b>\n\n"
        "Please select the service you need:",
        reply_markup=markup,
        parse_mode="HTML"
    )


# ============================================================
# 9. COMMAND HANDLERS
# ============================================================

@bot.message_handler(commands=["start"])
def start_command(message):
    user_id = message.from_user.id
    clear_session(user_id)
    save_user(message.from_user)

    if maintenance_enabled() and not is_admin(user_id):
        bot.send_message(
            user_id, maintenance_message(), parse_mode="HTML"
        )
        return

    first_name = html.escape(
        message.from_user.first_name or "Customer"
    )
    bot.send_message(
        user_id,
        f"👋 <b>Welcome, {first_name}!</b>\n\n"
        f"Welcome to <b>{html.escape(BOT_NAME)}</b>.\n"
        "Choose an option below to get started:",
        reply_markup=main_keyboard(),
        parse_mode="HTML"
    )


@bot.message_handler(commands=["cancel"])
def cancel_command(message):
    clear_session(message.from_user.id)
    bot.send_message(
        message.chat.id,
        "❌ Operation cancelled.",
        reply_markup=main_keyboard()
    )


@bot.message_handler(commands=["admin"])
def admin_command(message):
    user_id = message.from_user.id
    if not is_admin(user_id):
        bot.reply_to(message, "⛔ Access denied.")
        return

    clear_session(user_id)
    send_admin_panel(message.chat.id)


# ============================================================
# 10. CALLBACK HANDLER
# ============================================================

@bot.callback_query_handler(func=lambda call: True)
def callback_handler(call):
    user_id = call.from_user.id
    data = call.data or ""

    try:
        bot.answer_callback_query(call.id)

        if data == "home":
            clear_session(user_id)
            if maintenance_enabled() and not is_admin(user_id):
                bot.send_message(
                    user_id, maintenance_message(), parse_mode="HTML"
                )
                return
            send_main_menu(user_id)
            return

        if data == "services":
            if maintenance_enabled() and not is_admin(user_id):
                bot.send_message(
                    user_id, maintenance_message(), parse_mode="HTML"
                )
                return
            show_services(user_id)
            return

        if data == "faqs":
            if maintenance_enabled() and not is_admin(user_id):
                bot.send_message(
                    user_id, maintenance_message(), parse_mode="HTML"
                )
                return
            show_faq(user_id)
            return

        if data == "support":
            show_support(user_id)
            return

        if data == "new_order":
            begin_order(user_id)
            return

        if data.startswith("select_service:"):
            if maintenance_enabled() and not is_admin(user_id):
                clear_session(user_id)
                bot.send_message(
                    user_id, maintenance_message(), parse_mode="HTML"
                )
                return

            if get_state(user_id) != "order_service":
                bot.send_message(
                    user_id,
                    "Your booking session expired. Please use /start."
                )
                return

            try:
                index = int(data.split(":", 1)[1])
                service = SERVICES[index][0]
            except (ValueError, IndexError):
                bot.send_message(
                    user_id,
                    "Invalid service selection. Please try again."
                )
                return

            set_data(user_id, "service", service)
            set_state(user_id, "order_name")
            bot.send_message(
                user_id,
                "👤 <b>Please enter your full name:</b>",
                parse_mode="HTML"
            )
            return

        if data.startswith("admin_"):
            if not is_admin(user_id):
                bot.answer_callback_query(
                    call.id, "Access denied.", show_alert=True
                )
                return

            if data == "admin_home":
                send_admin_panel(user_id)
                return

            if data == "admin_stats":
                users, orders, pending = get_statistics()
                status = "ON 🔴" if maintenance_enabled() else "OFF 🟢"
                text = (
                    "📊 <b>BUSINESS STATISTICS</b>\n\n"
                    f"👥 Total users: <b>{users}</b>\n"
                    f"📦 Total orders: <b>{orders}</b>\n"
                    f"⏳ Pending orders: <b>{pending}</b>\n"
                    f"🔧 Maintenance: <b>{status}</b>"
                )
                bot.send_message(
                    user_id, text,
                    reply_markup=admin_keyboard(),
                    parse_mode="HTML"
                )
                return

            if data == "admin_orders":
                orders = get_recent_orders(10)
                if not orders:
                    bot.send_message(
                        user_id,
                        "📦 No orders have been placed yet.",
                        reply_markup=admin_keyboard()
                    )
                    return

                chunks = ["📦 <b>RECENT ORDERS</b>\n"]
                current = ""
                for order in orders:
                    item = (
                        f"\n🆔 <b>Order #{order['id']}</b>\n"
                        f"👤 {html.escape(order['customer_name'])}\n"
                        f"🛍 {html.escape(order['service'])}\n"
                        f"📌 {html.escape(order['status'])}\n"
                        f"🗓 {html.escape(order['created_at'])}\n"
                        f"🆔 User: <code>{order['user_id']}</code>\n"
                        "━━━━━━━━━━━━━━\n"
                    )
                    if len(current) + len(item) > 3500:
                        chunks.append(current)
                        current = ""
                    current += item

                if current:
                    chunks.append(current)

                for chunk in chunks:
                    bot.send_message(
                        user_id, chunk,
                        parse_mode="HTML"
                    )

                bot.send_message(
                    user_id,
                    "Admin controls:",
                    reply_markup=admin_keyboard()
                )
                return

            if data == "admin_broadcast":
                clear_session(user_id)
                set_state(user_id, "admin_broadcast")
                bot.send_message(
                    user_id,
                    "📢 <b>BROADCAST</b>\n\n"
                    "Send the text message to deliver to all users "
                    "who have started this bot.\n\n"
                    "Send /cancel to stop.",
                    parse_mode="HTML"
                )
                return

            if data == "admin_maintenance":
                currently_on = maintenance_enabled()
                new_value = "0" if currently_on else "1"
                set_setting("maintenance", new_value)
                status = "DISABLED 🟢" if currently_on else "ENABLED 🔴"
                bot.send_message(
                    user_id,
                    f"🔧 Maintenance mode: <b>{status}</b>",
                    reply_markup=admin_keyboard(),
                    parse_mode="HTML"
                )
                return

        if data in ("confirm_order", "cancel_order"):
            if get_state(user_id) != "order_confirm":
                bot.send_message(
                    user_id,
                    "Your booking session expired. Please start again."
                )
                return

            if data == "cancel_order":
                clear_session(user_id)
                bot.send_message(
                    user_id,
                    "❌ Order cancelled.",
                    reply_markup=main_keyboard()
                )
                return

            service = get_data(user_id, "service")
            name = get_data(user_id, "name")
            details = get_data(user_id, "details")

            if not all((service, name, details)):
                clear_session(user_id)
                bot.send_message(
                    user_id,
                    "Order information is incomplete. Please start again."
                )
                return

            order_id = save_order(
                user_id, service, name, details
            )
            clear_session(user_id)

            bot.send_message(
                user_id,
                "✅ <b>ORDER RECEIVED</b>\n\n"
                f"🆔 Order ID: <b>#{order_id}</b>\n"
                f"🛍 Service: {html.escape(service)}\n"
                f"👤 Name: {html.escape(name)}\n\n"
                "Your request has been saved. Our team will review it.",
                reply_markup=main_keyboard(),
                parse_mode="HTML"
            )

            admin_text = (
                "🔔 <b>NEW ORDER</b>\n\n"
                f"🆔 Order: #{order_id}\n"
                f"👤 Name: {html.escape(name)}\n"
                f"🛍 Service: {html.escape(service)}\n"
                f"📝 Details: {html.escape(details)}\n"
                f"🆔 User ID: <code>{user_id}</code>"
            )
            try:
                bot.send_message(
                    ADMIN_ID, admin_text, parse_mode="HTML"
                )
            except Exception:
                logger.exception("Could not notify administrator.")
            return

    except Exception:
        logger.exception("Callback handler failed.")
        try:
            bot.send_message(
                user_id,
                "⚠️ Something went wrong. Please try again."
            )
        except Exception:
            logger.exception("Could not send callback error message.")


# ============================================================
# 11. TEXT STATE HANDLER
# ============================================================

@bot.message_handler(
    content_types=["text"],
    func=lambda message: get_state(message.from_user.id) is not None
)
def state_handler(message):
    user_id = message.from_user.id
    state = get_state(user_id)
    text = (message.text or "").strip()

    if text.startswith("/"):
        bot.send_message(
            user_id,
            "Use /cancel to cancel the current operation."
        )
        return

    if state == "order_name":
        if not text or len(text) > 100:
            bot.send_message(
                user_id,
                "Please enter a name of 1 to 100 characters."
            )
            return

        set_data(user_id, "name", text)
        set_state(user_id, "order_details")
        bot.send_message(
            user_id,
            "📝 <b>Please describe the service you need:</b>\n"
            f"(Maximum {MAX_ORDER_DETAILS} characters)",
            parse_mode="HTML"
        )
        return

    if state == "order_details":
        if not text or len(text) > MAX_ORDER_DETAILS:
            bot.send_message(
                user_id,
                f"Please enter details of 1 to {MAX_ORDER_DETAILS} characters."
            )
            return

        set_data(user_id, "details", text)
        set_state(user_id, "order_confirm")

        service = html.escape(get_data(user_id, "service", ""))
        name = html.escape(get_data(user_id, "name", ""))

        bot.send_message(
            user_id,
            "📋 <b>ORDER SUMMARY</b>\n\n"
            f"👤 Name: {name}\n"
            f"🛍 Service: {service}\n"
            f"📝 Details: {html.escape(text)}\n\n"
            "Please confirm your order.",
            reply_markup=order_confirmation_keyboard(),
            parse_mode="HTML"
        )
        return

    if state == "admin_broadcast":
        if not is_admin(user_id):
            clear_session(user_id)
            return

        if not text:
            bot.send_message(user_id, "Please send a non-empty text message.")
            return

        clear_session(user_id)
        recipients = get_all_user_ids()
        sent = 0
        failed = 0

        progress = bot.send_message(
            user_id,
            f"📢 Starting broadcast to {len(recipients)} registered users..."
        )

        for recipient in recipients:
            try:
                bot.send_message(
                    recipient,
                    "📢 <b>BUSINESS ANNOUNCEMENT</b>\n\n"
                    + html.escape(text),
                    parse_mode="HTML"
                )
                sent += 1
                time.sleep(BROADCAST_DELAY_SECONDS)
            except Exception as exc:
                failed += 1
                logger.warning(
                    "Broadcast failed for user %s: %s",
                    recipient, exc
                )

        try:
            bot.edit_message_text(
                "✅ <b>BROADCAST FINISHED</b>\n\n"
                f"👥 Recipients: {len(recipients)}\n"
                f"✅ Sent: {sent}\n"
                f"❌ Failed: {failed}",
                user_id,
                progress.message_id,
                parse_mode="HTML"
            )
        except Exception:
            bot.send_message(
                user_id,
                f"Broadcast finished. Sent: {sent}; failed: {failed}."
            )


# ============================================================
# 12. FALLBACK HANDLER
# ============================================================

@bot.message_handler(content_types=["text"], func=lambda message: True)
def fallback_handler(message):
    user_id = message.from_user.id
    save_user(message.from_user)

    if maintenance_enabled() and not is_admin(user_id):
        bot.send_message(
            user_id, maintenance_message(), parse_mode="HTML"
        )
        return

    bot.send_message(
        user_id,
        "Please use the menu buttons below.",
        reply_markup=main_keyboard()
    )


# ============================================================
# 13. STARTUP
# ============================================================

def main():
    logger.info("Starting %s...", BOT_NAME)
    init_database()
    logger.info("Database ready. Admin ID: %s", ADMIN_ID)

    # Remove any old webhook so long polling can work.
    try:
        bot.remove_webhook()
    except Exception:
        logger.exception("Could not remove webhook; continuing.")

    bot.infinity_polling(
        timeout=30,
        long_polling_timeout=30,
        skip_pending=True,
        allowed_updates=["message", "callback_query"]
    )


if __name__ == "__main__":
    main()
