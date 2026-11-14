
import sqlite3
from datetime import datetime
from telebot import types

DB_NAME = "factory.db"

BOT_TYPES = {
    "channel": "Channel Management Bot",
    "business": "Business Assistant Bot",
    "ai": "AI Assistant Bot",
    "support": "Customer Support Bot",
    "automation": "Automation Bot"
}


def init_factory():
    conn = sqlite3.connect(DB_NAME)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS factory_projects (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            bot_type TEXT NOT NULL,
            status TEXT DEFAULT 'Planning',
            created_at TEXT NOT NULL
        )
    """)
    conn.commit()
    conn.close()


def create_project(name, bot_type):
    conn = sqlite3.connect(DB_NAME)
    cur = conn.cursor()

    cur.execute("""
        INSERT INTO factory_projects
        (name, bot_type, status, created_at)
        VALUES (?, ?, ?, ?)
    """, (
        name,
        bot_type,
        "Planning",
        datetime.now().isoformat()
    ))

    project_id = cur.lastrowid
    conn.commit()
    conn.close()
    return project_id


def get_projects():
    conn = sqlite3.connect(DB_NAME)
    conn.row_factory = sqlite3.Row

    rows = conn.execute("""
        SELECT * FROM factory_projects
        ORDER BY id DESC
    """).fetchall()

    conn.close()
    return [dict(row) for row in rows]


def register_factory_handlers(bot):

    init_factory()

    def is_admin(user_id):
        import os
        admins = os.getenv("FACTORY_ADMIN_IDS", "")
        allowed = [
            int(x.strip())
            for x in admins.split(",")
            if x.strip().isdigit()
        ]
        return user_id in allowed

    @bot.message_handler(commands=["factory"])
    def factory_menu(message):
        if not is_admin(message.from_user.id):
            bot.reply_to(message, "Access denied.")
            return

        markup = types.InlineKeyboardMarkup(row_width=2)

        markup.add(
            types.InlineKeyboardButton(
                "➕ Create New Bot",
                callback_data="factory_create"
            ),
            types.InlineKeyboardButton(
                "📁 My Projects",
                callback_data="factory_projects"
            )
        )

        bot.reply_to(
            message,
            "🏭 ULTRA PREMIUM BOT FACTORY\n\n"
            "Welcome to your Factory Control Panel.",
            reply_markup=markup
        )

    @bot.callback_query_handler(
        func=lambda call: call.data == "factory_create"
    )
    def factory_create(call):
        if not is_admin(call.from_user.id):
            return

        markup = types.InlineKeyboardMarkup(row_width=2)

        for key, label in BOT_TYPES.items():
            markup.add(
                types.InlineKeyboardButton(
                    label,
                    callback_data=f"factory_type_{key}"
                )
            )

        bot.answer_callback_query(call.id)
        bot.send_message(
            call.message.chat.id,
            "Select the type of bot you want to create:",
            reply_markup=markup
        )

    @bot.callback_query_handler(
        func=lambda call: call.data.startswith("factory_type_")
    )
    def factory_select_type(call):
        if not is_admin(call.from_user.id):
            return

        bot.answer_callback_query(call.id)

        bot.send_message(
            call.message.chat.id,
            "Send the name of your new bot project:"
        )

        bot.register_next_step_handler(
            bot.send_message(
                call.message.chat.id,
                "Example: Premium Business Assistant"
            ),
            save_project_name,
            call.data.replace("factory_type_", "")
        )

    def save_project_name(message, bot_type):
        if not is_admin(message.from_user.id):
            return

        name = message.text.strip() if message.text else ""

        if not name or len(name) > 80:
            bot.reply_to(
                message,
                "Please send a valid project name (1-80 characters)."
            )
            return

        project_id = create_project(name, bot_type)

        bot.reply_to(
            message,
            f"✅ PROJECT CREATED!\n\n"
            f"Project ID: #{project_id}\n"
            f"Name: {name}\n"
            f"Type: {BOT_TYPES[bot_type]}\n"
            f"Status: Planning"
        )

    @bot.callback_query_handler(
        func=lambda call: call.data == "factory_projects"
    )
    def factory_projects(call):
        if not is_admin(call.from_user.id):
            return

        bot.answer_callback_query(call.id)

        projects = get_projects()

        if not projects:
            bot.send_message(
                call.message.chat.id,
                "No projects created yet."
            )
            return

        output = "📁 YOUR FACTORY PROJECTS\n\n"

        for p in projects[:20]:
            output += (
                f"#{p['id']} - {p['name']}\n"
                f"Type: {p['bot_type']}\n"
                f"Status: {p['status']}\n\n"
            )

        bot.send_message(call.message.chat.id, output)
  
