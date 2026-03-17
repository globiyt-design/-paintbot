from telegram import Update
from telegram.ext import ApplicationBuilder, MessageHandler, filters, ContextTypes, CommandHandler
from groq import Groq
import openpyxl
import os

TELEGRAM_TOKEN = os.environ.get("TELEGRAM_TOKEN")
GROQ_KEY = os.environ.get("GROQ_KEY")

client = Groq(api_key=GROQ_KEY)

def save_lead(name, phone, task):
    try:
        file = "zayavki.xlsx"
        if os.path.exists(file):
            wb = openpyxl.load_workbook(file)
            ws = wb.active
        else:
            wb = openpyxl.Workbook()
            ws = wb.active
            ws.append(["Имя", "Телефон", "Задача"])
        ws.append([name, phone, task])
        wb.save(file)
    except Exception as e:
        print("Ошибка сохранения:", e)

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data.clear()
    await update.message.reply_text("Привет! Я помошник Айко-аудит Напиши свой вопрос.")

async def chat(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        user_message = update.message.text

        # фикс истории
        if "history" not in context.user_data:
            context.user_data["history"] = []

        context.user_data["history"].append({
            "role": "user",
            "content": user_message
        })

        messages = [
            {
                "role": "system",
                "content": """Ты помошник бухгалтерской организации-калькулятора.
Отвечай на вопросы клиентов.
Когда клиент готов оставить заявку — собери имя, телефон и задачу.
Когда получишь все данные, напиши:

ЗАЯВКА: Имя=[имя] Телефон=[телефон] Задача=[задача]"""
            }
        ] + context.user_data["history"]

        response = client.chat.completions.create(
            model="llama-3.3-70b-versatile",
            messages=messages
        )

        answer = response.choices[0].message.content

        context.user_data["history"].append({
            "role": "assistant",
            "content": answer
        })

        # обработка заявки
        if "ЗАЯВКА:" in answer:
            try:
                parts = answer.split("ЗАЯВКА:")[1].strip()
                name = parts.split("Имя=")[1].split()[0]
                phone = parts.split("Телефон=")[1].split()[0]
                task = parts.split("Задача=")[1].strip()

                save_lead(name, phone, task)

                clean = answer.split("ЗАЯВКА:")[0].strip()
                clean += "\n\n✅ Заявка сохранена!"
                await update.message.reply_text(clean)
                return
            except Exception as e:
                print("Ошибка парсинга:", e)

        await update.message.reply_text(answer)

    except Exception as e:
        print("Ошибка бота:", e)
        await update.message.reply_text("Ошибка 😢 попробуй позже")

app = ApplicationBuilder().token(TELEGRAM_TOKEN).build()

app.add_handler(CommandHandler("start", start))
app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, chat))

print("Бот запущен...")
app.run_polling()
