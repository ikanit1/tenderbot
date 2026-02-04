# main.py — точка входа: запуск бота и инициализация БД
import asyncio
import logging
from pathlib import Path

# Сначала импортируем только config для миграций
from config import settings

# Выполняем миграции ДО импорта модулей, которые могут создать async engine
def _run_migrations() -> None:
    """Запуск миграций Alembic до head (синхронно, ДО создания async engine)."""
    from alembic.config import Config
    from alembic import command
    root = Path(__file__).resolve().parent
    alembic_cfg = Config(str(root / "alembic.ini"))
    command.upgrade(alembic_cfg, "head")

# Выполняем миграции сразу при импорте модуля (до создания async engine)
_run_migrations()

# Теперь безопасно импортируем остальные модули
from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode

from aiogram.utils.token import TokenValidationError

from handlers import router
from middlewares.db import DbSessionMiddleware
from middlewares.fsm_cancel import FSMCancelMiddleware
from utils.ui_manager import FSMDeleteUserMessageMiddleware

# Логирование
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)


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
    # Миграции уже выполнены при импорте модуля
    # Импортируем init_db (engine создастся только при первом использовании благодаря ленивой инициализации)
    from database.session import init_db
    # Создание таблиц через init_db (если миграции не создали все)
    await init_db()
    logger.info("База данных инициализирована.")

    bot = Bot(
    token=settings.BOT_TOKEN,
    default=DefaultBotProperties(parse_mode=ParseMode.HTML),
)
    dp = Dispatcher()
    # Middleware для отмены FSM при нажатии кнопок меню (должен быть ПЕРЕД DbSessionMiddleware)
    dp.message.middleware(FSMCancelMiddleware())
    dp.callback_query.middleware(FSMCancelMiddleware())
    dp.message.middleware(DbSessionMiddleware())
    dp.message.middleware(FSMDeleteUserMessageMiddleware())
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
