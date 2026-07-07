import requests
import logging
from flask import Flask, request, jsonify

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

TELEGRAM_TOKEN = "8715390060:AAHT0IeCllzTJXgY4CusGDiHyBGMwQIxYEw"
API_URL = "https://softltd-softltd-ai.hf.space/v1/chat/completions"

app = Flask(__name__)
user_conversations = {}

def send_message(chat_id, text):
    """Отправка сообщения через Telegram API"""
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    try:
        if len(text) > 4096:
            for i in range(0, len(text), 4096):
                payload = {"chat_id": chat_id, "text": text[i:i+4096]}
                requests.post(url, json=payload, timeout=10)
        else:
            payload = {"chat_id": chat_id, "text": text}
            requests.post(url, json=payload, timeout=10)
        logger.info(f"✅ Сообщение отправлено в {chat_id}")
        return True
    except Exception as e:
        logger.error(f"❌ Ошибка отправки: {str(e)}")
        return False

@app.route('/webhook', methods=['POST'])
def webhook():
    """Обработка webhook от Telegram"""
    try:
        data = request.get_json()
        if not data:
            return jsonify({"status": "error"}), 400
        
        msg = data.get('message', {})
        if not msg:
            return jsonify({"status": "ok"}), 200
        
        chat_id = msg.get('chat', {}).get('id')
        user_id = msg.get('from', {}).get('id')
        text = msg.get('text', '')
        
        if not chat_id or not text:
            return jsonify({"status": "ok"}), 200
        
        logger.info(f"📩 Получено от {user_id}: {text[:50]}")
        
        # Обработка команд
        if text == '/start':
            send_message(chat_id, 
                "🤖 Привет! Я Qwen3.5 9B бот.\n"
                "Задайте любой вопрос!\n"
                "/clear - очистить историю\n"
                "/help - помощь"
            )
            return jsonify({"status": "ok"}), 200
        
        if text == '/help':
            send_message(chat_id,
                "📝 Просто напишите сообщение.\n"
                "/clear - очистить историю\n"
                "/start - начать сначала"
            )
            return jsonify({"status": "ok"}), 200
        
        if text == '/clear':
            user_conversations[user_id] = []
            send_message(chat_id, "🧹 История очищена!")
            return jsonify({"status": "ok"}), 200
        
        # Обычное сообщение
        if user_id not in user_conversations:
            user_conversations[user_id] = []
        
        user_conversations[user_id].append({"role": "user", "content": text})
        
        # Запрос к модели
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
                if "choices" in result and len(result["choices"]) > 0:
                    reply = result["choices"][0]["message"]["content"]
                    user_conversations[user_id].append({"role": "assistant", "content": reply})
                    send_message(chat_id, reply)
                else:
                    send_message(chat_id, "❌ Не удалось получить ответ от модели")
            else:
                send_message(chat_id, f"❌ Ошибка API: {response.status_code}")
                
        except requests.exceptions.Timeout:
            send_message(chat_id, "⏰ Модель обрабатывает запрос слишком долго. Попробуйте упростить вопрос.")
        except Exception as e:
            logger.error(f"❌ Ошибка: {str(e)}")
            send_message(chat_id, f"❌ Ошибка: {str(e)}")
        
        return jsonify({"status": "ok"}), 200
        
    except Exception as e:
        logger.error(f"❌ Webhook error: {str(e)}")
        return jsonify({"status": "error", "message": str(e)}), 500

@app.route('/health', methods=['GET'])
def health():
    """Проверка здоровья"""
    return jsonify({"status": "ok", "service": "telegram-bot"}), 200

@app.route('/', methods=['GET'])
def index():
    """Главная страница"""
    return jsonify({
        "status": "ok",
        "service": "Qwen3.5 Telegram Bot",
        "webhook_url": "https://your-service.onrender.com/webhook"
    }), 200

if __name__ == "__main__":
    logger.info("🚀 Запуск Flask сервера на порту 7860...")
    app.run(host='0.0.0.0', port=7860, debug=False)
