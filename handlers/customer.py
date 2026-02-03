# handlers/customer.py — команды заказчика: мои тендеры
from aiogram import F, Router
from aiogram.filters import Command
from aiogram.types import Message
from aiogram.fsm.context import FSMContext
from sqlalchemy import select
from sqlalchemy.orm import selectinload
from sqlalchemy.ext.asyncio import AsyncSession

from database.models import User, Tender, TenderApplication, TenderStatus
from handlers.keyboards import get_tender_actions_kb

router = Router()


@router.message(Command("my_tenders"))
@router.message(F.text == "📝 Мои тендеры")
async def cmd_my_tenders(message: Message, session: AsyncSession, state: FSMContext) -> None:
    """Список тендеров заказчика (draft/open/in_progress/closed) с кнопками."""
    # Отменяем FSM состояние, если оно активно
    current_state = await state.get_state()
    if current_state:
        await state.clear()
    
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
        kb = get_tender_actions_kb(t.id, t.status)
        await message.answer(text, reply_markup=kb if kb.inline_keyboard else None)
    if len(tenders) > 10:
        await message.answer("… показаны последние 10. Полный список — в веб-админке.")
