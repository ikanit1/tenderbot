# main.py — точка входа: запуск бота и инициализация БД
import asyncio
import logging
from pathlib import Path

from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode

from aiogram.utils.token import TokenValidationError

from config import settings
from database.session import init_db
from handlers import router
from middlewares.db import DbSessionMiddleware

# Логирование
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)


def _run_migrations() -> None:
    """Запуск миграций Alembic до head (синхронно при старте)."""
    from alembic.config import Config
    from alembic import command
    root = Path(__file__).resolve().parent
    # Путь к alembic.ini и script_location = alembic (относительно корня проекта)
    alembic_cfg = Config(str(root / "alembic.ini"))
    command.upgrade(alembic_cfg, "head")


def _check_token() -> None:
    """Проверка токена перед запуском: не заглушка и формат числа:строка."""
    t = (settings.BOT_TOKEN or "").strip()
    if not t or "ЗАМЕНИТЕ" in t or "токен" in t.lower() or "token" in t.lower():
        raise SystemExit(
            "В файле .env указан неверный BOT_TOKEN.\n"
            "Получите токен у @BotFather и впишите в .env: BOT_TOKEN=ваш_токен"
        )
    if ":" not in t or len(t) < 20:
        raise SystemExit(
            "BOT_TOKEN в .env не похож на токен Telegram (формат: 123456789:ABC...).\n"
            "Проверьте .env или получите новый токен в @BotFather (/newbot или /revoke)."
        )


async def main() -> None:
    _check_token()
    # Создание таблиц при старте (для новой БД)
    await init_db()
    # Приведение схемы к актуальной (колонка role и др.)
    _run_migrations()
    logger.info("База данных инициализирована.")

    bot = Bot(
    token=settings.BOT_TOKEN,
    default=DefaultBotProperties(parse_mode=ParseMode.HTML),
)
    dp = Dispatcher()
    dp.message.middleware(DbSessionMiddleware())
    dp.callback_query.middleware(DbSessionMiddleware())
    dp.include_router(router)

    await dp.start_polling(bot)


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except TokenValidationError:
        raise SystemExit(
            "Токен бота недействителен.\n"
            "Откройте .env и укажите правильный BOT_TOKEN от @BotFather.\n"
            "Если токен был в чате — зайдите в @BotFather, нажмите /revoke и вставьте новый токен в .env."
        )
