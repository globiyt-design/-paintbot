from telegram import Update
from telegram.ext import ApplicationBuilder, MessageHandler, filters, ContextTypes, CommandHandler
from groq import Groq
import openpyxl
import os

TELEGRAM_TOKEN = "8246064179:AAH6X7rPqDKCxq8g27p-pAcxaeBkRhBabgs"
GROQ_KEY = "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"

client = Groq(api_key=GROQ_KEY)

def save_lead(name, phone, task):
    file = "заявки.xlsx"
    if os.path.exists(file):
        wb = openpyxl.load_workbook(file)
        ws = wb.active
    else:
        wb = openpyxl.Workbook()
        ws = wb.active
        ws.append(["Имя", "Телефон", "Задача"])
    ws.append([name, phone, task])
    wb.save(file)

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data.clear()
    await update.message.reply_text("Привет! Я помощник по покраске стен. Задайте вопрос или оставьте заявку 🎨")

async def chat(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_message = update.message.text
    
    if "user_data" not in context.user_data:
        context.user_data["history"] = []
    
    context.user_data["history"].append({"role": "user", "content": user_message})
    
    messages = [{"role": "system", "content": """Ты помощник компании по покраске стен. 
Отвечай на вопросы клиентов. Когда клиент готов оставить заявку — собери имя, телефон и описание задачи.
Когда получишь все три данных — напиши в конце ответа точно в таком формате:
ЗАЯВКА: Имя=[имя] Телефон=[телефон] Задача=[задача]"""}]
    
    messages += context.user_data["history"]
    
    response = client.chat.completions.create(
        model="llama-3.3-70b-versatile",
        messages=messages
    )
    
    answer = response.choices[0].message.content
    context.user_data["history"].append({"role": "assistant", "content": answer})
    
    if "ЗАЯВКА:" in answer:
        try:
            parts = answer.split("ЗАЯВКА:")[1].strip()
            name = parts.split("Имя=")[1].split()[0]
            phone = parts.split("Телефон=")[1].split()[0]
            task = parts.split("Задача=")[1].strip()
            save_lead(name, phone, task)
            clean_answer = answer.split("ЗАЯВКА:")[0].strip()
            clean_answer += "\n\n✅ Заявка сохранена! Мы свяжемся с вами."
            await update.message.reply_text(clean_answer)
            return
        except:
            pass
    
    await update.message.reply_text(answer)

app = ApplicationBuilder().token(TELEGRAM_TOKEN).build()
app.add_handler(CommandHandler("start", start))
app.add_handler(MessageHandler(filters.TEXT, chat))
app.run_polling()