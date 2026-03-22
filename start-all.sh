#!/bin/bash

GREEN='\033[0;32m'
BLUE='\033[0;34m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m'

echo -e "${BLUE}=================================${NC}"
echo -e "${BLUE}  AInterior - Полный запуск${NC}"
echo -e "${BLUE}  Backend + Frontend + DB${NC}"
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

    echo -e "${BLUE}Запускаю инфраструктуру (PostgreSQL, MinIO, Redis)...${NC}"
    docker compose up -d postgres minio minio-init redis 2>/dev/null

    echo -e "${YELLOW}Ожидаю готовности PostgreSQL...${NC}"
    for i in {1..30}; do
        if docker compose exec -T postgres pg_isready -U user -d ainterior &> /dev/null; then
            echo -e "${GREEN}PostgreSQL готов${NC}\n"
            break
        fi
        sleep 1
        if [ $i -eq 30 ]; then
            echo -e "${RED}PostgreSQL не ответил за 30 секунд, проверь docker compose logs postgres${NC}\n"
        fi
    done
else
    echo -e "${RED}Docker не найден!${NC}"
    echo -e "${YELLOW}PostgreSQL, MinIO и Redis нужно запустить вручную.${NC}"
    echo -e "Установи Docker: https://docs.docker.com/get-docker/\n"
fi

if [ ! -d "venv" ]; then
    echo -e "${YELLOW}Виртуальное окружение не найдено. Создание...${NC}"
    python3 -m venv venv
    source venv/bin/activate
    echo -e "${BLUE}Установка Python-зависимостей...${NC}"
    pip install -r requirements.txt
else
    echo -e "${GREEN}Виртуальное окружение найдено${NC}"
    source venv/bin/activate
    pip install -r requirements.txt --quiet
fi

if [ ! -d "frontend/node_modules" ]; then
    echo -e "${YELLOW}Зависимости фронтенда не установлены. Установка...${NC}"
    cd frontend
    npm install
    cd ..
else
    echo -e "${GREEN}Зависимости фронтенда установлены${NC}"
fi

echo ""
echo -e "${BLUE}Запуск Backend (FastAPI)...${NC}"
uvicorn ml_api.main:app --reload --host 0.0.0.0 --port 8001 &
BACKEND_PID=$!

sleep 3
echo -e "${BLUE}Запуск Frontend (React + Vite)...${NC}\n"
cd frontend
npm run dev &
FRONTEND_PID=$!
cd ..

sleep 2
echo -e "\n${GREEN}=================================${NC}"
echo -e "${GREEN}  AInterior запущен${NC}"
echo -e "${GREEN}=================================${NC}\n"

echo -e "  ${GREEN}Frontend:${NC}       http://localhost:3000"
echo -e "  ${GREEN}Backend API:${NC}    http://localhost:8001"
echo -e "  ${GREEN}API Docs:${NC}       http://localhost:8001/docs"
echo -e "  ${GREEN}Health:${NC}         http://localhost:8001/health\n"

echo -e "${BLUE}Авторизация:${NC}"
echo -e "  POST /auth/register     — регистрация"
echo -e "  POST /auth/verify-email — подтверждение email"
echo -e "  POST /auth/login        — вход"
echo -e "  POST /auth/refresh      — обновление токена"
echo -e "  GET  /auth/me           — текущий пользователь\n"

echo -e "${BLUE}Инфраструктура:${NC}"
echo -e "  ${GREEN}PostgreSQL:${NC}     localhost:5432  (user/password/ainterior)"
echo -e "  ${GREEN}MinIO Console:${NC}  http://localhost:9001  (minioadmin/minioadmin)"
echo -e "  ${GREEN}Redis:${NC}          localhost:6379\n"

echo -e "${YELLOW}SMTP: Для отправки кодов подтверждения настрой SMTP_USER и SMTP_PASSWORD в .env${NC}\n"
echo -e "${YELLOW}Ctrl+C для остановки${NC}\n"

cleanup() {
    echo -e "\n${YELLOW}Остановка приложения...${NC}"
    kill $BACKEND_PID $FRONTEND_PID 2>/dev/null
    exit 0
}

trap cleanup SIGINT SIGTERM

wait
