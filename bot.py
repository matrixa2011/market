import requests
import logging
import time
import threading
import json
from http.server import HTTPServer, BaseHTTPRequestHandler

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

TELEGRAM_TOKEN = "8715390060:AAHT0IeCllzTJXgY4CusGDiHyBGMwQIxYEw"
API_URL = "https://softltd-softltd-ai.hf.space/v1/chat/completions"

user_conversations = {}

def send_message(chat_id, text):
    """Отправка сообщения через Telegram API"""
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    try:
        if len(text) > 4096:
            for i in range(0, len(text), 4096):
                payload = {"chat_id": chat_id, "text": text[i:i+4096]}
                response = requests.post(url, json=payload, timeout=30)
                logger.info(f"Ответ Telegram: {response.status_code}")
        else:
            payload = {"chat_id": chat_id, "text": text}
            response = requests.post(url, json=payload, timeout=30)
            logger.info(f"Ответ Telegram: {response.status_code} - {response.text[:100]}")
        
        if response.status_code == 200:
            logger.info(f"✅ Сообщение отправлено в {chat_id}")
            return True
        else:
            logger.error(f"❌ Ошибка отправки: {response.status_code} - {response.text}")
            return False
    except Exception as e:
        logger.error(f"❌ Ошибка отправки: {str(e)}")
        return False

def process_update(update):
    """Обработка одного обновления от Telegram"""
    try:
        msg = update.get('message', {})
        if not msg:
            return
        
        chat_id = msg.get('chat', {}).get('id')
        user_id = msg.get('from', {}).get('id')
        text = msg.get('text', '')
        
        if not chat_id or not text:
            return
        
        logger.info(f"📩 Получено от {user_id}: {text[:50]}")
        
        # Обработка команд
        if text == '/start':
            send_message(chat_id, 
                "🤖 Привет! Я Qwen3.5 9B бот.\n"
                "Задайте любой вопрос!\n"
                "/clear - очистить историю\n"
                "/help - помощь"
            )
            return
        
        if text == '/help':
            send_message(chat_id,
                "📝 Просто напишите сообщение.\n"
                "/clear - очистить историю\n"
                "/start - начать сначала"
            )
            return
        
        if text == '/clear':
            user_conversations[user_id] = []
            send_message(chat_id, "🧹 История очищена!")
            return
        
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
            
            logger.info(f"Отправка запроса к модели: {API_URL}")
            response = requests.post(API_URL, json=payload, timeout=180)
            logger.info(f"Ответ от модели: {response.status_code}")
            
            if response.status_code == 200:
                result = response.json()
                logger.info(f"Результат: {str(result)[:200]}...")
                
                if "choices" in result and len(result["choices"]) > 0:
                    reply = result["choices"][0]["message"]["content"]
                    logger.info(f"Ответ модели: {reply[:100]}...")
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
            
    except Exception as e:
        logger.error(f"❌ Ошибка обработки: {str(e)}")

def polling_loop():
    """Основной цикл polling"""
    offset = 0
    while True:
        try:
            url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/getUpdates"
            params = {"offset": offset, "timeout": 30}
            response = requests.get(url, params=params, timeout=35)
            
            if response.status_code == 200:
                data = response.json()
                if data.get('ok') and data.get('result'):
                    for update in data['result']:
                        process_update(update)
                        offset = update['update_id'] + 1
            else:
                logger.error(f"Ошибка получения обновлений: {response.status_code}")
                
        except Exception as e:
            logger.error(f"Ошибка в polling: {str(e)}")
        
        time.sleep(1)

class HealthHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        if self.path == '/health' or self.path == '/':
            self.send_response(200)
            self.send_header('Content-Type', 'application/json')
            self.end_headers()
            self.wfile.write(b'{"status":"ok","service":"telegram-bot","mode":"polling"}')
        else:
            self.send_response(404)
            self.end_headers()
    
    def log_message(self, format, *args):
        pass

def run_health_server():
    server_address = ('0.0.0.0', 7860)
    httpd = HTTPServer(server_address, HealthHandler)
    httpd.serve_forever()

if __name__ == "__main__":
    # Запускаем health-сервер в отдельном потоке
    health_thread = threading.Thread(target=run_health_server, daemon=True)
    health_thread.start()
    
    # Проверяем доступность API
    try:
        response = requests.get("https://softltd-softltd-ai.hf.space/health", timeout=10)
        logger.info(f"API Space доступен: {response.status_code}")
    except Exception as e:
        logger.error(f"API Space недоступен: {str(e)}")
    
    # Удаляем старый webhook
    try:
        url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/deleteWebhook"
        response = requests.get(url, timeout=10)
        logger.info(f"Webhook удален: {response.status_code}")
    except Exception as e:
        logger.error(f"Ошибка удаления webhook: {str(e)}")
    
    # Запускаем polling
    logger.info("🔄 Запуск polling...")
    polling_loop()
