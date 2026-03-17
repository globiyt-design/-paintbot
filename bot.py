from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, InputFile
from telegram.ext import ApplicationBuilder, MessageHandler, filters, ContextTypes, CommandHandler, CallbackQueryHandler
from groq import Groq
import sqlite3
import openpyxl
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
# Экспорт заявок в Excel
# ----------------------------
def export_leads_to_excel():
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.append(["ID", "Имя", "Телефон", "Задача"])
    cursor.execute("SELECT * FROM leads")
    rows = cursor.fetchall()
    for row in rows:
        ws.append(row)
    file_name = "all_leads.xlsx"
    wb.save(file_name)
    return file_name

# ----------------------------
# Настройка стартовой кнопки
# ----------------------------
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data.clear()
    keyboard = [
        [InlineKeyboardButton("Начать заявку", callback_data="start_form")],
        [InlineKeyboardButton("Получить все заявки (админ)", callback_data="get_leads")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    await update.message.reply_text("Привет! Выберите действие:", reply_markup=reply_markup)

# ----------------------------
# Обработка кнопок
# ----------------------------
async def button(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    if query.data == "start_form":
        context.user_data["step"] = "ask_name"
        await query.message.reply_text("Отлично! Как вас зовут?")
    elif query.data == "get_leads":
        file_name = export_leads_to_excel()
        await query.message.reply_document(document=InputFile(file_name), caption="Все текущие заявки")

# ----------------------------
# Пошаговый сбор заявки
# ----------------------------
TASK_OPTIONS = ["Покраска стен", "Ремонт", "Доставка", "Другое"]

async def chat(update: Update, context: ContextTypes.DEFAULT_TYPE):
    step = context.user_data.get("step")
    if not step:
        return  # Ждём нажатия кнопки "Начать заявку"

    if step == "ask_name":
        context.user_data["name"] = update.message.text
        context.user_data["step"] = "ask_phone"
        await update.message.reply_text("Напишите ваш номер телефона")
        return

    if step == "ask_phone":
        context.user_data["phone"] = update.message.text
        context.user_data["step"] = "ask_task"

        # Кнопки популярных задач
        keyboard = [[InlineKeyboardButton(t, callback_data=f"task_{t}")] for t in TASK_OPTIONS]
        reply_markup = InlineKeyboardMarkup(keyboard)
        await update.message.reply_text("Выберите тип задачи или напишите свой вариант:", reply_markup=reply_markup)
        return

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
        context.user_data["step"] = "ask_task_text"
        await query.message.reply_text("Напишите, пожалуйста, вашу задачу:")
        return

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
app.add_handler(CallbackQueryHandler(button, pattern="^start_form$|^get_leads$"))
app.add_handler(CallbackQueryHandler(task_button, pattern="^task_"))
app.add_handler(MessageHandler(filters.TEXT, chat))
app.run_polling()
