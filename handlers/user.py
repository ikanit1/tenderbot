# handlers/user.py — регистрация исполнителя и заказчика (FSM)
from datetime import datetime

from aiogram import F, Router
from aiogram.filters import Command, CommandStart
from aiogram.types import CallbackQuery, Message, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.fsm.context import FSMContext
from sqlalchemy import select
from sqlalchemy.orm import selectinload
from sqlalchemy.ext.asyncio import AsyncSession

from config import settings
from database.models import User, UserStatus, UserRole, TenderApplication
from states.registration import (
    RegistrationStates,
    ProfileEditStates,
)
from handlers.keyboards import (
    get_main_menu_kb,
    get_skills_kb,
    get_profile_edit_kb,
    get_help_kb,
)
from utils.chat_utils import answer_with_cleanup, clear_user_messages

router = Router()





@router.message(CommandStart())
@router.message(Command("start"))
async def cmd_start(
    message: Message,
    session: AsyncSession,
    state: FSMContext,
) -> None:
    """Старт: проверяем, зарегистрирован ли пользователь."""
    await state.clear()
    result = await session.execute(select(User).where(User.tg_id == message.from_user.id))
    user = result.scalar_one_or_none()
    
    is_admin = message.from_user.id == settings.ADMIN_ID
    
    if user is None:
        welcome_text = (
            "👋 <b>Добро пожаловать в TenderBot!</b>\n\n"
            "Я помогу вам найти работу по вашей специальности.\n\n"
            "Для начала работы пройдите регистрацию:"
        )
        await answer_with_cleanup(
            message,
            welcome_text,
            reply_markup=get_main_menu_kb(None, is_admin),
        )
        return
    
    if user.status == UserStatus.PENDING_MODERATION.value:
        await answer_with_cleanup(
            message,
            "⏳ <b>Ваша заявка на модерации</b>\n\n"
            "Ожидайте решения администратора. Мы уведомим вас, как только ваша заявка будет рассмотрена.",
            reply_markup=get_main_menu_kb(user.role, is_admin),
        )
        return
    
    if user.status == UserStatus.BANNED.value:
        await message.answer(
            "❌ <b>Ваш аккаунт заблокирован</b>\n\n"
            "Обратитесь к администратору для выяснения причин."
        )
        return
    
    # Пользователь активен
    welcome_back = (
        f"👷 <b>Добро пожаловать обратно!</b>\n\n"
        f"Вы зарегистрированы как <b>Исполнитель</b>.\n\n"
        f"💡 Когда появятся подходящие тендеры, мы пришлём вам уведомление."
    )
    
    await answer_with_cleanup(
        message,
        welcome_back,
        reply_markup=get_main_menu_kb(user.role, is_admin),
    )


@router.message(Command("register"))
@router.message(F.text == "📝 Регистрация")
async def cmd_register(
    message: Message,
    session: AsyncSession,
    state: FSMContext,
) -> None:
    """Начало регистрации исполнителя."""
    # Отменяем FSM состояние, если оно активно
    current_state = await state.get_state()
    if current_state:
        await state.clear()
    
    result = await session.execute(select(User).where(User.tg_id == message.from_user.id))
    existing = result.scalar_one_or_none()
    if existing:
        if existing.status == UserStatus.PENDING_MODERATION.value:
            await answer_with_cleanup(
                message,
                "⏳ <b>Вы уже подали заявку</b>\n\n"
                "Ожидайте модерации. Мы уведомим вас о результате.",
            )
            return
        if existing.status == UserStatus.ACTIVE.value:
            await answer_with_cleanup(
                message,
                "✅ <b>Вы уже зарегистрированы</b>\n\n"
                "Используйте меню для навигации.",
                reply_markup=get_main_menu_kb(existing.role, message.from_user.id == settings.ADMIN_ID),
            )
            return
    
    # Сразу начинаем регистрацию исполнителя
    await state.set_state(RegistrationStates.full_name)
    await message.answer(
        "👷 <b>Регистрация исполнителя</b>\n\n"
        "Введите ваше ФИО (полностью):"
    )








@router.message(RegistrationStates.full_name, F.text)
async def step_full_name(message: Message, state: FSMContext) -> None:
    await state.update_data(full_name=message.text.strip())
    await state.set_state(RegistrationStates.birth_date)
    await message.answer("Введите дату рождения в формате ДД.ММ.ГГГГ (например 15.05.1990):")


@router.message(RegistrationStates.birth_date, F.text)
async def step_birth_date(message: Message, state: FSMContext) -> None:
    text = message.text.strip()
    try:
        dt = datetime.strptime(text, "%d.%m.%Y").date()
    except ValueError:
        await message.answer("Неверный формат. Введите дату как ДД.ММ.ГГГГ:")
        return
    await state.update_data(birth_date=dt)
    await state.set_state(RegistrationStates.city)
    await message.answer("Введите город:")


@router.message(RegistrationStates.city, F.text)
async def step_city(message: Message, state: FSMContext) -> None:
    await state.update_data(city=message.text.strip())
    await state.set_state(RegistrationStates.phone)
    await message.answer("Введите номер телефона (например +7 999 123-45-67):")


@router.message(RegistrationStates.phone, F.text)
async def step_phone(message: Message, state: FSMContext) -> None:
    await state.update_data(phone=message.text.strip())
    await state.set_state(RegistrationStates.skills)
    await message.answer(
        "🛠️ <b>Выбор навыков</b>\n\n"
        "Выберите ваши навыки (можно несколько). Нажмите на навык для выбора, затем нажмите <b>«✅ Готово»</b>:",
        reply_markup=get_skills_kb(),
    )


@router.callback_query(RegistrationStates.skills, F.data.startswith("skill:"))
async def step_skills_callback(
    callback: CallbackQuery,
    state: FSMContext,
) -> None:
    data = await state.get_data()
    skills: list = data.get("skills") or []
    value = callback.data.replace("skill:", "")
    if value == "done":
        if not skills:
            await callback.answer("⚠️ Выберите хотя бы один навык.", show_alert=True)
            return
        await state.update_data(skills=skills)
        await state.set_state(RegistrationStates.documents)
        skills_str = ", ".join(skills)
        await callback.message.edit_text(
            f"✅ <b>Навыки выбраны:</b> {skills_str}\n\n"
            "📎 <b>Документы</b> (необязательно)\n\n"
            "Вы можете загрузить фото или документы для подтверждения квалификации.\n"
            "Или нажмите «Пропустить», чтобы продолжить без документов.",
            reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="⏭️ Пропустить", callback_data="doc:skip")]
            ]),
        )
        await callback.answer()
        return
    # Переключаем навык
    if value in skills:
        skills.remove(value)
        action = "Удалено"
    else:
        skills.append(value)
        action = "Добавлено"
    
    await state.update_data(skills=skills)
    await callback.message.edit_reply_markup(reply_markup=get_skills_kb(skills))
    await callback.answer(f"{action}: {value}. Выбрано: {len(skills)}")


@router.callback_query(RegistrationStates.documents, F.data == "doc:skip")
async def step_documents_skip(
    callback: CallbackQuery,
    state: FSMContext,
    session: AsyncSession,
) -> None:
    await state.update_data(documents=None)
    await _submit_registration(callback.message, state, session, callback.from_user)
    await callback.message.delete()
    await callback.answer()


@router.message(RegistrationStates.documents, F.text)
async def step_documents_text(message: Message) -> None:
    """Если пользователь написал текст — напоминаем про файл или Пропустить."""
    await message.answer(
        "Отправьте фото/документ или нажмите «Пропустить» в сообщении выше."
    )


@router.message(RegistrationStates.documents, F.photo)
async def step_documents_photo(
    message: Message,
    state: FSMContext,
    session: AsyncSession,
) -> None:
    # Сохраняем только file_id для простоты (в БД — JSONB)
    photo = message.photo[-1]
    await state.update_data(documents={"photo_file_id": photo.file_id})
    await _submit_registration(message, state, session, message.from_user)


@router.message(RegistrationStates.documents, F.document)
async def step_documents_doc(
    message: Message,
    state: FSMContext,
    session: AsyncSession,
) -> None:
    doc = message.document
    await state.update_data(
        documents={"document_file_id": doc.file_id, "file_name": doc.file_name}
    )
    await _submit_registration(message, state, session, message.from_user)


async def _submit_registration(
    message: Message,
    state: FSMContext,
    session: AsyncSession,
    from_user,
) -> None:
    """Сохранение исполнителя в БД и отправка заявки админу на модерацию."""
    data = await state.get_data()
    birth_date = data.get("birth_date")
    user = User(
        tg_id=from_user.id,
        full_name=data["full_name"],
        birth_date=birth_date,
        city=data["city"],
        phone=data["phone"],
        role=UserRole.EXECUTOR.value,  # Только исполнитель
        skills=data["skills"],
        documents=data.get("documents"),
        status=UserStatus.PENDING_MODERATION.value,
    )
    session.add(user)
    await session.flush()  # чтобы получить user.id до коммита (коммит сделает middleware)
    await state.clear()
    # Очищаем старые сообщения после завершения регистрации
    from utils.chat_utils import clear_user_messages
    clear_user_messages(message.chat.id)

    # Текст для админа
    skills_str = ", ".join(data["skills"])
    text = (
        "🆕 Новая заявка на регистрацию:\n\n"
        f"ФИО: {data['full_name']}\n"
        f"Дата рождения: {birth_date}\n"
        f"Город: {data['city']}\n"
        f"Телефон: {data['phone']}\n"
        f"Навыки: {skills_str}\n"
        f"TG ID: {from_user.id}"
    )
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="✅ Одобрить", callback_data=f"mod_approve:{user.id}"),
            InlineKeyboardButton(text="❌ Отклонить", callback_data=f"mod_reject:{user.id}"),
        ]
    ])
    await message.bot.send_message(
        settings.ADMIN_ID,
        text,
        reply_markup=kb,
    )
    await answer_with_cleanup(
        message,
        "✅ <b>Заявка отправлена на модерацию</b>\n\n"
        "Ожидайте решения администратора. Мы уведомим вас о результате.",
        reply_markup=get_main_menu_kb(None, message.from_user.id == settings.ADMIN_ID),
    )


# ——— Профиль и мои отклики (исполнитель) ———
@router.message(Command("profile"))
@router.message(F.text == "👤 Профиль")
async def cmd_profile(message: Message, session: AsyncSession, state: FSMContext) -> None:
    """Просмотр своего профиля."""
    # Отменяем FSM состояние, если оно активно
    current_state = await state.get_state()
    if current_state:
        await state.clear()
    
    result = await session.execute(select(User).where(User.tg_id == message.from_user.id))
    user = result.scalar_one_or_none()
    if not user:
        await answer_with_cleanup(
            message,
            "❌ <b>Профиль не найден</b>\n\n"
            "Сначала пройдите регистрацию.",
            reply_markup=get_main_menu_kb(None, message.from_user.id == settings.ADMIN_ID),
        )
        return
    
    skills_str = ", ".join(user.skills) if user.skills else "—"
    role_str = "👷 Исполнитель"
    
    status_emoji = {
        UserStatus.PENDING_MODERATION.value: "⏳",
        UserStatus.ACTIVE.value: "✅",
        UserStatus.BANNED.value: "❌",
    }
    status_text = {
        UserStatus.PENDING_MODERATION.value: "На модерации",
        UserStatus.ACTIVE.value: "Активен",
        UserStatus.BANNED.value: "Заблокирован",
    }
    
    emoji = status_emoji.get(user.status, "•")
    status_display = f"{emoji} {status_text.get(user.status, user.status)}"
    
    text = (
        f"👤 <b>Ваш профиль</b>\n\n"
        f"📝 <b>ФИО:</b> {user.full_name}\n"
        f"📍 <b>Город:</b> {user.city}\n"
        f"📞 <b>Телефон:</b> {user.phone}\n"
        f"🎭 <b>Роль:</b> {role_str}\n"
        f"🛠️ <b>Навыки:</b> {skills_str}\n"
        f"📊 <b>Статус:</b> {status_display}\n"
    )
    
    if user.birth_date:
        text += f"\n🎂 <b>Дата рождения:</b> {user.birth_date.strftime('%d.%m.%Y')}"
    
    await answer_with_cleanup(message, text, reply_markup=get_profile_edit_kb())


@router.message(Command("edit_profile"))
@router.callback_query(F.data == "edit_profile")
async def cmd_edit_profile(
    message_or_callback: Message | CallbackQuery,
    session: AsyncSession,
    state: FSMContext,
) -> None:
    """Начало редактирования профиля: город, телефон, навыки."""
    if isinstance(message_or_callback, CallbackQuery):
        callback = message_or_callback
        if not callback.message:
            await callback.answer("Ошибка: сообщение не найдено.", show_alert=True)
            return
        message = callback.message
        tg_id = callback.from_user.id
        await callback.answer()
    else:
        message = message_or_callback
        tg_id = message.from_user.id
    
    result = await session.execute(select(User).where(User.tg_id == tg_id))
    user = result.scalar_one_or_none()
    if not user:
        await answer_with_cleanup(
            message,
            "❌ <b>Профиль не найден</b>\n\n"
            "Сначала пройдите регистрацию.",
            reply_markup=get_main_menu_kb(None, tg_id == settings.ADMIN_ID),
        )
        return
    await state.set_state(ProfileEditStates.city)
    await message.answer(
        f"✏️ <b>Редактирование профиля</b>\n\n"
        f"Введите новый город (текущий: <b>{user.city}</b>):"
    )


@router.message(ProfileEditStates.city, F.text)
async def edit_city(message: Message, state: FSMContext) -> None:
    await state.update_data(city=message.text.strip())
    await state.set_state(ProfileEditStates.phone)
    await message.answer("Введите новый телефон:")


@router.message(ProfileEditStates.phone, F.text)
async def edit_phone(message: Message, state: FSMContext) -> None:
    await state.update_data(phone=message.text.strip())
    await state.set_state(ProfileEditStates.skills)
    await message.answer(
        "🛠️ <b>Выбор навыков</b>\n\n"
        "Выберите ваши навыки (можно несколько). Нажмите на навык для выбора, затем нажмите <b>«✅ Готово»</b>:",
        reply_markup=get_skills_kb(),
    )


@router.callback_query(ProfileEditStates.skills, F.data.startswith("skill:"))
async def edit_skills_callback(callback: CallbackQuery, state: FSMContext, session: AsyncSession) -> None:
    data = await state.get_data()
    skills: list = data.get("skills") or []
    value = callback.data.replace("skill:", "")
    if value == "done":
        if not skills:
            await callback.answer("⚠️ Выберите хотя бы один навык.", show_alert=True)
            return
        await state.update_data(skills=skills)
        # Сохраняем в БД
        result = await session.execute(select(User).where(User.tg_id == callback.from_user.id))
        user = result.scalar_one_or_none()
        if user:
            user.city = data.get("city", user.city)
            user.phone = data.get("phone", user.phone)
            user.skills = skills
            await session.flush()
        await state.clear()
        # Очищаем старые сообщения после завершения редактирования
        from utils.chat_utils import clear_user_messages
        clear_user_messages(callback.message.chat.id)
        
        skills_str = ", ".join(skills)
        await callback.message.edit_text(
            f"✅ <b>Профиль обновлён</b>\n\n"
            f"📍 Город: <b>{data.get('city', user.city)}</b>\n"
            f"📞 Телефон: <b>{data.get('phone', user.phone)}</b>\n"
            f"🛠️ Навыки: <b>{skills_str}</b>"
        )
        await callback.answer("Профиль успешно обновлён!")
        
        # Показываем обновлённое меню
        from handlers.keyboards import get_main_menu_kb
        from config import settings
        await answer_with_cleanup(
            callback.message,
            "✅ <b>Профиль успешно обновлён!</b>",
            reply_markup=get_main_menu_kb(user.role, callback.from_user.id == settings.ADMIN_ID),
        )
        return
    # Переключаем навык
    if value in skills:
        skills.remove(value)
        action = "Удалено"
    else:
        skills.append(value)
        action = "Добавлено"
    
    await state.update_data(skills=skills)
    await callback.message.edit_reply_markup(reply_markup=get_skills_kb(skills))
    await callback.answer(f"{action}: {value}. Выбрано: {len(skills)}")


@router.message(Command("my_applications"))
@router.message(F.text == "📋 Мои отклики")
@router.callback_query(F.data == "my_applications")
async def cmd_my_applications(
    message_or_callback: Message | CallbackQuery,
    session: AsyncSession,
    state: FSMContext,
) -> None:
    """Мои отклики: список откликов исполнителя со статусами."""
    if isinstance(message_or_callback, CallbackQuery):
        callback = message_or_callback
        if not callback.message:
            await callback.answer("Ошибка: сообщение не найдено.", show_alert=True)
            return
        message = callback.message
        tg_id = callback.from_user.id
        await callback.answer()
    else:
        message = message_or_callback
        tg_id = message.from_user.id
        # Отменяем FSM состояние, если оно активно
        current_state = await state.get_state()
        if current_state:
            await state.clear()
    
    result = await session.execute(select(User).where(User.tg_id == tg_id))
    user = result.scalar_one_or_none()
    if not user:
        await answer_with_cleanup(
            message,
            "❌ <b>Профиль не найден</b>\n\n"
            "Сначала пройдите регистрацию.",
            reply_markup=get_main_menu_kb(None, tg_id == settings.ADMIN_ID),
        )
        return
    
    result = await session.execute(
        select(TenderApplication)
        .options(selectinload(TenderApplication.tender))
        .where(TenderApplication.user_id == user.id)
        .order_by(TenderApplication.id.desc())
    )
    apps = result.scalars().all()
    if not apps:
        await answer_with_cleanup(
            message,
            "📋 <b>Мои отклики</b>\n\n"
            "У вас пока нет откликов на тендеры.\n\n"
            "💡 Используйте кнопку <b>«🔍 Найти тендеры»</b> для поиска подходящих проектов.",
            reply_markup=get_main_menu_kb(user.role, message.from_user.id == settings.ADMIN_ID),
        )
        return
    
    status_emoji = {
        "applied": "⏳",
        "selected": "✅",
        "rejected": "❌",
        "completed": "✔️"
    }
    status_text = {
        "applied": "Ожидает",
        "selected": "Выбран",
        "rejected": "Отклонён",
        "completed": "Завершён"
    }
    
    lines = []
    for a in apps[:10]:
        em = status_emoji.get(a.status, "•")
        status_display = status_text.get(a.status, a.status)
        lines.append(f"{em} <b>{a.tender.title}</b> — {status_display}")
    
    text = "📋 <b>Мои отклики</b>\n\n" + "\n".join(lines)
    if len(apps) > 10:
        text += f"\n\n... показаны последние 10 из {len(apps)}"
    
    await answer_with_cleanup(message, text, reply_markup=get_main_menu_kb(user.role, message.from_user.id == settings.ADMIN_ID))


@router.message(F.text == "🔍 Найти тендеры")
async def cmd_find_tenders(message: Message, session: AsyncSession, state: FSMContext) -> None:
    """Поиск доступных тендеров для исполнителя."""
    # Отменяем FSM состояние, если оно активно
    current_state = await state.get_state()
    if current_state:
        await state.clear()
    
    result = await session.execute(select(User).where(User.tg_id == message.from_user.id))
    user = result.scalar_one_or_none()
    if not user:
        await answer_with_cleanup(
            message,
            "❌ <b>Профиль не найден</b>\n\n"
            "Сначала пройдите регистрацию.",
            reply_markup=get_main_menu_kb(None, message.from_user.id == settings.ADMIN_ID),
        )
        return
    
    # Показываем открытые тендеры, подходящие по городу и навыкам
    from database.models import Tender, TenderStatus
    result = await session.execute(
        select(Tender)
        .where(
            Tender.status == TenderStatus.OPEN.value,
            Tender.city == user.city,
        )
        .order_by(Tender.id.desc())
        .limit(10)
    )
    tenders = result.scalars().all()
    
    if not tenders:
        await answer_with_cleanup(
            message,
            "🔍 <b>Поиск тендеров</b>\n\n"
            "К сожалению, в вашем городе пока нет открытых тендеров.\n\n"
            "💡 Мы уведомим вас, когда появятся подходящие проекты!",
            reply_markup=get_main_menu_kb(user.role, message.from_user.id == settings.ADMIN_ID),
        )
        return
    
    from handlers.keyboards import get_tender_list_kb
    for tender in tenders:
        text = (
            f"📋 <b>{tender.title}</b>\n"
            f"📍 {tender.city} | 💰 {tender.budget or 'по договорённости'}\n"
            f"📝 {tender.description[:100]}{'...' if len(tender.description) > 100 else ''}"
        )
        await answer_with_cleanup(
            message,
            text,
            reply_markup=get_tender_list_kb(tender.id, can_apply=True),
        )


@router.message(Command("help"))
@router.message(F.text == "ℹ️ Помощь")
@router.callback_query(F.data.startswith("help_"))
async def cmd_help(
    message_or_callback: Message | CallbackQuery,
    state: FSMContext,
) -> None:
    """Справка и помощь пользователю."""
    if isinstance(message_or_callback, CallbackQuery):
        message = message_or_callback.message
        help_type = message_or_callback.data.replace("help_", "")
        await message_or_callback.answer()
    else:
        message = message_or_callback
        help_type = None
        # Отменяем FSM состояние, если оно активно
        current_state = await state.get_state()
        if current_state:
            await state.clear()
    
    if help_type == "commands":
        text = (
            "📖 <b>Доступные команды</b>\n\n"
            "👤 <b>Для всех:</b>\n"
            "/start — Главное меню\n"
            "/register — Регистрация\n"
            "/profile — Мой профиль\n"
            "/help — Справка\n\n"
            "👷 <b>Для исполнителей:</b>\n"
            "/my_applications — Мои отклики\n\n"
            "⚙️ <b>Для администраторов:</b>\n"
            "/workers — Список рабочих\n"
            "/stats — Статистика"
        )
    elif help_type == "faq":
        text = (
            "❓ <b>Часто задаваемые вопросы</b>\n\n"
            "<b>Как зарегистрироваться?</b>\n"
            "Используйте команду /register или кнопку «📝 Регистрация» в меню.\n\n"
            "<b>Сколько времени занимает модерация?</b>\n"
            "Обычно модерация занимает от нескольких минут до 24 часов.\n\n"
            "<b>Как создать тендер?</b>\n"
            "После регистрации как заказчик используйте /add_tender.\n\n"
            "<b>Как откликнуться на тендер?</b>\n"
            "Используйте кнопку «📩 Откликнуться» в описании тендера."
        )
    elif help_type == "support":
        text = (
            "📞 <b>Поддержка</b>\n\n"
            "Если у вас возникли вопросы или проблемы:\n\n"
            "1. Проверьте раздел FAQ\n"
            "2. Используйте команду /help\n"
            "3. Обратитесь к администратору"
        )
    else:
        text = (
            "ℹ️ <b>Помощь</b>\n\n"
            "Выберите интересующий вас раздел:"
        )
        await answer_with_cleanup(message, text, reply_markup=get_help_kb())
        return
    
    await answer_with_cleanup(message, text)
