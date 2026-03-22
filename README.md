# AInterior

Веб-приложение для проектирования и визуализации интерьерных решений с AI-ассистентом.

## Запуск

### Полный запуск (backend + frontend + инфраструктура)

```bash
./start-all.sh
```

### Только backend

```bash
./start.sh
```

**Требования:** Python 3.11+, Node.js 18+, Docker.

После первого запуска отредактируй `SMTP_USER` и `SMTP_PASSWORD` в `.env` для отправки кодов подтверждения email.

## Архитектура

```
Frontend (React + Three.js)  →  Backend (FastAPI)  →  PostgreSQL
                                       ↓
                                  ML Service (агенты)
                                       ↓
                                  MinIO / S3
```

**Backend (FastAPI, порт 8001)** — авторизация (JWT), проекты, загрузка/генерация 3D-моделей, интеграция с S3.

**Frontend (React + Vite, порт 3000)** — интерактивный 3D-редактор с чатом, панелью объектов и управлением проектами.

**Инфраструктура (Docker Compose):** PostgreSQL, MinIO (S3), Redis.

## Структура проекта

```
AInterior/
├── ml_api/
│   ├── agents/          # AI-агенты (парсинг, генерация, планировка)
│   ├── db/              # Каталог мебели
│   ├── models/          # SQLAlchemy модели (User, VerificationCode)
│   ├── routers/         # Роутеры (auth)
│   ├── schema/          # Pydantic DTO
│   ├── services/        # Сервисы (auth, email, s3, agents)
│   ├── config.py        # Конфигурация
│   ├── database.py      # Подключение к БД
│   ├── dependencies.py  # FastAPI зависимости
│   └── main.py          # Точка входа
├── frontend/
│   └── src/
│       ├── components/  # React-компоненты
│       ├── context/     # AuthContext, AppContext
│       ├── pages/       # Login, Register, VerifyEmail
│       ├── services/    # API-клиент
│       └── styles/      # CSS
├── database/
│   └── init.sql         # Схема БД
├── docker-compose.yml
├── Dockerfile.ml
├── requirements.txt
├── start.sh             # Запуск backend
├── start-all.sh         # Запуск всего
├── .env.example
└── .gitignore
```

## API

**Авторизация:**
- `POST /auth/register` — регистрация
- `POST /auth/verify-email` — подтверждение email
- `POST /auth/login` — вход
- `POST /auth/refresh` — обновление токена
- `GET /auth/me` — текущий пользователь

**Модели:**
- `POST /upload_model` — загрузка 3D-модели
- `POST /generate_furniture` — генерация мебели из текста
- `POST /auto_arrange` — автоматическая расстановка
- `GET /list_models` — список моделей

**Проекты:**
- `GET /projects` — список проектов
- `POST /projects` — создать проект
- `PUT /projects/{id}` — обновить
- `DELETE /projects/{id}` — удалить

Swagger UI: http://localhost:8001/docs

## Технологии

**Backend:** FastAPI, SQLAlchemy (async), PyTorch, Trimesh, Boto3, python-jose (JWT), bcrypt, aiosmtplib

**Frontend:** React 18, Three.js, Vite, React Router

**Инфраструктура:** Docker Compose, PostgreSQL, MinIO, Redis
