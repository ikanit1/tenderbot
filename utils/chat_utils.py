# utils/chat_utils.py
from typing import Optional, Any
from collections import defaultdict
from aiogram import Bot
from aiogram.types import Message, InlineKeyboardMarkup, ReplyKeyboardMarkup

_last_bot_messages: dict[int, list[int]] = defaultdict(list)
_last_user_messages: dict[int, list[int]] = defaultdict(list)
_MAX_MESSAGES_TO_KEEP = 2

async def cleanup_old_messages(bot: Bot, chat_id: int, keep_last: int = _MAX_MESSAGES_TO_KEEP) -> None:
    if chat_id in _last_bot_messages:
        messages = _last_bot_messages[chat_id]
        if len(messages) > keep_last:
            to_delete = messages[:-keep_last]
            for msg_id in to_delete:
                try:
                    await bot.delete_message(chat_id=chat_id, message_id=msg_id)
                except Exception:
                    pass
            _last_bot_messages[chat_id] = messages[-keep_last:]
        elif len(messages) > keep_last * 3:
            _last_bot_messages[chat_id] = messages[-keep_last:]
    if chat_id in _last_user_messages:
        messages = _last_user_messages[chat_id]
        if len(messages) > keep_last:
            to_delete = messages[:-keep_last]
            for msg_id in to_delete:
                try:
                    if chat_id > 0:
                        await bot.delete_message(chat_id=chat_id, message_id=msg_id)
                except Exception:
                    pass
            _last_user_messages[chat_id] = messages[-keep_last:]
        elif len(messages) > keep_last * 3:
            _last_user_messages[chat_id] = messages[-keep_last:]

async def track_user_message(chat_id: int, message_id: int) -> None:
    _last_user_messages[chat_id].append(message_id)
    if len(_last_user_messages[chat_id]) > _MAX_MESSAGES_TO_KEEP * 3:
        _last_user_messages[chat_id] = _last_user_messages[chat_id][-_MAX_MESSAGES_TO_KEEP * 3:]

async def track_bot_message(chat_id: int, message_id: int) -> None:
    _last_bot_messages[chat_id].append(message_id)
    if len(_last_bot_messages[chat_id]) > _MAX_MESSAGES_TO_KEEP * 3:
        _last_bot_messages[chat_id] = _last_bot_messages[chat_id][-_MAX_MESSAGES_TO_KEEP * 3:]

async def answer_with_cleanup(message: Message, text: str, reply_markup: Optional[InlineKeyboardMarkup | ReplyKeyboardMarkup] = None, **kwargs: Any) -> Message:
    bot = message.bot
    chat_id = message.chat.id
    await cleanup_old_messages(bot, chat_id)
    new_message = await message.answer(text=text, reply_markup=reply_markup, **kwargs)
    await track_bot_message(chat_id, new_message.message_id)
    return new_message

def clear_user_messages(chat_id: int) -> None:
    if chat_id in _last_bot_messages:
        _last_bot_messages[chat_id].clear()
    if chat_id in _last_user_messages:
        _last_user_messages[chat_id].clear()
