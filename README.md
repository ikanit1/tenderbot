# TenderBot — Система управления тендерами

Telegram-бот и веб-админка для управления тендерами, исполнителями и заказчиками.

## Быстрый старт

### 1. Установка зависимостей

```bash
pip install -r requirements.txt
```

### 2. Настройка

Создайте файл `.env` в корне проекта:

```env
BOT_TOKEN=ваш_токен_от_BotFather
ADMIN_ID=ваш_telegram_id
DATABASE_URL=sqlite+aiosqlite:///./test.db
WEB_SECRET_KEY=секретный_ключ_для_сессий
ADMIN_PASSWORD=пароль_для_веб_админки
WEB_HOST=0.0.0.0
WEB_PORT=8000
```

### 3. Запуск

**Единый запуск (бот + веб-интерфейс):**
```bash
python run.py
```

**Только бот:**
```bash
python run.py --bot-only
```

**Только веб-интерфейс:**
```bash
python run.py --web-only
```

**Альтернативные способы запуска:**

- Только бот: `python main.py`
- Только веб: `python run_web.py` или `uvicorn web.main:app --host 0.0.0.0 --port 8000`

## Функционал

### Telegram бот

- Регистрация пользователей (исполнители, заказчики)
- Создание и управление тендерами
- Отклики на тендеры
- Модерация пользователей
- Рейтинги и отзывы

### Веб-админка

Доступна по адресу: `http://localhost:8000`

- **Дашборд**: статистика и последние записи
- **Пользователи**: просмотр, модерация, блокировка
- **Тендеры**: создание, редактирование, управление статусами
- **Отклики**: выбор исполнителя, отклонение откликов
- **Рейтинги**: просмотр отзывов

**Логин**: `admin`  
**Пароль**: указан в `.env` (по умолчанию `admin`)

## Структура проекта

```
tenderbot/
├── main.py              # Точка входа бота
├── run.py               # Единый запуск бота и веб-интерфейса
├── run_web.py           # Запуск только веб-интерфейса
├── config.py            # Настройки приложения
├── requirements.txt     # Зависимости
├── database/
│   ├── models.py        # SQLAlchemy модели
│   └── session.py       # Управление сессиями БД
├── handlers/            # Обработчики команд бота
│   ├── user.py          # Регистрация, профиль
│   ├── admin.py         # Админ-функции
│   ├── customer.py      # Функции заказчика
│   ├── tender.py        # Отклики на тендеры
│   └── keyboards.py     # Клавиатуры
├── middlewares/         # Middleware для бота
│   ├── db.py            # Сессии БД
│   └── fsm_cancel.py    # Отмена FSM при нажатии меню
├── states/              # FSM состояния
├── web/                 # Веб-админка
│   ├── main.py          # FastAPI приложение
│   ├── routes/          # Роуты веб-интерфейса
│   └── templates/       # HTML шаблоны
└── alembic/             # Миграции БД
```

## Команды бота

- `/start` — Главное меню
- `/register` — Регистрация
- `/profile` — Профиль
- `/my_applications` — Мои отклики (для исполнителей)
- `/my_tenders` — Мои тендеры (для заказчиков)
- `/add_tender` — Создать тендер
- `/help` — Справка

## Миграции БД

Миграции выполняются автоматически при запуске бота.

Для ручного запуска:
```bash
alembic upgrade head
```

## Деплой на сервер

После заливки файлов на сервер:

1. **Python 3.11+** и виртуальное окружение:
   ```bash
   python3 -m venv .venv
   source .venv/bin/activate   # Linux/macOS
   pip install -r requirements.txt
   ```

2. **Файл `.env`** в корне проекта (скопировать из `.env.example` и заполнить):
   ```env
   BOT_TOKEN=токен_от_BotFather
   ADMIN_ID=ваш_telegram_id
   DATABASE_URL=postgresql+asyncpg://user:password@host:5432/tenderbot
   WEB_SECRET_KEY=длинная_случайная_строка
   ADMIN_PASSWORD=надёжный_пароль
   WEB_HOST=0.0.0.0
   WEB_PORT=8000
   ```
   Для SQLite: `DATABASE_URL=sqlite+aiosqlite:///./data.db`

3. **Миграции** (выполняются при первом запуске бота, или вручную):
   ```bash
   alembic upgrade head
   ```

4. **Запуск** (все в одном процессе):
   ```bash
   python run.py
   ```
   Или раздельно в screen/tmux/systemd:
   - `python run.py --bot-only`
   - `python run.py --web-only` (веб на порту из `WEB_PORT`)

5. **Только веб с несколькими воркерами** (production):
   ```bash
   uvicorn web.main:app --host 0.0.0.0 --port 8000 --workers 2
   ```

Убедитесь, что на сервере открыт порт из `WEB_PORT` (по умолчанию 8000) и что PostgreSQL доступен по `DATABASE_URL`. Все команды выполняйте из **корня проекта** (где лежат `run.py` и `.env`).

---

## Разработка

### Добавление новой миграции

```bash
alembic revision --autogenerate -m "описание изменений"
alembic upgrade head
```

### Запуск в режиме разработки

Веб-интерфейс с автоперезагрузкой:
```bash
uvicorn web.main:app --reload --host 0.0.0.0 --port 8000
```

## Лицензия

MIT
