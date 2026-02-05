# middlewares/db.py — внедрение сессии БД в хендлеры
import time
import logging
from typing import Any, Awaitable, Callable, Dict

from aiogram import BaseMiddleware
from aiogram.types import TelegramObject, Message, CallbackQuery
from sqlalchemy.ext.asyncio import AsyncSession

from database.session import get_async_session_maker
from utils.logging_config import set_log_context, clear_log_context

logger = logging.getLogger(__name__)


class DbSessionMiddleware(BaseMiddleware):
    """Подставляет async-сессию БД в handler.data['session']."""

    async def __call__(
        self,
        handler: Callable[[TelegramObject, Dict[str, Any]], Awaitable[Any]],
        event: TelegramObject,
        data: Dict[str, Any],
    ) -> Any:
        # Устанавливаем контекст логирования
        user_id = None
        action = None
        
        if isinstance(event, Message):
            user_id = event.from_user.id if event.from_user else None
            action = event.text or "message"
        elif isinstance(event, CallbackQuery):
            user_id = event.from_user.id if event.from_user else None
            action = event.data or "callback"
        
        if user_id:
            set_log_context(user_id=user_id, action=action)
        
        start_time = time.time()
        async_session_maker = get_async_session_maker()
        async with async_session_maker() as session:
            data["session"] = session
            try:
                result = await handler(event, data)
                await session.commit()
                
                # Логируем время выполнения
                duration = time.time() - start_time
                if duration > 1.0:  # Логируем только медленные запросы
                    logger.warning(f"Slow handler execution: {duration:.2f}s for action '{action}'")
                
                return result
            except Exception:
                await session.rollback()
                raise
            finally:
                await session.close()
                clear_log_context()
