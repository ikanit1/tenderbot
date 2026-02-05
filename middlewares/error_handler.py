# middlewares/error_handler.py — централизованная обработка ошибок
import logging
import traceback
from typing import Any, Awaitable, Callable, Dict

from aiogram import BaseMiddleware
from aiogram.types import TelegramObject, Message, CallbackQuery, ErrorEvent
from aiogram.exceptions import (
    TelegramBadRequest,
    TelegramNetworkError,
    TelegramAPIError,
    TelegramRetryAfter,
)
from sqlalchemy.exc import SQLAlchemyError

logger = logging.getLogger(__name__)


class ErrorHandlerMiddleware(BaseMiddleware):
    """Middleware для централизованной обработки ошибок."""
    
    async def __call__(
        self,
        handler: Callable[[TelegramObject, Dict[str, Any]], Awaitable[Any]],
        event: TelegramObject,
        data: Dict[str, Any],
    ) -> Any:
        try:
            return await handler(event, data)
        except TelegramRetryAfter as e:
            # Обработка rate limit от Telegram
            logger.warning(f"Telegram rate limit: retry after {e.retry_after} seconds")
            if isinstance(event, (Message, CallbackQuery)):
                try:
                    if isinstance(event, CallbackQuery):
                        await event.answer(
                            f"⏳ Превышен лимит запросов. Попробуйте через {e.retry_after} секунд.",
                            show_alert=True,
                        )
                    else:
                        await event.answer(
                            f"⏳ Превышен лимит запросов. Попробуйте через {e.retry_after} секунд."
                        )
                except Exception:
                    pass
            return None
        except TelegramBadRequest as e:
            # Обработка некорректных запросов к Telegram API
            logger.error(f"Telegram BadRequest: {e}")
            if isinstance(event, CallbackQuery):
                try:
                    await event.answer("❌ Ошибка обработки запроса.", show_alert=True)
                except Exception:
                    pass
            return None
        except TelegramNetworkError as e:
            # Обработка сетевых ошибок
            logger.error(f"Telegram NetworkError: {e}")
            if isinstance(event, CallbackQuery):
                try:
                    await event.answer("⚠️ Проблемы с сетью. Попробуйте позже.", show_alert=True)
                except Exception:
                    pass
            return None
        except TelegramAPIError as e:
            # Обработка других ошибок Telegram API
            logger.error(f"Telegram API Error: {e}")
            if isinstance(event, CallbackQuery):
                try:
                    await event.answer("❌ Ошибка при обращении к Telegram API.", show_alert=True)
                except Exception:
                    pass
            return None
        except SQLAlchemyError as e:
            # Обработка ошибок БД
            logger.error(f"Database error: {e}", exc_info=True)
            if isinstance(event, CallbackQuery):
                try:
                    await event.answer("❌ Ошибка базы данных. Попробуйте позже.", show_alert=True)
                except Exception:
                    pass
            # Rollback уже выполнен в DbSessionMiddleware
            return None
        except Exception as e:
            # Обработка всех остальных ошибок
            logger.error(
                f"Unexpected error in handler: {e}\n{traceback.format_exc()}",
                exc_info=True,
            )
            if isinstance(event, CallbackQuery):
                try:
                    await event.answer("❌ Произошла ошибка. Попробуйте позже.", show_alert=True)
                except Exception:
                    pass
            elif isinstance(event, Message):
                try:
                    await event.answer("❌ Произошла ошибка. Попробуйте позже.")
                except Exception:
                    pass
            return None
