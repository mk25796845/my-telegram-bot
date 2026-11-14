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


# ==========================================
# DATABASE INITIALIZATION
# ==========================================

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


# ==========================================
# PROJECT CREATION
# ==========================================

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


# ==========================================
# GET ALL PROJECTS
# ==========================================

def get_projects():
    conn = sqlite3.connect(DB_NAME)
    conn.row_factory = sqlite3.Row

    rows = conn.execute("""
        SELECT * FROM factory_projects
        ORDER BY id DESC
    """).fetchall()

    conn.close()

    return [dict(row) for row in rows]


# ==========================================
# BOT FACTORY HANDLERS
# ==========================================

def register_factory_handlers(bot):

    init_factory()

    import os

    def is_admin(user_id):
        admins = os.getenv("FACTORY_ADMIN_IDS", "")

        allowed = [
            int(x.strip())
            for x in admins.split(",")
            if x.strip().isdigit()
        ]

        return user_id in allowed

    # ======================================
    # MAIN FACTORY MENU
    # ======================================

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

    # ======================================
    # CREATE NEW BOT MENU
    # ======================================

    @bot.callback_query_handler(
        func=lambda call: call.data == "factory_create"
    )
    def factory_create(call):

        if not is_admin(call.from_user.id):
            bot.answer_callback_query(call.id)
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

    # ======================================
    # SELECT BOT TYPE
    # ======================================

    @bot.callback_query_handler(
        func=lambda call: call.data.startswith("factory_type_")
    )
    def factory_select_type(call):

        if not is_admin(call.from_user.id):
            bot.answer_callback_query(call.id)
            return

        bot.answer_callback_query(call.id)

        bot_type = call.data.replace(
            "factory_type_", ""
        )

        if bot_type not in BOT_TYPES:
            return

        prompt = bot.send_message(
            call.message.chat.id,
            "Send the name of your new bot project:"
        )

        bot.register_next_step_handler(
            prompt,
            save_project_name,
            bot_type
        )

    # ======================================
    # SAVE PROJECT NAME
    # ======================================

    def save_project_name(message, bot_type):

        if not is_admin(message.from_user.id):
            return

        if not message.text:
            bot.reply_to(
                message,
                "Please send a text project name."
            )
            return

        name = message.text.strip()

        if not name or len(name) > 80:
            bot.reply_to(
                message,
                "Project name must be 1-80 characters."
            )
            return

        project_id = create_project(
            name,
            bot_type
        )

        bot.reply_to(
            message,
            "✅ PROJECT CREATED!\n\n"
            f"Project ID: #{project_id}\n"
            f"Name: {name}\n"
            f"Type: {BOT_TYPES[bot_type]}\n"
            "Status: Planning"
        )

    # ======================================
    # VIEW PROJECTS
    # ======================================

    @bot.callback_query_handler(
        func=lambda call: call.data == "factory_projects"
    )
    def factory_projects(call):

        if not is_admin(call.from_user.id):
            bot.answer_callback_query(call.id)
            return

        bot.answer_callback_query(call.id)

        projects = get_projects()

        if not projects:
            bot.send_message(
                call.message.chat.id,
                "📁 No projects created yet."
            )
            return

        output = "📁 YOUR FACTORY PROJECTS\n\n"

        for project in projects[:20]:

            output += (
                f"#{project['id']} - {project['name']}\n"
                f"Type: {project['bot_type']}\n"
                f"Status: {project['status']}\n\n"
            )

        bot.send_message(
            call.message.chat.id,
            output
    )
        
