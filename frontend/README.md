# AInterior Frontend

React-приложение для 3D дизайна интерьеров с AI ассистентом.

## Установка

Для работы требуется Node.js версии 16 или выше.

```bash
# Установка зависимостей
npm install

# Запуск в режиме разработки
npm run dev

# Сборка для продакшена
npm run build

# Предпросмотр production build
npm run preview
```

## Структура проекта

```
frontend/
├── src/
│   ├── components/      # React компоненты
│   │   ├── Header.jsx   # Верхняя панель с вкладками проектов
│   │   ├── ChatPanel.jsx # Чат с AI ассистентом
│   │   ├── ViewerPanel.jsx # 3D viewer с Three.js
│   │   └── ScenePanel.jsx # Список объектов сцены
│   ├── context/         # React Context для управления состоянием
│   │   └── AppContext.jsx
│   ├── services/        # API сервисы
│   │   └── api.js
│   ├── styles/          # Глобальные стили
│   │   └── global.css
│   ├── App.jsx         # Главный компонент
│   └── main.jsx        # Точка входа
├── index.html
├── vite.config.js      # Конфигурация Vite
└── package.json
```

## Технологии

- **React 18** - UI библиотека
- **Three.js** - 3D рендеринг
- **Vite** - Сборщик и dev сервер
- **Context API** - Управление состоянием

## Backend

Frontend настроен на работу с backend API на `http://localhost:8001`.
Все API запросы проксируются через Vite dev server.
