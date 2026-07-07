import requests
import logging
from telegram import Update
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

TELEGRAM_TOKEN = "8715390060:AAHT0IeCllzTJXgY4CusGDiHyBGMwQIxYEw"
API_URL = "https://softltd-softltd-ai.hf.space/v1/chat/completions"

user_conversations = {}

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    user_conversations[user_id] = []
    await update.message.reply_text(
        "🤖 Привет! Я Qwen3.5 9B бот.\n"
        "Задайте любой вопрос!\n"
        "/clear - очистить историю\n"
        "/help - помощь"
    )

async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "📝 Просто напишите сообщение.\n"
        "/clear - очистить историю\n"
        "/start - начать сначала"
    )

async def clear_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    user_conversations[user_id] = []
    await update.message.reply_text("🧹 История очищена!")

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    user_message = update.message.text
    
    logger.info(f"Сообщение от {user_id}: {user_message[:50]}...")
    
    if user_id not in user_conversations:
        user_conversations[user_id] = []
    
    user_conversations[user_id].append({"role": "user", "content": user_message})
    
    try:
        payload = {
            "model": "Qwen3.5-9B",
            "messages": user_conversations[user_id][-5:],
            "temperature": 0.7,
            "max_tokens": 200,
            "stream": False
        }
        
        response = requests.post(
            API_URL,
            headers={"Content-Type": "application/json"},
            json=payload,
            timeout=180
        )
        
        if response.status_code == 200:
            result = response.json()
            if "choices" in result and len(result["choices"]) > 0:
                assistant_message = result["choices"][0]["message"]["content"]
            else:
                assistant_message = "Не удалось получить ответ от модели"
            
            user_conversations[user_id].append({"role": "assistant", "content": assistant_message})
            
            if len(assistant_message) > 4000:
                for i in range(0, len(assistant_message), 4000):
                    await update.message.reply_text(assistant_message[i:i+4000])
            else:
                await update.message.reply_text(assistant_message)
        else:
            logger.error(f"API Error: {response.status_code}")
            await update.message.reply_text(f"❌ Ошибка API: {response.status_code}")
            
    except requests.exceptions.Timeout:
        await update.message.reply_text("⏰ Модель обрабатывает запрос слишком долго. Попробуйте упростить вопрос.")
    except Exception as e:
        logger.error(f"Error: {str(e)}")
        await update.message.reply_text(f"❌ Ошибка: {str(e)}")

def main():
    application = Application.builder().token(TELEGRAM_TOKEN).build()
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("help", help_command))
    application.add_handler(CommandHandler("clear", clear_command))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    
    logger.info("🚀 Запуск бота...")
    application.run_polling(allowed_updates=Update.ALL_TYPES)

if __name__ == "__main__":
    main()
