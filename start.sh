#!/bin/bash

GREEN='\033[0;32m'
BLUE='\033[0;34m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m'

echo -e "${BLUE}=================================${NC}"
echo -e "${BLUE}  AInterior - Backend Services${NC}"
echo -e "${BLUE}=================================${NC}\n"

export PATH="/opt/homebrew/bin:/usr/local/bin:$PATH"

if [ ! -f .env ]; then
    echo -e "${YELLOW}Файл .env не найден, создаю из .env.example...${NC}"
    cp .env.example .env
    echo -e "${GREEN}.env создан — отредактируй SMTP_USER и SMTP_PASSWORD для отправки почты${NC}\n"
fi

if command -v docker &> /dev/null && docker compose version &> /dev/null 2>&1; then
    if [ -S "$HOME/.colima/default/docker.sock" ]; then
        export DOCKER_HOST="unix://$HOME/.colima/default/docker.sock"
    fi

    echo -e "${BLUE}Запускаю PostgreSQL и MinIO...${NC}"
    docker compose up -d postgres minio minio-init 2>/dev/null

    echo -e "${YELLOW}Ожидаю готовности PostgreSQL...${NC}"
    for i in {1..30}; do
        if docker compose exec -T postgres pg_isready -U user -d ainterior &> /dev/null; then
            echo -e "${GREEN}PostgreSQL готов${NC}\n"
            break
        fi
        sleep 1
        if [ $i -eq 30 ]; then
            echo -e "${RED}PostgreSQL не ответил за 30 секунд${NC}\n"
        fi
    done
else
    echo -e "${YELLOW}Docker не найден — PostgreSQL и MinIO нужно запустить вручную${NC}\n"
fi

if [ ! -d "venv" ]; then
    echo -e "${YELLOW}Создание виртуального окружения...${NC}"
    python3 -m venv venv
    source venv/bin/activate
    echo -e "${BLUE}Установка зависимостей...${NC}"
    pip install -r requirements.txt
else
    echo -e "${GREEN}Виртуальное окружение найдено${NC}"
    source venv/bin/activate
    pip install -r requirements.txt --quiet
fi

echo ""
echo -e "${BLUE}Запуск Auth Service (порт 8001)...${NC}"
uvicorn auth_service.main:app --reload --host 0.0.0.0 --port 8001 &
AUTH_PID=$!

sleep 2
echo -e "${BLUE}Запуск ML Service (порт 8002)...${NC}"
uvicorn ml_service.main:app --reload --host 0.0.0.0 --port 8002 &
ML_PID=$!

sleep 2
echo -e "${BLUE}Запуск Backend Service (порт 8000)...${NC}\n"
uvicorn backend_service.main:app --reload --host 0.0.0.0 --port 8000 &
BACKEND_PID=$!

sleep 2
echo ""
echo -e "${GREEN}=================================${NC}"
echo -e "${GREEN}  Backend Services запущены${NC}"
echo -e "${GREEN}=================================${NC}"
echo ""
echo -e "  ${GREEN}Backend Service:${NC}   http://localhost:8000/docs"
echo -e "  ${GREEN}Auth Service:${NC}      http://localhost:8001/docs"
echo -e "  ${GREEN}ML Service:${NC}        http://localhost:8002/docs"
echo ""
echo -e "${YELLOW}Ctrl+C для остановки${NC}"
echo ""

cleanup() {
    echo -e "\n${YELLOW}Остановка сервисов...${NC}"
    kill $AUTH_PID $ML_PID $BACKEND_PID 2>/dev/null
    echo -e "${GREEN}Сервисы остановлены${NC}"
    exit 0
}

trap cleanup SIGINT SIGTERM

wait
