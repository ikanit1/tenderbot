# middlewares/chat_cleanup.py — удаление старых сообщений бота для чистоты чата
from typing import Any, Awaitable, Callable, Dict
from collections import defaultdict

from aiogram import BaseMiddleware
from aiogram.types import TelegramObject, Message
from aiogram.fsm.context import FSMContext

# Храним последние message_id бота для каждого пользователя
# Структура: {user_id: [message_id1, message_id2, ...]}
_last_bot_messages: Dict[int, list[int]] = defaultdict(list)
_MAX_MESSAGES_TO_KEEP = 3  # Сколько последних сообщений оставлять


class ChatCleanupMiddleware(BaseMiddleware):
    """Удаляет старые сообщения бота, оставляя только последние N сообщений."""

    async def __call__(
        self,
        handler: Callable[[TelegramObject, Dict[str, Any]], Awaitable[Any]],
        event: TelegramObject,
        data: Dict[str, Any],
    ) -> Any:
        result = await handler(event, data)
        
        # Если это ответ бота (Message), сохраняем его ID
        if isinstance(event, Message) and not event.from_user.is_bot:
            # Это сообщение от пользователя, проверяем ответ бота
            if hasattr(result, 'message_id') or (isinstance(result, Message) and result.message_id):
                # Если handler вернул сообщение бота, сохраняем его ID
                pass
        
        return result


async def cleanup_old_messages(bot, chat_id: int, keep_last: int = _MAX_MESSAGES_TO_KEEP) -> None:
    """Удаляет старые сообщения бота, оставляя только последние N."""
    if chat_id not in _last_bot_messages:
        return
    
    messages = _last_bot_messages[chat_id]
    
    # Если сообщений больше, чем нужно оставить, удаляем старые
    if len(messages) > keep_last:
        to_delete = messages[:-keep_last]  # Все кроме последних N
        for msg_id in to_delete:
            try:
                await bot.delete_message(chat_id=chat_id, message_id=msg_id)
            except Exception:
                # Сообщение уже удалено или недоступно - игнорируем
                pass
        
        # Обновляем список, оставляя только последние N
        _last_bot_messages[chat_id] = messages[-keep_last:]
    elif len(messages) > keep_last * 2:
        # Если список слишком большой, очищаем старые записи
        _last_bot_messages[chat_id] = messages[-keep_last:]


async def track_bot_message(chat_id: int, message_id: int) -> None:
    """Добавляет ID сообщения бота в список для отслеживания."""
    _last_bot_messages[chat_id].append(message_id)
    # Ограничиваем размер списка
    if len(_last_bot_messages[chat_id]) > _MAX_MESSAGES_TO_KEEP * 3:
        _last_bot_messages[chat_id] = _last_bot_messages[chat_id][-_MAX_MESSAGES_TO_KEEP * 3:]

