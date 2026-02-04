# utils/ui_manager.py — логика «одного сообщения» для FSM-хендлеров
from typing import Any, Awaitable, Callable, Dict, Optional, Union

from aiogram import BaseMiddleware
from aiogram.types import Message, CallbackQuery, InlineKeyboardMarkup, ReplyKeyboardMarkup, TelegramObject
from aiogram.fsm.context import FSMContext
from aiogram.exceptions import TelegramBadRequest

STATE_KEY_LAST_MSG_ID = "last_msg_id"


async def answer_ui(
    message_or_callback: Union[Message, CallbackQuery],
    text: str,
    reply_markup: Optional[InlineKeyboardMarkup | ReplyKeyboardMarkup] = None,
    state: Optional[FSMContext] = None,
    *,
    delete_user_message: bool = True,
    **kwargs: Any,
) -> Message:
    """
    Универсальный ответ: редактирует последнее сообщение бота или отправляет новое.
    Сохраняет message_id в state для следующего редактирования.
    При delete_user_message=True удаляет входящее текстовое сообщение пользователя (для Message).
    """
    if isinstance(message_or_callback, CallbackQuery):
        target_msg = message_or_callback.message
        chat_id = target_msg.chat.id
        is_callback = True
        user_message = None
    else:
        target_msg = message_or_callback
        chat_id = target_msg.chat.id
        is_callback = False
        user_message = (
            message_or_callback
            if (target_msg.text and target_msg.from_user and not target_msg.from_user.is_bot)
            else None
        )

    bot = target_msg.bot
    last_msg_id: Optional[int] = None
    if state:
        data = await state.get_data()
        last_msg_id = data.get(STATE_KEY_LAST_MSG_ID)

    if last_msg_id:
        try:
            result = await bot.edit_message_text(
                chat_id=chat_id,
                message_id=last_msg_id,
                text=text,
                reply_markup=reply_markup,
                **kwargs,
            )
            if delete_user_message and user_message:
                try:
                    await user_message.delete()
                except Exception:
                    pass
            return result if isinstance(result, Message) else target_msg
        except TelegramBadRequest:
            pass

    if is_callback:
        try:
            await target_msg.edit_text(text=text, reply_markup=reply_markup, **kwargs)
            if state:
                await state.update_data(**{STATE_KEY_LAST_MSG_ID: target_msg.message_id})
            return target_msg
        except TelegramBadRequest:
            pass

    new_msg = await bot.send_message(
        chat_id=chat_id, text=text, reply_markup=reply_markup, **kwargs
    )
    if state:
        await state.update_data(**{STATE_KEY_LAST_MSG_ID: new_msg.message_id})
    if delete_user_message and user_message:
        try:
            await user_message.delete()
        except Exception:
            pass
    return new_msg


class FSMDeleteUserMessageMiddleware(BaseMiddleware):
    """
    После обработки хендлера удаляет текстовое сообщение пользователя,
    если он всё ещё в FSM (состояние не было сброшено). Избавляет от
    необходимости вызывать message.delete() в каждом FSM-хендлере.
    """

    async def __call__(
        self,
        handler: Callable[[TelegramObject, Dict[str, Any]], Awaitable[Any]],
        event: TelegramObject,
        data: Dict[str, Any],
    ) -> Any:
        result = await handler(event, data)
        if (
            isinstance(event, Message)
            and event.text
            and event.from_user
            and not event.from_user.is_bot
        ):
            state: Optional[FSMContext] = data.get("state")
            if state:
                current = await state.get_state()
                if current:
                    try:
                        await event.delete()
                    except Exception:
                        pass
        return result
