# utils/menu_updater.py — автоматическое обновление меню и уведомлений в реальном времени
import logging
from typing import Optional
from aiogram import Bot
from aiogram.types import Message, ReplyKeyboardMarkup
from aiogram.exceptions import TelegramBadRequest, TelegramAPIError
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from config import settings
from database.models import User, UserStatus, UserRole
from handlers.keyboards import get_main_menu_kb, get_admin_menu_kb
from utils import is_admin

logger = logging.getLogger(__name__)


async def update_user_menu(
    bot: Bot,
    user_tg_id: int,
    session: AsyncSession,
    new_status: Optional[str] = None,
) -> bool:
    """
    Обновляет меню пользователя в зависимости от его текущего состояния.
    Находит последнее сообщение с меню и обновляет его клавиатуру.
    
    Args:
        bot: Экземпляр бота
        user_tg_id: Telegram ID пользователя
        session: Сессия БД
        new_status: Новый статус пользователя (если известен заранее)
    
    Returns:
        True если меню обновлено, False если не удалось
    """
    try:
        # Получаем актуальные данные пользователя
        result = await session.execute(select(User).where(User.tg_id == user_tg_id))
        user = result.scalar_one_or_none()
        
        if not user:
            return False
        
        # Определяем статус
        status = new_status or user.status
        is_admin_user = is_admin(user_tg_id)
        is_pending = status == UserStatus.PENDING_MODERATION.value
        
        # Получаем соответствующее меню
        menu_kb = get_main_menu_kb(
            user_role=user.role,
            is_admin=is_admin_user,
            is_pending_moderation=is_pending,
        )
        
        # Пытаемся обновить меню через set_my_commands или отправляем новое сообщение
        # В Telegram нет прямого способа обновить ReplyKeyboardMarkup существующего сообщения,
        # поэтому отправляем новое сообщение с обновленным меню
        try:
            await bot.send_message(
                chat_id=user_tg_id,
                text="🔄 <b>Меню обновлено</b>",
                reply_markup=menu_kb,
            )
            return True
        except TelegramAPIError as e:
            logger.error(f"Failed to update menu for user {user_tg_id}: {e}")
            return False
            
    except Exception as e:
        logger.error(f"Error updating menu for user {user_tg_id}: {e}")
        return False


async def send_notification_with_menu_update(
    bot: Bot,
    user_tg_id: int,
    message_text: str,
    session: AsyncSession,
    update_menu: bool = True,
) -> bool:
    """
    Отправляет уведомление пользователю и автоматически обновляет его меню.
    
    Args:
        bot: Экземпляр бота
        user_tg_id: Telegram ID пользователя
        message_text: Текст уведомления
        session: Сессия БД
        update_menu: Обновлять ли меню после отправки уведомления
    
    Returns:
        True если уведомление отправлено успешно
    """
    try:
        # Отправляем уведомление
        await bot.send_message(
            chat_id=user_tg_id,
            text=message_text,
            parse_mode="HTML",
        )
        
        # Обновляем меню если требуется
        if update_menu:
            await update_user_menu(bot, user_tg_id, session)
        
        return True
    except TelegramAPIError as e:
        logger.error(f"Failed to send notification to user {user_tg_id}: {e}")
        return False


async def refresh_user_menu_on_state_change(
    bot: Bot,
    user_tg_id: int,
    session: AsyncSession,
    old_status: str,
    new_status: str,
) -> None:
    """
    Обновляет меню пользователя при изменении его статуса.
    Вызывается после изменения статуса пользователя в БД.
    
    Args:
        bot: Экземпляр бота
        user_tg_id: Telegram ID пользователя
        session: Сессия БД
        old_status: Старый статус
        new_status: Новый статус
    """
    # Обновляем меню только если статус действительно изменился
    if old_status != new_status:
        await update_user_menu(bot, user_tg_id, session, new_status=new_status)


async def ensure_menu_visible(
    bot: Bot,
    user_tg_id: int,
    session: AsyncSession,
    welcome_text: Optional[str] = None,
) -> None:
    """
    Убеждается, что у пользователя видно актуальное меню.
    Если меню не видно, отправляет сообщение с меню.
    
    Args:
        bot: Экземпляр бота
        user_tg_id: Telegram ID пользователя
        session: Сессия БД
        welcome_text: Текст приветствия (опционально)
    """
    try:
        result = await session.execute(select(User).where(User.tg_id == user_tg_id))
        user = result.scalar_one_or_none()
        
        if not user:
            return
        
        is_admin_user = is_admin(user_tg_id)
        is_pending = user.status == UserStatus.PENDING_MODERATION.value
        
        menu_kb = get_main_menu_kb(
            user_role=user.role,
            is_admin=is_admin_user,
            is_pending_moderation=is_pending,
        )
        
        text = welcome_text or "🏠 <b>Главное меню</b>"
        
        await bot.send_message(
            chat_id=user_tg_id,
            text=text,
            reply_markup=menu_kb,
            parse_mode="HTML",
        )
    except Exception as e:
        logger.error(f"Error ensuring menu visibility for user {user_tg_id}: {e}")
