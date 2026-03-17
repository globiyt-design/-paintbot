from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ApplicationBuilder, MessageHandler, filters, ContextTypes, CommandHandler, CallbackQueryHandler
from groq import Groq
import sqlite3
import os

TELEGRAM_TOKEN = os.environ.get("TELEGRAM_TOKEN")
GROQ_KEY = os.environ.get("GROQ_KEY")

client = Groq(api_key=GROQ_KEY)

# ----------------------------
# Настройка базы данных
# ----------------------------
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

def save_lead(name, phone, task):
    cursor.execute("INSERT INTO leads (name, phone, task) VALUES (?, ?, ?)", (name, phone, task))
    conn.commit()

# ----------------------------
# Старт бота
# ----------------------------
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data.clear()
    keyboard = [[InlineKeyboardButton("Начать заявку", callback_data="start_form")]]
    reply_markup = InlineKeyboardMarkup(keyboard)
    await update.message.reply_text("Привет! Нажмите кнопку, чтобы начать заявку.", reply_markup=reply_markup)

# ----------------------------
# Кнопки старта
# ----------------------------
async def button(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    if query.data == "start_form":
        context.user_data["step"] = "ask_name"
        await query.message.reply_text("Отлично! Как вас зовут?")

# ----------------------------
# Пошаговый чат
# ----------------------------
TASK_OPTIONS = ["Покраска стен", "Ремонт", "Доставка", "Другое"]

async def chat(update: Update, context: ContextTypes.DEFAULT_TYPE):
    step = context.user_data.get("step")
    if not step:
        return  # Ждём нажатия кнопки "Начать заявку"

    # ------------------ Шаг 1: имя ------------------
    if step == "ask_name":
        context.user_data["name"] = update.message.text
        context.user_data["step"] = "ask_phone"
        await update.message.reply_text("Напишите ваш номер телефона")
        return

    # ------------------ Шаг 2: телефон ------------------
    if step == "ask_phone":
        context.user_data["phone"] = update.message.text
        context.user_data["step"] = "ask_task"

        # Кнопки популярных задач
        keyboard = [[InlineKeyboardButton(t, callback_data=f"task_{t}")] for t in TASK_OPTIONS]
        reply_markup = InlineKeyboardMarkup(keyboard)
        await update.message.reply_text("Выберите тип задачи или напишите свой вариант:", reply_markup=reply_markup)
        return

    # ------------------ Шаг 3: задача (текст пользователем) ------------------
    if step == "ask_task_text":
        context.user_data["task"] = update.message.text
        await process_task(update, context)
        return

# ----------------------------
# Обработка кнопок выбора задачи
# ----------------------------
async def task_button(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    task_text = query.data.replace("task_", "")
    
    if task_text == "Другое":
        # Пользователь будет писать свой вариант
        context.user_data["step"] = "ask_task_text"
        await query.message.reply_text("Напишите, пожалуйста, вашу задачу:")
        return

    # Выбран один из популярных вариантов
    context.user_data["task"] = task_text
    await process_task(query, context)

# ----------------------------
# Отправка задачи ИИ и сохранение заявки
# ----------------------------
async def process_task(update_or_query, context: ContextTypes.DEFAULT_TYPE):
    messages = [
        {"role": "system", "content": """
Ты помощник компании. Отвечай клиенту вежливо и по делу.
Когда клиент готов оставить заявку — собери Имя, Телефон и Задачу.
"""}, 
        {"role": "user", "content": context.user_data["task"]}
    ]

    response = client.chat.completions.create(
        model="llama-3.3-70b-versatile",
        messages=messages
    )

    answer = response.choices[0].message.content
    save_lead(context.user_data["name"], context.user_data["phone"], context.user_data["task"])

    # Кнопка "Сделать новую заявку"
    keyboard = [[InlineKeyboardButton("Сделать новую заявку", callback_data="start_form")]]
    reply_markup = InlineKeyboardMarkup(keyboard)

    # Определяем объект для отправки (Message или CallbackQuery)
    if hasattr(update_or_query, "message"):
        await update_or_query.message.reply_text(f"{answer}\n\n✅ Ваша заявка сохранена!", reply_markup=reply_markup)
    else:
        await update_or_query.edit_message_text(f"{answer}\n\n✅ Ваша заявка сохранена!", reply_markup=reply_markup)

    context.user_data.clear()

# ----------------------------
# Запуск бота
# ----------------------------
app = ApplicationBuilder().token(TELEGRAM_TOKEN).build()
app.add_handler(CommandHandler("start", start))
app.add_handler(CallbackQueryHandler(button, pattern="^start_form$"))
app.add_handler(CallbackQueryHandler(task_button, pattern="^task_"))
app.add_handler(MessageHandler(filters.TEXT, chat))
app.run_polling()
