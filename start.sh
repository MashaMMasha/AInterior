#!/bin/bash


if [ ! -d "venv" ]; then
    echo "Виртуальное окружение не найдено!"
    echo "Создание виртуального окружения..."
    python3 -m venv venv
    
    echo "Установка зависимостей..."
    source venv/bin/activate
    pip install -r requirements.txt
else
    echo "Виртуальное окружение найдено"
    source venv/bin/activate
fi

echo ""
echo "Запуск FastAPI сервера..."
echo ""
echo "Приложение будет доступно по адресу: http://localhost:8000"
echo "API документация: http://localhost:8000/docs"
echo ""
echo "Нажмите Ctrl+C для остановки сервера"
echo ""

uvicorn ml_api.main:app --reload --host 0.0.0.0 --port 8000

