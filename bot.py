import requests
import logging
from telegram import Update
from telegram.ext import Updater, CommandHandler, MessageHandler, Filters, CallbackContext

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

TELEGRAM_TOKEN = "8715390060:AAHT0IeCllzTJXgY4CusGDiHyBGMwQIxYEw"
API_URL = "https://softltd-softltd-ai.hf.space/v1/chat/completions"

user_conversations = {}

def start(update: Update, context: CallbackContext):
    user_id = update.effective_user.id
    user_conversations[user_id] = []
    update.message.reply_text(
        "🤖 Привет! Я Qwen3.5 9B бот.\n"
        "Задайте любой вопрос!\n"
        "/clear - очистить историю\n"
        "/help - помощь"
    )

def help_command(update: Update, context: CallbackContext):
    update.message.reply_text(
        "📝 Просто напишите сообщение.\n"
        "/clear - очистить историю\n"
        "/start - начать сначала"
    )

def clear_command(update: Update, context: CallbackContext):
    user_id = update.effective_user.id
    user_conversations[user_id] = []
    update.message.reply_text("🧹 История очищена!")

def handle_message(update: Update, context: CallbackContext):
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
            "max_tokens": 200
        }
        
        response = requests.post(API_URL, json=payload, timeout=180)
        
        if response.status_code == 200:
            result = response.json()
            if "choices" in result:
                assistant_message = result["choices"][0]["message"]["content"]
                user_conversations[user_id].append({"role": "assistant", "content": assistant_message})
                update.message.reply_text(assistant_message)
            else:
                update.message.reply_text("❌ Не удалось получить ответ")
        else:
            update.message.reply_text(f"❌ Ошибка API: {response.status_code}")
            
    except requests.exceptions.Timeout:
        update.message.reply_text("⏰ Модель обрабатывает запрос слишком долго. Попробуйте упростить вопрос.")
    except Exception as e:
        logger.error(f"Error: {str(e)}")
        update.message.reply_text(f"❌ Ошибка: {str(e)}")

def main():
    updater = Updater(TELEGRAM_TOKEN, use_context=True)
    dp = updater.dispatcher
    
    dp.add_handler(CommandHandler("start", start))
    dp.add_handler(CommandHandler("help", help_command))
    dp.add_handler(CommandHandler("clear", clear_command))
    dp.add_handler(MessageHandler(Filters.text & ~Filters.command, handle_message))
    
    logger.info("🚀 Запуск бота...")
    updater.start_polling()
    updater.idle()

if __name__ == "__main__":
    main()
