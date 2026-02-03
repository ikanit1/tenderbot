# handlers/customer.py — команды заказчика: мои тендеры
from aiogram import F, Router
from aiogram.filters import Command
from aiogram.types import CallbackQuery, Message, InlineKeyboardMarkup, InlineKeyboardButton
from sqlalchemy import select
from sqlalchemy.orm import selectinload
from sqlalchemy.ext.asyncio import AsyncSession

from config import settings
from database.models import User, Tender, TenderApplication, TenderStatus

router = Router()


def _is_admin(tg_id: int) -> bool:
    return tg_id == settings.ADMIN_ID


@router.message(Command("my_tenders"))
async def cmd_my_tenders(message: Message, session: AsyncSession) -> None:
    """Список тендеров заказчика (draft/open/in_progress/closed) с кнопками."""
    result = await session.execute(
        select(User).where(User.tg_id == message.from_user.id)
    )
    user = result.scalar_one_or_none()
    if not user:
        await message.answer("Сначала пройдите регистрацию (/register).")
        return
    if user.role not in ("customer", "both"):
        await message.answer("Команда для заказчиков. Вы зарегистрированы как исполнитель.")
        return
    result = await session.execute(
        select(Tender)
        .options(selectinload(Tender.applications))
        .where(Tender.created_by_user_id == user.id)
        .order_by(Tender.id.desc())
    )
    tenders = result.scalars().all()
    if not tenders:
        await message.answer("У вас пока нет тендеров. Создайте: /add_tender")
        return
    status_emoji = {
        TenderStatus.DRAFT.value: "📝",
        TenderStatus.OPEN.value: "🟢",
        TenderStatus.IN_PROGRESS.value: "🟡",
        TenderStatus.CLOSED.value: "✅",
        TenderStatus.CANCELLED.value: "❌",
    }
    for t in tenders[:10]:  # последние 10
        em = status_emoji.get(t.status, "•")
        dl = f"\nДедлайн: {t.deadline.strftime('%d.%m.%Y %H:%M')}" if t.deadline else ""
        apps_count = sum(1 for a in t.applications if a.status == "applied")
        selected = next((a for a in t.applications if a.status == "selected"), None)
        text = (
            f"{em} <b>{t.title}</b> | {t.city} | {t.status}{dl}\n"
            f"Откликов: {apps_count}"
            + (f" | Выбран: исполнитель #{selected.user_id}" if selected else "")
        )
        buttons = []
        if t.status == TenderStatus.DRAFT.value:
            buttons.append([InlineKeyboardButton(text="Опубликовать", callback_data=f"publish:{t.id}")])
        if t.status in (TenderStatus.OPEN.value, TenderStatus.IN_PROGRESS.value):
            buttons.append([InlineKeyboardButton(text="Закрыть", callback_data=f"close_tender:{t.id}")])
            buttons.append([InlineKeyboardButton(text="Отменить", callback_data=f"cancel_tender:{t.id}")])
        if buttons:
            await message.answer(text, reply_markup=InlineKeyboardMarkup(inline_keyboard=buttons))
        else:
            await message.answer(text)
    if len(tenders) > 10:
        await message.answer("… показаны последние 10. Полный список — в веб-админке.")
