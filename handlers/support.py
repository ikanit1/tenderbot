# handlers/support.py — тикеты поддержки
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from aiogram import F, Router
from aiogram.types import Message, CallbackQuery
from aiogram.fsm.context import FSMContext

from config import settings
from database.models import User, UserStatus, SupportTicket, SupportMessage, TicketStatus
from states.support import SupportStates
from handlers.keyboards import get_main_menu_kb, get_support_chat_kb
from utils.chat_utils import answer_with_cleanup, cleanup_old_messages, track_bot_message, track_user_message

router = Router()


async def _get_or_create_open_ticket(session: AsyncSession, user_id: int) -> SupportTicket | None:
    """Найти открытый тикет пользователя или создать новый."""
    result = await session.execute(
        select(SupportTicket)
        .where(
            SupportTicket.user_id == user_id,
            SupportTicket.status != TicketStatus.CLOSED.value,
        )
        .order_by(SupportTicket.id.desc())
        .limit(1)
    )
    ticket = result.scalar_one_or_none()
    if ticket:
        return ticket
    ticket = SupportTicket(user_id=user_id, status=TicketStatus.NEW.value)
    session.add(ticket)
    await session.flush()
    return ticket


@router.message(F.text == "💬 Поддержка")
async def cmd_support(
    message: Message,
    session: AsyncSession,
    state: FSMContext,
) -> None:
    """Вход в чат поддержки: создаём/открываем тикет, включаем состояние active_chat."""
    result = await session.execute(select(User).where(User.tg_id == message.from_user.id))
    user = result.scalar_one_or_none()
    is_admin = message.from_user.id == settings.ADMIN_ID
    if not user:
        await answer_with_cleanup(
            message,
            "❌ Сначала пройдите регистрацию.",
            reply_markup=get_main_menu_kb(None, is_admin),
        )
        return
    if user.status == UserStatus.PENDING_MODERATION.value:
        await answer_with_cleanup(
            message,
            "⏳ Доступ к поддержке будет после одобрения модерации.",
            reply_markup=get_main_menu_kb(user.role, is_admin, is_pending_moderation=True),
        )
        return
    if user.status == UserStatus.BANNED.value:
        await message.answer("❌ Ваш аккаунт заблокирован.")
        return

    ticket = await _get_or_create_open_ticket(session, user.id)
    await state.update_data(support_ticket_id=ticket.id)
    await state.set_state(SupportStates.active_chat)

    await answer_with_cleanup(
        message,
        "💬 <b>Чат поддержки</b>\n\n"
        "Напишите ваше сообщение. Администратор ответит в веб-панели.\n"
        "Чтобы завершить обращение — нажмите кнопку ниже.",
        reply_markup=get_support_chat_kb(),
    )


@router.message(SupportStates.active_chat, F.text)
async def support_message(
    message: Message,
    session: AsyncSession,
    state: FSMContext,
) -> None:
    """Сообщение пользователя в чате поддержки: сохраняем в БД (видят в веб-админке)."""
    data = await state.get_data()
    ticket_id = data.get("support_ticket_id")
    if not ticket_id:
        await state.clear()
        await message.answer("Сессия чата истекла. Нажмите «💬 Поддержка» снова.")
        return

    result = await session.execute(select(SupportTicket).where(SupportTicket.id == ticket_id))
    ticket = result.scalar_one_or_none()
    if not ticket or ticket.status == TicketStatus.CLOSED.value:
        await state.clear()
        await message.answer("Тикет закрыт. Нажмите «💬 Поддержка» для нового обращения.")
        return

    msg = SupportMessage(ticket_id=ticket_id, author="user", text=message.text.strip())
    session.add(msg)
    if ticket.status == TicketStatus.NEW.value:
        ticket.status = TicketStatus.IN_PROGRESS.value
    await session.flush()

    # Очистка старых сообщений в чате
    await track_user_message(message.chat.id, message.message_id)
    await cleanup_old_messages(message.bot, message.chat.id, keep_last=3)

    sent = await message.answer(
        "✅ Сообщение передано в поддержку. Ожидайте ответа.",
        reply_markup=get_support_chat_kb(),
    )
    await track_bot_message(message.chat.id, sent.message_id)


@router.callback_query(SupportStates.active_chat, F.data == "support_end_chat")
@router.callback_query(F.data == "support_end_chat")
async def support_end_chat(
    callback: CallbackQuery,
    session: AsyncSession,
    state: FSMContext,
) -> None:
    """Завершить чат: закрыть тикет, сбросить состояние."""
    await callback.answer()
    data = await state.get_data()
    ticket_id = data.get("support_ticket_id")
    if ticket_id:
        result = await session.execute(select(SupportTicket).where(SupportTicket.id == ticket_id))
        ticket = result.scalar_one_or_none()
        if ticket:
            ticket.status = TicketStatus.CLOSED.value

    await state.clear()

    result = await session.execute(select(User).where(User.tg_id == callback.from_user.id))
    user = result.scalar_one_or_none()
    is_admin = callback.from_user.id == settings.ADMIN_ID
    reply_markup = get_main_menu_kb(
        user.role if user else None,
        is_admin,
        is_pending_moderation=user and user.status == UserStatus.PENDING_MODERATION.value,
    )

    if callback.message:
        await callback.message.edit_text(
            "🔚 Чат поддержки завершён. Если появятся вопросы — нажмите «💬 Поддержка» снова."
        )
        await callback.message.answer("🏠 Главное меню", reply_markup=reply_markup)
