import requests
import logging
from http.server import HTTPServer, BaseHTTPRequestHandler
import json

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
                requests.post(url, json=payload, timeout=10)
        else:
            payload = {"chat_id": chat_id, "text": text}
            requests.post(url, json=payload, timeout=10)
        logger.info(f"✅ Сообщение отправлено в {chat_id}")
        return True
    except Exception as e:
        logger.error(f"❌ Ошибка отправки: {str(e)}")
        return False

class WebhookHandler(BaseHTTPRequestHandler):
    def do_POST(self):
        """Обработка POST запросов (webhook)"""
        if self.path == '/webhook':
            try:
                content_length = int(self.headers['Content-Length'])
                post_data = self.rfile.read(content_length)
                data = json.loads(post_data.decode('utf-8'))
                
                msg = data.get('message', {})
                if not msg:
                    self.send_response(200)
                    self.end_headers()
                    self.wfile.write(b'{"status":"ok"}')
                    return
                
                chat_id = msg.get('chat', {}).get('id')
                user_id = msg.get('from', {}).get('id')
                text = msg.get('text', '')
                
                if not chat_id or not text:
                    self.send_response(200)
                    self.end_headers()
                    self.wfile.write(b'{"status":"ok"}')
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
                    self.send_response(200)
                    self.end_headers()
                    self.wfile.write(b'{"status":"ok"}')
                    return
                
                if text == '/help':
                    send_message(chat_id,
                        "📝 Просто напишите сообщение.\n"
                        "/clear - очистить историю\n"
                        "/start - начать сначала"
                    )
                    self.send_response(200)
                    self.end_headers()
                    self.wfile.write(b'{"status":"ok"}')
                    return
                
                if text == '/clear':
                    user_conversations[user_id] = []
                    send_message(chat_id, "🧹 История очищена!")
                    self.send_response(200)
                    self.end_headers()
                    self.wfile.write(b'{"status":"ok"}')
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
                
                self.send_response(200)
                self.end_headers()
                self.wfile.write(b'{"status":"ok"}')
                
            except Exception as e:
                logger.error(f"❌ Webhook error: {str(e)}")
                self.send_response(500)
                self.end_headers()
                self.wfile.write(f'{{"status":"error","message":"{str(e)}"}}'.encode('utf-8'))
        else:
            self.send_response(404)
            self.end_headers()

    def do_GET(self):
        """Обработка GET запросов (health check)"""
        if self.path == '/health' or self.path == '/':
            self.send_response(200)
            self.send_header('Content-Type', 'application/json')
            self.end_headers()
            self.wfile.write(b'{"status":"ok","service":"telegram-bot"}')
        else:
            self.send_response(404)
            self.end_headers()

def run_server():
    logger.info("🚀 Запуск HTTP сервера на порту 7860...")
    server_address = ('0.0.0.0', 7860)
    httpd = HTTPServer(server_address, WebhookHandler)
    logger.info("✅ Сервер запущен. Ожидание webhook...")
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        logger.info("⏹️ Сервер остановлен")

if __name__ == "__main__":
    run_server()
