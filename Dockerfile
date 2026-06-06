# Используем официальный образ Playwright с Python 3.11 (на нём сборка гарантированно работает)
FROM mcr.microsoft.com/playwright/python:v1.46.0-jammy

# Устанавливаем зависимости Python
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Копируем всё приложение
COPY . .

# Запускаем сервер
CMD ["uvicorn", "app:app", "--host", "0.0.0.0", "--port", "10000"]