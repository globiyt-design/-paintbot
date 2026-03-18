import sqlite3
from telegram import Update, ReplyKeyboardMarkup
from telegram.ext import ApplicationBuilder, CommandHandler, MessageHandler, filters, ContextTypes
import os

TELEGRAM_TOKEN = os.environ.get("TELEGRAM_TOKEN")
ADMIN_ID = int(os.environ.get("ADMIN_ID"))  


def init_db():
    conn = sqlite3.connect("leads.db")
    cursor = conn.cursor()
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS leads (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT,
            phone TEXT,
            task TEXT
        )
    """)
    conn.commit()
    conn.close()

def save_lead(name, phone, task):
    conn = sqlite3.connect("leads.db")
    cursor = conn.cursor()
    cursor.execute(
        "INSERT INTO leads (name, phone, task) VALUES (?, ?, ?)",
        (name, phone, task)
    )
    conn.commit()
    conn.close()
    print("✅ Заявка сохранена в базе:", name, phone, task)

async def notify_admin(context: ContextTypes.DEFAULT_TYPE, name, phone, task):
    await context.bot.send_message(
        chat_id=ADMIN_ID,
        text=f"🔥 Новая заявка!\nИмя: {name}\nТелефон: {phone}\nЗадача: {task}"
    )

# ----------------------
# --- Команды ---
# ----------------------
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    keyboard = [["📋 Оставить заявку"]]
    reply_markup = ReplyKeyboardMarkup(keyboard, resize_keyboard=True)

    await update.message.reply_text(
        "Привет! Нажми кнопку, чтобы оставить заявку.",
        reply_markup=reply_markup
    )

# ----------------------
# --- Обработка сообщений ---
# ----------------------
async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text
    print("ПОЛУЧЕНО СООБЩЕНИЕ:", text, "ШАГ:", context.user_data.get("step"))

    # Начало заявки
    if text == "📋 Оставить заявку":
        context.user_data["step"] = "name"
        await update.message.reply_text("Введите имя:")
        return

    # Шаг 1 — имя
    if context.user_data.get("step") == "name":
        context.user_data["name"] = text
        context.user_data["step"] = "phone"
        await update.message.reply_text("Введите телефон:")
        return

    # Шаг 2 — телефон
    if context.user_data.get("step") == "phone":
        context.user_data["phone"] = text
        context.user_data["step"] = "task"
        await update.message.reply_text("Опишите задачу:")
        return

    # Шаг 3 — задача
    if context.user_data.get("step") == "task":
        name = context.user_data.get("name")
        phone = context.user_data.get("phone")
        task = text

        # Сохранение в базу
        save_lead(name, phone, task)

        # Уведомление админа
        await notify_admin(context, name, phone, task)

        await update.message.reply_text("✅ Ваша заявка сохранена!")

        # Очистка данных
        context.user_data.clear()
        return

# ----------------------
# --- Команда просмотра заявок (только для админа) ---
# ----------------------
async def leads(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_ID:
        await update.message.reply_text("❌ У вас нет доступа.")
        return

    conn = sqlite3.connect("leads.db")
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM leads ORDER BY id DESC")
    rows = cursor.fetchall()
    conn.close()

    if not rows:
        await update.message.reply_text("Заявок пока нет.")
        return

    text = ""
    for row in rows:
        text += f"ID: {row[0]}\nИмя: {row[1]}\nТелефон: {row[2]}\nЗадача: {row[3]}\n\n"

    await update.message.reply_text(text)

# ----------------------
# --- Запуск бота ---
# ----------------------
def main():
    init_db()
    app = ApplicationBuilder().token(TELEGRAM_TOKEN).build()  # <-- здесь TELEGRAM_TOKEN

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("leads", leads))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))

    print("Бот запущен...")
    app.run_polling()

if __name__ == "__main__":
    main()
