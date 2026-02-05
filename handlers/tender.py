# handlers/tender.py — отклик на тендер («Откликнуться»)
import logging
from datetime import datetime, timezone

from aiogram import F, Router
from aiogram.types import CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton
from sqlalchemy import func, select
from sqlalchemy.orm import selectinload
from sqlalchemy.ext.asyncio import AsyncSession

from config import settings
from database.models import User, Tender, TenderApplication, Review, UserStatus, TenderStatus
from utils.validators import parse_callback_id
from utils.menu_updater import send_notification_with_menu_update
from services.user_service import UserService

logger = logging.getLogger(__name__)

router = Router()


@router.callback_query(F.data.startswith("tender_detail:"))
async def tender_detail_callback(
    callback: CallbackQuery,
    session: AsyncSession,
) -> None:
    """Показать подробную информацию о тендере."""
    tender_id = parse_callback_id(callback.data, "tender_detail:")
    if tender_id is None:
        await callback.answer("Ошибка обработки запроса.", show_alert=True)
        return
    
    result = await session.execute(
        select(Tender)
        .options(selectinload(Tender.creator))
        .where(Tender.id == tender_id)
    )
    tender = result.scalar_one_or_none()
    
    if not tender:
        await callback.answer("Тендер не найден.", show_alert=True)
        return
    
    # Проверяем, откликался ли пользователь на этот тендер
    tg_id = callback.from_user.id
    user = await UserService.get_user_by_tg_id(session, tg_id)
    
    has_applied = False
    if user:
        result = await session.execute(
            select(TenderApplication).where(
                TenderApplication.tender_id == tender_id,
                TenderApplication.user_id == user.id,
            )
        )
        has_applied = result.scalar_one_or_none() is not None
    
    # Форматируем дату дедлайна
    deadline_str = "Не указан"
    if tender.deadline:
        from datetime import datetime, timezone
        deadline_utc = tender.deadline
        if deadline_utc.tzinfo is None:
            deadline_utc = deadline_utc.replace(tzinfo=timezone.utc)
        deadline_str = deadline_utc.strftime("%d.%m.%Y %H:%M")
    
    text = (
        f"📋 <b>{tender.title}</b>\n\n"
        f"📍 <b>Город:</b> {tender.city}\n"
        f"🏷️ <b>Категория:</b> {tender.category}\n"
        f"💰 <b>Бюджет:</b> {tender.budget or 'по договорённости'}\n"
        f"⏰ <b>Дедлайн:</b> {deadline_str}\n"
        f"📊 <b>Статус:</b> {tender.status}\n\n"
        f"📝 <b>Описание:</b>\n{tender.description}\n\n"
    )
    
    if has_applied:
        text += "✅ <i>Вы уже откликнулись на этот тендер</i>"
    
    from handlers.keyboards import get_tender_list_kb
    kb = get_tender_list_kb(tender_id, can_apply=not has_applied and tender.status == TenderStatus.OPEN.value)
    
    await callback.message.edit_text(
        text=text,
        reply_markup=kb,
        parse_mode="HTML",
    )
    await callback.answer()


@router.callback_query(F.data.startswith("apply:"))
async def apply_to_tender(
    callback: CallbackQuery,
    session: AsyncSession,
) -> None:
    """Мастер нажал «Откликнуться»: создаём отклик и уведомляем админа с профилем мастера."""
    tender_id = parse_callback_id(callback.data, "apply:")
    if tender_id is None:
        await callback.answer("Ошибка обработки запроса.", show_alert=True)
        return
    tg_id = callback.from_user.id

    # Проверяем, может ли пользователь откликаться на тендеры
    can_apply = await UserService.can_user_apply_to_tenders(session, tg_id)
    if not can_apply:
        user = await UserService.get_user_by_tg_id(session, tg_id)
        if not user:
            await callback.answer("Сначала пройдите регистрацию.", show_alert=True)
        elif user.status != UserStatus.ACTIVE.value:
            await callback.answer("Ваш аккаунт не одобрен или заблокирован.", show_alert=True)
        else:
            await callback.answer("Откликаться на тендеры могут только исполнители.", show_alert=True)
        return
    
    user = await UserService.get_user_by_tg_id(session, tg_id)

    result = await session.execute(
        select(Tender)
        .options(selectinload(Tender.creator))
        .where(Tender.id == tender_id, Tender.status == TenderStatus.OPEN.value)
    )
    tender = result.scalar_one_or_none()
    if not tender:
        await callback.answer("Тендер не найден или приём откликов закрыт.", show_alert=True)
        return
    if tender.deadline:
        # Приводим deadline к UTC для корректного сравнения
        deadline_utc = tender.deadline
        if deadline_utc.tzinfo is None:
            # Если naive datetime, считаем что это UTC
            deadline_utc = deadline_utc.replace(tzinfo=timezone.utc)
        else:
            # Если есть timezone, конвертируем в UTC
            deadline_utc = deadline_utc.astimezone(timezone.utc)
        
        if datetime.now(timezone.utc) > deadline_utc:
            await callback.answer("Срок приёма откликов по этому тендеру истёк.", show_alert=True)
            return

    result = await session.execute(
        select(TenderApplication).where(
            TenderApplication.tender_id == tender_id,
            TenderApplication.user_id == user.id,
        )
    )
    if result.scalar_one_or_none():
        await callback.answer("Вы уже откликались на этот тендер.", show_alert=True)
        return

    # Создаём отклик
    app = TenderApplication(
        tender_id=tender_id,
        user_id=user.id,
        status="applied",
    )
    session.add(app)
    await session.flush()

    # Рейтинг исполнителя (средний по отзывам)
    result_r = await session.execute(
        select(func.avg(Review.rating), func.count(Review.id))
        .where(Review.to_user_id == user.id)
    )
    row_r = result_r.one_or_none()
    rating_str = ""
    if row_r and row_r[1] and row_r[1] > 0:
        rating_str = f"\nРейтинг: ★ {float(row_r[0]):.1f} ({row_r[1]} отзывов)"
    skills_str = ", ".join(user.skills) if user.skills else "—"
    text = (
        f"📩 Отклик на тендер «{tender.title}»\n\n"
        f"Мастер:\n"
        f"ФИО: {user.full_name}\n"
        f"Город: {user.city}\n"
        f"Телефон: {user.phone}\n"
        f"Навыки: {skills_str}\n"
        f"TG ID: {user.tg_id}{rating_str}"
    )
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="✅ Выбрать исполнителя", callback_data=f"select_user:{app.id}")]
    ])
    await callback.bot.send_message(
        settings.ADMIN_ID,
        text,
        reply_markup=kb,
    )
    # Уведомляем создателя тендера (если не админ) с обновлением меню
    if tender.creator and tender.creator.tg_id != settings.ADMIN_ID:
        notification_text = (
            f"📩 <b>Новый отклик на тендер</b>\n\n"
            f"{text}"
        )
        await send_notification_with_menu_update(
            bot=callback.bot,
            user_tg_id=tender.creator.tg_id,
            message_text=notification_text,
            session=session,
            update_menu=False,  # Не обновляем меню для создателя тендера
        )
        # Отправляем отдельное сообщение с кнопками
        try:
            await callback.bot.send_message(
                tender.creator.tg_id,
                "Выберите действие:",
                reply_markup=kb,
            )
        except Exception as e:
            logger.error(f"Failed to send application buttons to creator {tender.creator.tg_id}: {e}")
        logger.info(f"Application notification sent to tender creator {tender.creator.tg_id} for tender {tender_id}")
    
    # Отправляем уведомление пользователю с обновлением меню
    user_notification = (
        "✅ <b>Отклик отправлен!</b>\n\n"
        f"Ваш отклик на тендер «{tender.title}» успешно отправлен.\n"
        f"Ожидайте решения заказчика. Вы можете отслеживать статус в разделе «📋 Мои отклики»."
    )
    await send_notification_with_menu_update(
        bot=callback.bot,
        user_tg_id=callback.from_user.id,
        message_text=user_notification,
        session=session,
        update_menu=True,
    )
    
    logger.info(f"User {user.id} applied to tender {tender_id}")
    await callback.answer("Отклик отправлен. Ожидайте решения по вашей заявке.")
