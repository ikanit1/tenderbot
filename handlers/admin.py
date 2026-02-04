# handlers/admin.py — модерация пользователей и создание тендеров
from aiogram import F, Router
from aiogram.filters import Command
from aiogram.types import CallbackQuery, Message, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.fsm.context import FSMContext
from sqlalchemy import select, func
from sqlalchemy.orm import selectinload
from sqlalchemy.ext.asyncio import AsyncSession

from config import settings
from database.models import User, Tender, TenderApplication, Review, UserStatus, TenderStatus
from states.admin import ReviewStates
from utils import is_admin
from utils.chat_utils import answer_with_cleanup

router = Router()


# ——— Модерация: Одобрить / Отклонить ———
@router.callback_query(F.data.startswith("mod_approve:"))
async def moderation_approve(
    callback: CallbackQuery,
    session: AsyncSession,
) -> None:
    if not is_admin(callback.from_user.id):
        await callback.answer("Доступ запрещён.", show_alert=True)
        return
    user_id = int(callback.data.replace("mod_approve:", ""))
    result = await session.execute(select(User).where(User.id == user_id))
    user = result.scalar_one_or_none()
    if not user:
        await callback.answer("Пользователь не найден.", show_alert=True)
        return
    user.status = UserStatus.ACTIVE.value
    await session.flush()
    await callback.message.edit_text(
        callback.message.text + "\n\n✅ Одобрено."
    )
    await callback.bot.send_message(
        user.tg_id,
        "Ваша заявка одобрена. Теперь вы будете получать уведомления о подходящих тендерах."
    )
    await callback.answer("Пользователь одобрен.")


@router.callback_query(F.data.startswith("mod_reject:"))
async def moderation_reject(
    callback: CallbackQuery,
    session: AsyncSession,
) -> None:
    if not is_admin(callback.from_user.id):
        await callback.answer("Доступ запрещён.", show_alert=True)
        return
    user_id = int(callback.data.replace("mod_reject:", ""))
    result = await session.execute(select(User).where(User.id == user_id))
    user = result.scalar_one_or_none()
    if not user:
        await callback.answer("Пользователь не найден.", show_alert=True)
        return
    user.status = UserStatus.BANNED.value
    await session.flush()
    await callback.message.edit_text(
        callback.message.text + "\n\n❌ Отклонено."
    )
    await callback.bot.send_message(
        user.tg_id,
        "К сожалению, ваша заявка отклонена."
    )
    await callback.answer("Пользователь отклонён.")


@router.message(F.text == "⚙️ Админ-панель")
@router.message(F.text == "🏠 Главное меню")
async def cmd_admin_menu(message: Message, session: AsyncSession, state: FSMContext) -> None:
    """Переключение между админ-меню и главным меню."""
    # Отменяем FSM состояние, если оно активно
    current_state = await state.get_state()
    if current_state:
        await state.clear()
    
    from handlers.keyboards import get_admin_menu_kb, get_main_menu_kb
    result = await session.execute(select(User).where(User.tg_id == message.from_user.id))
    user = result.scalar_one_or_none()
    
    if message.text == "⚙️ Админ-панель":
        if not is_admin(message.from_user.id):
            await answer_with_cleanup(message, "❌ Доступ только для администратора.")
            return
        await answer_with_cleanup(
            message,
            "⚙️ <b>Админ-панель</b>\n\n"
            "Выберите действие:",
            reply_markup=get_admin_menu_kb(),
        )
    elif message.text == "🏠 Главное меню":
        user_role = user.role if user else None
        pending = user and user.status == UserStatus.PENDING_MODERATION.value
        await answer_with_cleanup(
            message,
            "🏠 <b>Главное меню</b>",
            reply_markup=get_main_menu_kb(user_role, is_admin(message.from_user.id), is_pending_moderation=pending),
        )


@router.message(F.text == "👥 Модерация")
async def cmd_moderation(message: Message, session: AsyncSession, state: FSMContext) -> None:
    """Просмотр заявок на модерацию."""
    # Отменяем FSM состояние, если оно активно
    current_state = await state.get_state()
    if current_state:
        await state.clear()
    
    if not is_admin(message.from_user.id):
        await answer_with_cleanup(message, "❌ Доступ только для администратора.")
        return
    
    result = await session.execute(
        select(User).where(User.status == UserStatus.PENDING_MODERATION.value)
        .order_by(User.id.desc())
        .limit(10)
    )
    users = result.scalars().all()
    
    if not users:
        await answer_with_cleanup(message, "✅ Нет заявок на модерацию.")
        return
    
    from handlers.keyboards import get_moderation_kb
    for user in users:
        role_str = "Исполнитель" if user.role == "executor" else (user.role or "—")
        skills_str = ", ".join(user.skills) if user.skills else "—"
        text = (
            f"🆕 <b>Новая заявка</b>\n\n"
            f"ФИО: {user.full_name}\n"
            f"Роль: {role_str}\n"
            f"Город: {user.city}\n"
            f"Телефон: {user.phone}\n"
            f"Навыки: {skills_str}\n"
            f"TG ID: {user.tg_id}"
        )
        await answer_with_cleanup(message, text, reply_markup=get_moderation_kb(user.id))


@router.message(F.text == "👷 Рабочие")
async def cmd_workers_button(message: Message, session: AsyncSession, state: FSMContext) -> None:
    """Обработчик кнопки 'Рабочие'."""
    # Отменяем FSM состояние, если оно активно
    current_state = await state.get_state()
    if current_state:
        await state.clear()
    await cmd_workers(message, session)


# ——— Просмотр мастеров (рабочих) ———
@router.message(Command("workers"))
async def cmd_workers(message: Message, session: AsyncSession) -> None:
    """Админ: список всех зарегистрированных мастеров (исполнителей)."""
    if not is_admin(message.from_user.id):
        await message.answer("Доступ только для администратора.")
        return
    # Можно: /workers — все, /workers active — только одобренные
    args = (message.text or "").strip().split()
    status_filter = args[1].lower() if len(args) > 1 else None  # active, pending_moderation, banned

    q = select(User).order_by(User.id)
    if status_filter in ("active", "pending_moderation", "banned"):
        q = q.where(User.status == status_filter)
    result = await session.execute(q)
    users = result.scalars().all()

    if not users:
        status_hint = f" со статусом «{status_filter}»" if status_filter else ""
        await message.answer(f"Мастеров{status_hint} пока нет.")
        return

    # Средний рейтинг по отзывам (to_user_id)
    result = await session.execute(
        select(Review.to_user_id, func.avg(Review.rating), func.count(Review.id))
        .group_by(Review.to_user_id)
    )
    ratings = {row[0]: (float(row[1]) if row[1] else 0, row[2]) for row in result.all()}

    lines = []
    status_emoji = {
        "active": "✅",
        "pending_moderation": "⏳",
        "banned": "❌",
    }
    for i, u in enumerate(users, 1):
        skills = ", ".join(u.skills[:3]) if u.skills else "—"
        if u.skills and len(u.skills) > 3:
            skills += "…"
        em = status_emoji.get(u.status, "•")
        rating_str = ""
        if u.id in ratings:
            avg_r, cnt_r = ratings[u.id]
            rating_str = f" | ★ {avg_r:.1f} ({cnt_r})"
        lines.append(
            f"{i}. {em} {u.full_name} | {u.city} | {skills} | {u.status}{rating_str}"
        )
    text = "📋 <b>Мастера (исполнители)</b>\n\n" + "\n".join(lines)
    if len(text) > 4000:
        text = text[:3990] + "\n\n… (обрезано, слишком много записей)"
    await message.answer(text)


# ——— Список тендеров (админ): /tenders [статус], пагинация ———
PAGE_SIZE = 5


@router.message(Command("tenders"))
async def cmd_tenders(message: Message, session: AsyncSession) -> None:
    """Админ: список тендеров с фильтром по статусу и пагинацией."""
    if not is_admin(message.from_user.id):
        await message.answer("Доступ только для администратора.")
        return
    args = (message.text or "").strip().split()
    status_filter = args[1].lower() if len(args) > 1 else None
    q = select(Tender).order_by(Tender.id.desc())
    if status_filter in ("draft", "open", "in_progress", "closed", "cancelled"):
        q = q.where(Tender.status == status_filter)
    result = await session.execute(q.limit(PAGE_SIZE + 1))
    tenders = result.scalars().all()
    has_more = len(tenders) > PAGE_SIZE
    if has_more:
        tenders = tenders[:PAGE_SIZE]
    if not tenders:
        await message.answer("Тендеров пока нет." + (f" Со статусом «{status_filter}»." if status_filter else ""))
        return
    lines = []
    for t in tenders:
        lines.append(f"#{t.id} {t.title} | {t.city} | {t.status}")
    text = "📋 <b>Тендеры</b>\n\n" + "\n".join(lines)
    buttons = []
    if has_more:
        buttons.append([
            InlineKeyboardButton(text="Далее", callback_data=f"tenders_page:{status_filter or 'all'}:{PAGE_SIZE}"),
        ])
    if buttons:
        await message.answer(text, reply_markup=InlineKeyboardMarkup(inline_keyboard=buttons))
    else:
        await message.answer(text)


@router.callback_query(F.data.startswith("tenders_page:"))
async def tenders_page_callback(callback: CallbackQuery, session: AsyncSession) -> None:
    """Пагинация списка тендеров."""
    if not is_admin(callback.from_user.id):
        await callback.answer("Доступ запрещён.", show_alert=True)
        return
    parts = callback.data.replace("tenders_page:", "").split(":")
    status_filter = parts[0] if parts[0] != "all" else None
    offset = int(parts[1]) if len(parts) > 1 else PAGE_SIZE
    q = select(Tender).order_by(Tender.id.desc()).offset(offset).limit(PAGE_SIZE + 1)
    if status_filter:
        q = q.where(Tender.status == status_filter)
    result = await session.execute(q)
    tenders = result.scalars().all()
    has_more = len(tenders) > PAGE_SIZE
    if has_more:
        tenders = tenders[:PAGE_SIZE]
    if not tenders:
        await callback.answer("Больше нет.")
        return
    lines = [f"#{t.id} {t.title} | {t.city} | {t.status}" for t in tenders]
    text = "📋 <b>Тендеры</b> (стр. " + str(offset // PAGE_SIZE + 1) + ")\n\n" + "\n".join(lines)
    buttons = []
    if has_more:
        buttons.append([
            InlineKeyboardButton(text="Далее", callback_data=f"tenders_page:{status_filter or 'all'}:{offset + PAGE_SIZE}"),
        ])
    await callback.message.edit_text(
        text,
        reply_markup=InlineKeyboardMarkup(inline_keyboard=buttons) if buttons else None,
    )
    await callback.answer()


@router.message(F.text == "📊 Статистика")
async def cmd_stats_button(message: Message, session: AsyncSession, state: FSMContext) -> None:
    """Обработчик кнопки 'Статистика'."""
    # Отменяем FSM состояние, если оно активно
    current_state = await state.get_state()
    if current_state:
        await state.clear()
    await cmd_stats(message, session)


# ——— Статистика: /stats ———
@router.message(Command("stats"))
async def cmd_stats(message: Message, session: AsyncSession) -> None:
    """Админ: сводка по пользователям, тендерам, откликам."""
    if not is_admin(message.from_user.id):
        await message.answer("Доступ только для администратора.")
        return
    from datetime import datetime, timedelta, timezone
    now = datetime.now(timezone.utc)
    today = now.replace(hour=0, minute=0, second=0, microsecond=0)
    week_ago = today - timedelta(days=7)
    # Пользователи по ролям и статусам
    result = await session.execute(
        select(User.role, User.status, func.count(User.id))
        .group_by(User.role, User.status)
    )
    role_status = result.all()
    result = await session.execute(select(func.count(User.id)))
    users_total = result.scalar() or 0
    # Тендеры по статусам
    result = await session.execute(
        select(Tender.status, func.count(Tender.id)).group_by(Tender.status)
    )
    tender_status = result.all()
    result = await session.execute(select(func.count(Tender.id)))
    tenders_total = result.scalar() or 0
    # Отклики за сегодня и за неделю
    result = await session.execute(
        select(func.count(TenderApplication.id)).where(TenderApplication.created_at >= today)
    )
    apps_today = result.scalar() or 0
    result = await session.execute(
        select(func.count(TenderApplication.id)).where(TenderApplication.created_at >= week_ago)
    )
    apps_week = result.scalar() or 0
    lines = [
        "<b>Статистика</b>",
        "",
        f"Пользователей: {users_total}",
    ]
    for r, s, c in role_status:
        lines.append(f"  — {r} / {s}: {c}")
    lines.extend(["", f"Тендеров: {tenders_total}"])
    for s, c in tender_status:
        lines.append(f"  — {s}: {c}")
    lines.extend([
        "",
        f"Откликов сегодня: {apps_today}",
        f"Откликов за неделю: {apps_week}",
    ])
    await message.answer("\n".join(lines))


# ——— Создание тендера: только через веб-интерфейс ———
@router.message(Command("add_tender"))
@router.message(F.text == "➕ Создать тендер")
async def cmd_add_tender(
    message: Message,
    session: AsyncSession,
) -> None:
    """Создание тендеров доступно только через веб-интерфейс."""
    from config import settings
    await answer_with_cleanup(
        message,
        "📋 <b>Создание тендеров</b>\n\n"
        "Создание тендеров доступно только через веб-интерфейс.\n\n"
        f"🌐 Откройте админ-панель: http://localhost:{settings.WEB_PORT}/tenders/create\n\n"
        "Или используйте веб-интерфейс для полного управления системой.",
    )


# Создание тендеров через бота отключено - используется веб-интерфейс


@router.callback_query(F.data.startswith("publish:"))
async def publish_tender(
    callback: CallbackQuery,
    session: AsyncSession,
) -> None:
    """Опубликовать черновик тендера: статус open, рассылка исполнителям."""
    tender_id = int(callback.data.replace("publish:", ""))
    result = await session.execute(
        select(Tender).where(Tender.id == tender_id, Tender.status == TenderStatus.DRAFT.value)
    )
    tender = result.scalar_one_or_none()
    if not tender:
        await callback.answer("Тендер не найден или уже опубликован.", show_alert=True)
        return
    # Только админ или создатель тендера
    if not is_admin(callback.from_user.id):
        result = await session.execute(select(User).where(User.tg_id == callback.from_user.id))
        user = result.scalar_one_or_none()
        if not user or user.id != tender.created_by_user_id:
            await callback.answer("Публиковать может только создатель или админ.", show_alert=True)
            return
    tender.status = TenderStatus.OPEN.value
    await session.flush()
    # Уведомляем только исполнителей: тот же город и навыки совпадают с категорией тендера
    result = await session.execute(
        select(User).where(
            User.status == UserStatus.ACTIVE.value,
            User.city == tender.city,
        )
    )
    all_city = result.scalars().all()
    users = [
        u for u in all_city
        if u.role in ("executor", "both")
        and (u.skills or [])
        and tender.category in (u.skills or [])
    ]
    tender_text = (
        f"📋 Тендер: {tender.title}\n"
        f"Категория: {tender.category}\n"
        f"Город: {tender.city}\n"
        f"Бюджет: {tender.budget or 'не указан'}\n\n"
        f"{tender.description}"
    )
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="Откликнуться", callback_data=f"apply:{tender.id}")]
    ])
    for u in users:
        try:
            await callback.bot.send_message(u.tg_id, tender_text, reply_markup=kb)
        except Exception:
            pass
    await callback.message.edit_text(
        callback.message.text + "\n\n✅ Опубликовано. Уведомления отправлены " + str(len(users)) + " исполнителям."
    )
    await callback.answer("Тендер опубликован.")


# ——— Выбор исполнителя по откликам ———
@router.callback_query(F.data.startswith("select_user:"))
async def admin_select_executor(
    callback: CallbackQuery,
    session: AsyncSession,
) -> None:
    """Выбор исполнителя: тендер in_progress, отклик selected, остальные rejected. Доступ: админ или создатель тендера."""
    app_id = int(callback.data.replace("select_user:", ""))
    result = await session.execute(
        select(TenderApplication)
        .options(
            selectinload(TenderApplication.user),
            selectinload(TenderApplication.tender),
        )
        .where(TenderApplication.id == app_id)
    )
    app = result.scalar_one_or_none()
    if not app:
        await callback.answer("Отклик не найден.", show_alert=True)
        return
    tender = app.tender
    # Доступ: админ или создатель тендера
    if not is_admin(callback.from_user.id):
        result = await session.execute(select(User).where(User.tg_id == callback.from_user.id))
        user = result.scalar_one_or_none()
        if not user or user.id != tender.created_by_user_id:
            await callback.answer("Выбрать исполнителя может только создатель тендера или админ.", show_alert=True)
            return
    app.status = "selected"
    tender.status = TenderStatus.IN_PROGRESS.value
    # Остальные отклики по этому тендеру — rejected
    result = await session.execute(
        select(TenderApplication).where(
            TenderApplication.tender_id == tender.id,
            TenderApplication.id != app.id,
        )
    )
    for other in result.scalars().all():
        other.status = "rejected"
    await session.flush()
    await callback.message.edit_text(
        callback.message.text + "\n\n✅ Исполнитель выбран."
    )
    await callback.bot.send_message(
        app.user.tg_id,
        f"Вас выбрали исполнителем по тендеру «{tender.title}». Администраторы свяжутся с вами для уточнения деталей."
    )
    await callback.answer("Исполнитель выбран.")


# ——— Закрыть / Отменить тендер (админ или создатель) ———
@router.callback_query(F.data.startswith("close_tender:"))
async def close_tender_callback(
    callback: CallbackQuery,
    session: AsyncSession,
) -> None:
    tender_id = int(callback.data.replace("close_tender:", ""))
    result = await session.execute(select(Tender).where(Tender.id == tender_id))
    tender = result.scalar_one_or_none()
    if not tender:
        await callback.answer("Тендер не найден.", show_alert=True)
        return
    if not is_admin(callback.from_user.id):
        result = await session.execute(select(User).where(User.tg_id == callback.from_user.id))
        user = result.scalar_one_or_none()
        if not user or user.id != tender.created_by_user_id:
            await callback.answer("Доступ только для создателя или админа.", show_alert=True)
            return
    tender.status = TenderStatus.CLOSED.value
    await session.flush()
    await callback.message.edit_text(
        (callback.message.text or "") + "\n\n✅ Тендер закрыт."
    )
    # Предложить создателю тендера оценить исполнителя (если есть выбранный отклик)
    result = await session.execute(
        select(TenderApplication)
        .options(selectinload(TenderApplication.user))
        .where(
            TenderApplication.tender_id == tender.id,
            TenderApplication.status == "selected",
        )
    )
    selected_app = result.scalar_one_or_none()
    if selected_app and tender.creator and tender.creator.tg_id:
        kb = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="Оценить исполнителя", callback_data=f"rate:{tender.id}")]
        ])
        try:
            await callback.bot.send_message(
                tender.creator.tg_id,
                f"Тендер «{tender.title}» закрыт. Оцените работу исполнителя?",
                reply_markup=kb,
            )
        except Exception:
            pass
    await callback.answer("Тендер закрыт.")


@router.callback_query(F.data.startswith("cancel_tender:"))
async def cancel_tender_callback(
    callback: CallbackQuery,
    session: AsyncSession,
) -> None:
    tender_id = int(callback.data.replace("cancel_tender:", ""))
    result = await session.execute(select(Tender).where(Tender.id == tender_id))
    tender = result.scalar_one_or_none()
    if not tender:
        await callback.answer("Тендер не найден.", show_alert=True)
        return
    if not is_admin(callback.from_user.id):
        result = await session.execute(select(User).where(User.tg_id == callback.from_user.id))
        user = result.scalar_one_or_none()
        if not user or user.id != tender.created_by_user_id:
            await callback.answer("Доступ только для создателя или админа.", show_alert=True)
            return
    tender.status = TenderStatus.CANCELLED.value
    await session.flush()
    await callback.message.edit_text(
        (callback.message.text or "") + "\n\n❌ Тендер отменён."
    )
    await callback.answer("Тендер отменён.")


# ——— Рейтинг исполнителя после закрытия тендера ———
@router.callback_query(F.data.startswith("rate:"))
async def rate_tender_start(
    callback: CallbackQuery,
    state: FSMContext,
    session: AsyncSession,
) -> None:
    """Начало оценки: только создатель тендера, по выбранному отклику."""
    tender_id = int(callback.data.replace("rate:", ""))
    result = await session.execute(
        select(Tender)
        .options(selectinload(Tender.creator))
        .where(Tender.id == tender_id, Tender.status == TenderStatus.CLOSED.value)
    )
    tender = result.scalar_one_or_none()
    if not tender:
        await callback.answer("Тендер не найден.", show_alert=True)
        return
    result = await session.execute(
        select(User).where(User.tg_id == callback.from_user.id)
    )
    user = result.scalar_one_or_none()
    if not user or user.id != tender.created_by_user_id:
        await callback.answer("Оценить может только создатель тендера.", show_alert=True)
        return
    result = await session.execute(
        select(TenderApplication)
        .options(selectinload(TenderApplication.user))
        .where(
            TenderApplication.tender_id == tender_id,
            TenderApplication.status == "selected",
        )
    )
    app = result.scalar_one_or_none()
    if not app:
        await callback.answer("Нет выбранного исполнителя по этому тендеру.", show_alert=True)
        return
    # Проверяем, что отзыв ещё не оставлен
    result = await session.execute(
        select(Review).where(Review.application_id == app.id)
    )
    if result.scalar_one_or_none():
        await callback.answer("Вы уже оценили этого исполнителя по данному тендеру.", show_alert=True)
        return
    await state.update_data(
        application_id=app.id,
        tender_id=tender_id,
        to_user_id=app.user_id,
        from_user_id=user.id,
    )
    await state.set_state(ReviewStates.rating)
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="1", callback_data="rating:1"), InlineKeyboardButton(text="2", callback_data="rating:2"),
         InlineKeyboardButton(text="3", callback_data="rating:3"), InlineKeyboardButton(text="4", callback_data="rating:4"),
         InlineKeyboardButton(text="5", callback_data="rating:5")],
    ])
    await callback.message.edit_text(
        f"Оцените исполнителя по тендеру «{tender.title}» (1–5):"
    )
    await callback.message.answer("Выберите оценку:", reply_markup=kb)
    await callback.answer()


@router.callback_query(ReviewStates.rating, F.data.startswith("rating:"))
async def review_rating_callback(
    callback: CallbackQuery,
    state: FSMContext,
) -> None:
    rating = int(callback.data.replace("rating:", ""))
    if rating not in (1, 2, 3, 4, 5):
        await callback.answer("Выберите оценку от 1 до 5.", show_alert=True)
        return
    await state.update_data(rating=rating)
    await state.set_state(ReviewStates.comment)
    await callback.message.edit_text(f"Оценка: {rating}. Введите комментарий к отзыву или напишите «пропустить».")
    await callback.answer()


@router.message(ReviewStates.comment, F.text)
async def review_comment_submit(
    message: Message,
    state: FSMContext,
    session: AsyncSession,
) -> None:
    data = await state.get_data()
    comment = None if message.text.strip().lower() in ("пропустить", "нет", "—", "-") else message.text.strip()
    review = Review(
        tender_id=data["tender_id"],
        application_id=data["application_id"],
        from_user_id=data["from_user_id"],
        to_user_id=data["to_user_id"],
        rating=data["rating"],
        comment=comment,
    )
    session.add(review)
    await session.flush()
    await state.clear()
    # Уведомляем исполнителя
    result = await session.execute(select(User).where(User.id == data["to_user_id"]))
    to_user = result.scalar_one_or_none()
    if to_user:
        try:
            await message.bot.send_message(
                to_user.tg_id,
                f"Вам поставили оценку {data['rating']}/5 по тендеру."
                + (f" Комментарий: {comment}" if comment else ""),
            )
        except Exception:
            pass
    await message.answer("Спасибо, ваш отзыв сохранён.")
