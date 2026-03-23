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


async def notify_admin(context: ContextTypes.DEFAULT_TYPE, name, phone, task):
    await context.bot.send_message(
        chat_id=ADMIN_ID,
        text=f"🔥 Новая заявка!\nИмя: {name}\nТелефон: {phone}\nЗадача: {task}"
    )


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id == ADMIN_ID:
        keyboard = [["📋 Оставить заявку", "👀 Посмотреть заявки"]]
    else:
        keyboard = [["📋 Оставить заявку"]]

    reply_markup = ReplyKeyboardMarkup(keyboard, resize_keyboard=True)

    await update.message.reply_text(
        "Привет! Нажми кнопку, чтобы оставить заявку.",
        reply_markup=reply_markup
    )


async def get_db(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_ID:
        await update.message.reply_text("❌ Ты не админ")
        return

    if not os.path.exists("leads.db"):
        await update.message.reply_text("❌ База не найдена")
        return

    with open("leads.db", "rb") as f:
        await update.message.reply_document(f)


async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text

    # ❌ Отмена
    if text == '❌ Отменить заявку':
        context.user_data.clear()

        if update.effective_user.id == ADMIN_ID:
            keyboard = [["📋 Оставить заявку", "👀 Посмотреть заявки"]]
        else:
            keyboard = [["📋 Оставить заявку"]]

        reply_markup = ReplyKeyboardMarkup(keyboard, resize_keyboard=True)

        await update.message.reply_text(
            '❌ Заявка отменена',
            reply_markup=reply_markup
        )
        return

    # 📋 Старт заявки
    if text == "📋 Оставить заявку":
        context.user_data["step"] = "name"

        keyboard = [['❌ Отменить заявку']]
        reply_markup = ReplyKeyboardMarkup(keyboard, resize_keyboard=True)

        await update.message.reply_text("Введите имя:", reply_markup=reply_markup)
        return

    # 👀 Заявки (админ)
    if text == "👀 Посмотреть заявки" and update.effective_user.id == ADMIN_ID:
        await leads(update, context)
        return

    # 👤 Имя
    if context.user_data.get("step") == "name":
        context.user_data["name"] = text
        context.user_data["step"] = "phone"

        keyboard = [['❌ Отменить заявку']]
        reply_markup = ReplyKeyboardMarkup(keyboard, resize_keyboard=True)

        await update.message.reply_text("Введите телефон:", reply_markup=reply_markup)
        return

    # 📞 Телефон
    if context.user_data.get("step") == "phone":

        clean_phone = text.replace(" ", "")

        if not clean_phone.isdigit():
            await update.message.reply_text("❌ Введите только цифры (можно с пробелами)")
            return

        if len(clean_phone) < 10 or len(clean_phone) > 15:
            await update.message.reply_text("❌ Введите корректный номер (10–15 цифр)")
            return

        context.user_data["phone"] = clean_phone
        context.user_data["step"] = "task"

        keyboard = [['❌ Отменить заявку']]
        reply_markup = ReplyKeyboardMarkup(keyboard, resize_keyboard=True)

        await update.message.reply_text("Опишите задачу:", reply_markup=reply_markup)
        return

    # 📝 Задача
    if context.user_data.get("step") == "task":

        if len(text) > 500:
            await update.message.reply_text("❌ Слишком длинное описание (макс 500 символов)")
            return

        name = context.user_data.get("name")
        phone = context.user_data.get("phone")
        task = text

        save_lead(name, phone, task)
        await notify_admin(context, name, phone, task)

        if update.effective_user.id == ADMIN_ID:
            keyboard = [["📋 Оставить заявку", "👀 Посмотреть заявки"]]
        else:
            keyboard = [["📋 Оставить заявку"]]

        reply_markup = ReplyKeyboardMarkup(keyboard, resize_keyboard=True)

        await update.message.reply_text(
            "✅ Ваша заявка сохранена!",
            reply_markup=reply_markup
        )

        context.user_data.clear()
        return


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


def main():
    init_db()
    app = ApplicationBuilder().token(TELEGRAM_TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("leads", leads))
    app.add_handler(CommandHandler("db", get_db))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))

    print("Бот запущен...")
    app.run_polling()


if __name__ == "__main__":
    main()
