# middlewares/fsm_cancel.py — отмена FSM при нажатии кнопок меню
from typing import Any, Awaitable, Callable, Dict

from aiogram import BaseMiddleware
from aiogram.types import TelegramObject, Message
from aiogram.fsm.context import FSMContext

# Список кнопок меню
MENU_BUTTONS = [
    "📝 Регистрация", "👤 Профиль", "📋 Мои отклики", 
    "🔍 Найти тендеры", "⚙️ Админ-панель", "🏠 Главное меню", 
    "ℹ️ Помощь", "👥 Модерация", "👷 Рабочие", "📊 Статистика"
]


class FSMCancelMiddleware(BaseMiddleware):
    """Отменяет FSM состояние при нажатии кнопок меню."""

    async def __call__(
        self,
        handler: Callable[[TelegramObject, Dict[str, Any]], Awaitable[Any]],
        event: TelegramObject,
        data: Dict[str, Any],
    ) -> Any:
        # Проверяем только текстовые сообщения
        if isinstance(event, Message) and event.text:
            # Если это кнопка меню, отменяем FSM
            if event.text in MENU_BUTTONS:
                state: FSMContext = data.get("state")
                if state:
                    current_state = await state.get_state()
                    if current_state:
                        await state.clear()
        
        return await handler(event, data)

