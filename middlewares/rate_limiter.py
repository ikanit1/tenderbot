# middlewares/rate_limiter.py — rate limiting для защиты от спама
import time
import logging
from typing import Any, Awaitable, Callable, Dict
from collections import defaultdict

from aiogram import BaseMiddleware
from aiogram.types import TelegramObject, Message, CallbackQuery
from config import settings

logger = logging.getLogger(__name__)


class RateLimiterMiddleware(BaseMiddleware):
    """
    Middleware для ограничения частоты запросов от одного пользователя.
    Использует простой in-memory счетчик запросов.
    """
    
    def __init__(self):
        self._requests: dict[int, list[float]] = defaultdict(list)
        self._max_requests = settings.RATE_LIMIT_REQUESTS
        self._period = settings.RATE_LIMIT_PERIOD
    
    def _cleanup_old_requests(self, user_id: int) -> None:
        """Удалить старые запросы вне периода."""
        now = time.time()
        cutoff = now - self._period
        self._requests[user_id] = [
            req_time
            for req_time in self._requests[user_id]
            if req_time > cutoff
        ]
    
    def _is_rate_limited(self, user_id: int) -> bool:
        """Проверить, превышен ли лимит запросов."""
        self._cleanup_old_requests(user_id)
        return len(self._requests[user_id]) >= self._max_requests
    
    def _record_request(self, user_id: int) -> None:
        """Записать запрос."""
        now = time.time()
        self._requests[user_id].append(now)
    
    async def __call__(
        self,
        handler: Callable[[TelegramObject, Dict[str, Any]], Awaitable[Any]],
        event: TelegramObject,
        data: Dict[str, Any],
    ) -> Any:
        # Получаем user_id из события
        user_id = None
        if isinstance(event, Message):
            user_id = event.from_user.id if event.from_user else None
        elif isinstance(event, CallbackQuery):
            user_id = event.from_user.id if event.from_user else None
        
        # Админы не ограничиваются
        if user_id == settings.ADMIN_ID:
            return await handler(event, data)
        
        if user_id is None:
            return await handler(event, data)
        
        # Проверяем rate limit
        if self._is_rate_limited(user_id):
            logger.warning(f"Rate limit exceeded for user {user_id}")
            if isinstance(event, CallbackQuery):
                await event.answer(
                    f"⏳ Слишком много запросов. Подождите {self._period} секунд.",
                    show_alert=True,
                )
            elif isinstance(event, Message):
                await event.answer(
                    f"⏳ Слишком много запросов. Подождите {self._period} секунд."
                )
            return None
        
        # Записываем запрос и продолжаем обработку
        self._record_request(user_id)
        return await handler(event, data)
