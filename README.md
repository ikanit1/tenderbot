# TenderBot — бот подбора исполнителей под тендеры

Telegram-бот на **Aiogram 3.x** и **PostgreSQL (SQLAlchemy 2.x)** для системы тендеров: регистрация мастеров, модерация, публикация тендеров и отклики.

## Алгоритм работы

1. **Регистрация исполнителя**  
   Сбор данных: ФИО, дата рождения, город, телефон, навыки (теги), по желанию — фото/документы. Статус: `pending_moderation`.

2. **Модерация**  
   Админ получает уведомление с данными мастера и кнопками «Одобрить» / «Отклонить». После одобрения статус: `active`.

3. **Публикация тендера (админ)**  
   Команда `/add_tender`: название, тип (СКУД, АПС и т.д.), город, бюджет, описание. Система выбирает мастеров: `skill == тип тендера` и `city == город тендера`.

4. **Рассылка и отклик**  
   Подходящим мастерам приходит сообщение с кнопкой «Откликнуться». Админ видит список откликнувшихся и выбирает исполнителя.

## Структура проекта

```
handlers/     — user, admin, customer, tender
database/     — модели (User, Tender, TenderApplication, Review) и сессия БД
middlewares/  — DbSession
states/       — FSM (регистрация, создание тендера, рейтинг)
web/          — веб-админка (FastAPI, Jinja2): dashboard, users, tenders, applications, reviews
alembic/      — миграции
main.py       — точка входа бота
run_web.py    — запуск веб-админки
config.py     — pydantic-settings
```

## Установка и запуск

1. Клонировать/перейти в папку проекта, создать виртуальное окружение:

   ```bash
   python -m venv venv
   venv\Scripts\activate   # Windows
   ```

2. Установить зависимости:

   ```bash
   pip install -r requirements.txt
   ```

3. Создать БД PostgreSQL и файл `.env` (по образцу `.env.example`):

   ```
   BOT_TOKEN=токен_от_BotFather
   ADMIN_ID=ваш_telegram_id
   DATABASE_URL=postgresql+asyncpg://user:password@localhost:5432/tenderbot
   ```

4. (Опционально) Миграции Alembic:

   ```bash
   alembic revision --autogenerate -m "initial"
   alembic upgrade head
   ```

   Либо таблицы создадутся при первом запуске через `init_db()` в `main.py`.

5. Запуск бота:

   ```bash
   python main.py
   ```

### Сброс БД (разработка)

Если тестовые данные не нужны, самый быстрый способ — удалить файл БД и запустить бота заново. При использовании SQLite это файл `test.db` в корне проекта (или путь из `DATABASE_URL` в `.env`). После удаления при следующем запуске `python main.py` таблицы и миграции создадут схему с нуля.

## Команды

- **Пользователь:** `/start`, `/register` — старт и регистрация (выбор роли: исполнитель / заказчик / оба). `/profile`, `/edit_profile`, `/my_applications` — профиль и отклики исполнителя.
- **Заказчик:** `/add_tender` — создание тендера (черновик → «Опубликовать»), `/my_tenders` — список своих тендеров.
- **Админ:** модерация (Одобрить/Отклонить), `/add_tender`, `/workers`, `/tenders`, `/stats`, выбор исполнителя по отклику, закрытие/отмена тендера.

## Веб-админка

Запуск (отдельно от бота):

```bash
python run_web.py
```

Открыть в браузере: `http://localhost:8000`. Логин: `admin`, пароль задаётся в `.env` (`ADMIN_PASSWORD`). Дашборд, пользователи, тендеры, отклики, рейтинги.

## Технологии

- Python 3.10+
- Aiogram 3.x
- SQLAlchemy 2.x (async + asyncpg)
- PostgreSQL
- pydantic-settings, Alembic (опционально)

Код с комментариями на русском.
