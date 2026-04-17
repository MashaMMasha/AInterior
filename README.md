# AInterior

Веб-приложение для проектирования и визуализации интерьерных решений с AI-ассистентом.

## Запуск

### Полный запуск (backend + frontend + инфраструктура)

```bash
./start-all.sh
```

### Только backend

```bash
docker-compose up -d
```

**Требования:** Python 3.11+, Node.js 18+, Docker.

После первого запуска отредактируй `SMTP_USER` и `SMTP_PASSWORD` в `.env` для отправки кодов подтверждения email.

## Архитектура

```
Frontend (React + Three.js)
         ↓
Backend Service (FastAPI, :8000)  ←→  Auth Service (FastAPI, :8001)
         ↓                                       ↓
    ML Service (FastAPI, :8002)            PostgreSQL
         ↓
    MinIO / S3
```

### Сервисы

**Auth Service (порт 8001)** — изолированный сервис авторизации:
- Регистрация и вход (JWT)
- Подтверждение email
- Управление пользователями и сессиями

**Backend Service (порт 8000)** — основной API-шлюз:
- Управление проектами (CRUD) — требует авторизации
- Загрузка 3D-моделей — требует авторизации
- Интеграция с S3 для хранения файлов
- Проксирование запросов к ML Service — требует авторизации

**ML Service (порт 8002)** — изолированный ML-сервис:
- AI-агенты (парсинг запросов, генерация, планировка) — требует авторизации
- Генерация 3D-моделей из текста — требует авторизации
- Автоматическая расстановка мебели — требует авторизации

**Frontend (React + Vite, порт 3000)** — интерактивный 3D-редактор с чатом, панелью объектов и управлением проектами.

**Инфраструктура (Docker Compose):** PostgreSQL, MinIO (S3), Redis, RabbitMQ.

## Структура проекта

```
AInterior/
├── auth-service/          # Сервис авторизации
│   ├── models/           # SQLAlchemy модели (User, VerificationCode)
│   ├── routers/          # Auth endpoints
│   ├── services/         # Auth logic, email
│   ├── config.py         # Настройки auth-service
│   ├── database.py       # Подключение к БД
│   ├── dependencies.py   # FastAPI dependencies
│   └── main.py           # Точка входа
├── backend-service/       # Основной API-шлюз
│   ├── routers/          # Projects, models, ML proxy
│   ├── services/         # S3, auth-client, ml-client
│   ├── schema/           # Pydantic DTO
│   ├── config.py         # Настройки backend-service
│   ├── dependencies.py   # Auth middleware
│   └── main.py           # Точка входа
├── ml-service/            # ML сервис
│   ├── agents/           # AI-агенты (парсинг, генерация, планировка)
│   ├── db/               # Каталог мебели
│   ├── schema/           # Pydantic DTO
│   ├── services/         # ML logic, S3, auth-client
│   ├── config.py         # Настройки ml-service
│   ├── dependencies.py   # Auth middleware
│   ├── database.py       # Подключение к БД
│   └── main.py           # Точка входа
├── frontend/
│   └── src/
│       ├── components/   # React-компоненты
│       ├── context/      # AuthContext, AppContext
│       ├── pages/        # Login, Register, VerifyEmail
│       ├── services/     # API-клиент
│       └── styles/       # CSS
├── database/
│   └── init.sql          # Схема БД
├── docker-compose.yml     # Оркестрация всех сервисов
├── Dockerfile.auth        # Auth Service image
├── Dockerfile.backend     # Backend Service image
├── Dockerfile.ml          # ML Service image
├── requirements.txt
├── start.sh              # Запуск backend-сервисов
├── start-all.sh          # Запуск всего стека
├── .env.example
└── .gitignore
```

## API

### Auth Service (:8001)

**Авторизация:**
- `POST /auth/register` — регистрация
- `POST /auth/verify-email` — подтверждение email
- `POST /auth/login` — вход
- `POST /auth/refresh` — обновление токена
- `GET /auth/me` — текущий пользователь
- `POST /auth/verify-token` — проверка токена

### Backend Service (:8000)

**Все эндпоинты требуют JWT токен в заголовке `Authorization: Bearer <token>`**

**Модели:**
- `POST /upload_model` — загрузка 3D-модели
- `GET /list_models` — список моделей
- `GET /uploaded_models/{filename}` — скачать модель
- `GET /generated_models/{filename}` — скачать сгенерированную модель

**Проекты:**
- `GET /projects` — список проектов пользователя
- `POST /projects` — создать проект
- `PUT /projects/{id}` — обновить
- `DELETE /projects/{id}` — удалить

**ML Proxy:**
- `POST /generate` — генерация из текста
- `POST /generate_furniture` — генерация мебели
- `POST /auto_arrange` — автоматическая расстановка
- `POST /chat` — чат с ассистентом
- `POST /generate_scene` — генерация сцены
- `GET /generation/{generation_id}` — статус генерации

**WebSocket:**
- `WS /ws/generation/{generation_id}?token=<jwt>` — стрим прогресса генерации

### ML Service (:8002)

**Все эндпоинты требуют JWT токен в заголовке `Authorization: Bearer <token>`**

**ML Операции:**
- `POST /generate` — генерация модели
- `POST /generate_furniture` — генерация мебели из текста
- `POST /auto_arrange` — автоматическая расстановка
- `POST /chat` — парсинг запроса
- `POST /generate_scene` — генерация сцены (streaming)
- `GET /generation/{generation_id}` — статус генерации
- `GET /health` — проверка здоровья сервиса (публичный)

Swagger UI:
- Auth: http://localhost:8001/docs
- Backend: http://localhost:8000/docs  
- ML: http://localhost:8002/docs

## Технологии

**Backend:** FastAPI, SQLAlchemy (async), PyTorch, Trimesh, Boto3, python-jose (JWT), bcrypt, aiosmtplib, httpx

**Frontend:** React 18, Three.js, Vite, React Router

**Инфраструктура:** Docker Compose, PostgreSQL, MinIO, Redis, RabbitMQ