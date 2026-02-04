# handlers/tender.py — отклик на тендер («Откликнуться»)
from datetime import datetime, timezone

from aiogram import F, Router
from aiogram.types import CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton
from sqlalchemy import func, select
from sqlalchemy.orm import selectinload
from sqlalchemy.ext.asyncio import AsyncSession

from config import settings
from database.models import User, Tender, TenderApplication, Review, UserStatus, TenderStatus

router = Router()


@router.callback_query(F.data.startswith("apply:"))
async def apply_to_tender(
    callback: CallbackQuery,
    session: AsyncSession,
) -> None:
    """Мастер нажал «Откликнуться»: создаём отклик и уведомляем админа с профилем мастера."""
    tender_id = int(callback.data.replace("apply:", ""))
    tg_id = callback.from_user.id

    # Проверяем, что пользователь active
    result = await session.execute(
        select(User).where(User.tg_id == tg_id)
    )
    user = result.scalar_one_or_none()
    if not user:
        await callback.answer("Сначала пройдите регистрацию.", show_alert=True)
        return
    if user.status != UserStatus.ACTIVE.value:
        await callback.answer("Ваш аккаунт не одобрен или заблокирован.", show_alert=True)
        return
    if user.role not in ("executor", "both"):
        await callback.answer("Откликаться на тендеры могут только исполнители.", show_alert=True)
        return

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
    # Уведомляем создателя тендера (если не админ)
    if tender.creator and tender.creator.tg_id != settings.ADMIN_ID:
        try:
            await callback.bot.send_message(
                tender.creator.tg_id,
                text,
                reply_markup=kb,
            )
        except Exception:
            pass

    await callback.answer("Отклик отправлен. Ожидайте решения по вашей заявке.")
