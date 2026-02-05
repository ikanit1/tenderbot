# middlewares/menu_refresh.py — автоматическое обновление меню при изменении состояния
import logging
from typing import Any, Awaitable, Callable, Dict

from aiogram import BaseMiddleware
from aiogram.types import TelegramObject, Message, CallbackQuery
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from database.models import User, UserStatus
from utils.menu_updater import ensure_menu_visible, update_user_menu
from utils import is_admin

logger = logging.getLogger(__name__)


class MenuRefreshMiddleware(BaseMiddleware):
    """
    Middleware для автоматического обновления меню пользователя.
    Проверяет актуальность меню при каждом взаимодействии и обновляет его при необходимости.
    """

    async def __call__(
        self,
        handler: Callable[[TelegramObject, Dict[str, Any]], Awaitable[Any]],
        event: TelegramObject,
        data: Dict[str, Any],
    ) -> Any:
        # Обрабатываем только сообщения и callback_query от пользователей
        if isinstance(event, (Message, CallbackQuery)):
            user_id = None
            bot = None
            
            if isinstance(event, Message):
                user_id = event.from_user.id if event.from_user else None
                bot = event.bot
            elif isinstance(event, CallbackQuery):
                user_id = event.from_user.id if event.from_user else None
                bot = event.bot
            
            if user_id and bot:
                session: AsyncSession = data.get("session")
                if session:
                    try:
                        # Проверяем актуальность статуса пользователя
                        result = await session.execute(
                            select(User).where(User.tg_id == user_id)
                        )
                        user = result.scalar_one_or_none()
                        
                        if user:
                            # Если пользователь на модерации, но меню не соответствует статусу,
                            # обновляем его автоматически
                            # Это особенно важно после одобрения/отклонения заявки
                            current_status = user.status
                            
                            # Обновляем меню только для текстовых сообщений с кнопками меню
                            # или для callback_query, чтобы не спамить
                            should_refresh = False
                            
                            if isinstance(event, Message) and event.text:
                                # Обновляем меню при командах /start или кнопках меню
                                menu_commands = ["/start", "🏠 Главное меню", "⚙️ Админ-панель"]
                                if event.text in menu_commands:
                                    should_refresh = True
                            
                            if should_refresh:
                                await update_user_menu(
                                    bot=bot,
                                    user_tg_id=user_id,
                                    session=session,
                                    new_status=current_status,
                                )
                    except Exception as e:
                        logger.error(f"Error in MenuRefreshMiddleware for user {user_id}: {e}")
        
        return await handler(event, data)
