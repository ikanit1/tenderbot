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
    CustomerRegistrationStates,
    RoleChoiceStates,
    ProfileEditStates,
)

router = Router()


def _skills_kb() -> InlineKeyboardMarkup:
    """Клавиатура выбора навыков (тегов)."""
    buttons = [
        [InlineKeyboardButton(text=tag, callback_data=f"skill:{tag}")]
        for tag in settings.SKILL_TAGS
    ]
    buttons.append([InlineKeyboardButton(text="✅ Готово", callback_data="skill:done")])
    return InlineKeyboardMarkup(inline_keyboard=buttons)


def _role_kb() -> InlineKeyboardMarkup:
    """Клавиатура выбора роли при регистрации."""
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="Исполнитель (откликаюсь на тендеры)", callback_data="role:executor")],
        [InlineKeyboardButton(text="Заказчик (создаю тендеры)", callback_data="role:customer")],
        [InlineKeyboardButton(text="И то и другое", callback_data="role:both")],
    ])


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
    if user is None:
        await message.answer(
            "Добро пожаловать! Выберите роль и нажмите /register для регистрации.",
            reply_markup=_role_kb(),
        )
        return
    if user.status == UserStatus.PENDING_MODERATION.value:
        await message.answer(
            "Ваша заявка на модерации. Ожидайте решения администратора."
        )
        return
    if user.status == UserStatus.BANNED.value:
        await message.answer("Ваш аккаунт заблокирован.")
        return
    role_hint = ""
    if user.role == UserRole.CUSTOMER.value:
        role_hint = "Используйте /add_tender для создания тендера. "
    elif user.role in (UserRole.EXECUTOR.value, UserRole.BOTH.value):
        role_hint = "Когда появятся подходящие тендеры, мы пришлём уведомление. "
    if user.role == UserRole.BOTH.value:
        role_hint += "/add_tender — создать тендер."
    await message.answer(
        "Вы уже зарегистрированы. " + (role_hint or "Используйте /add_tender или ожидайте тендеры.")
    )


@router.message(Command("register"))
async def cmd_register(
    message: Message,
    session: AsyncSession,
    state: FSMContext,
) -> None:
    """Начало регистрации: выбор роли, затем соответствующий FSM."""
    result = await session.execute(select(User).where(User.tg_id == message.from_user.id))
    existing = result.scalar_one_or_none()
    if existing:
        if existing.status == UserStatus.PENDING_MODERATION.value:
            await message.answer("Вы уже подали заявку. Ожидайте модерации.")
            return
        if existing.status == UserStatus.ACTIVE.value:
            await message.answer("Вы уже зарегистрированы.")
            return
    await state.set_state(RoleChoiceStates.role)
    await message.answer(
        "Выберите роль:",
        reply_markup=_role_kb(),
    )


@router.callback_query(RoleChoiceStates.role, F.data.startswith("role:"))
async def role_choice_callback(
    callback: CallbackQuery,
    state: FSMContext,
) -> None:
    """После выбора роли запускаем FSM исполнителя или заказчика."""
    role = callback.data.replace("role:", "")
    if role not in (UserRole.EXECUTOR.value, UserRole.CUSTOMER.value, UserRole.BOTH.value):
        await callback.answer("Неверный выбор.", show_alert=True)
        return
    await state.update_data(role=role)
    await callback.message.edit_text(f"Роль: {'Исполнитель' if role == 'executor' else 'Заказчик' if role == 'customer' else 'Оба'}")
    if role == UserRole.CUSTOMER.value:
        await state.set_state(CustomerRegistrationStates.full_name)
        await callback.message.answer("Введите название организации или ФИО заказчика:")
    else:
        await state.set_state(RegistrationStates.full_name)
        await callback.message.answer("Введите ваше ФИО (полностью):")
    await callback.answer()


# ——— Регистрация заказчика (короткий поток) ———
@router.message(CustomerRegistrationStates.full_name, F.text)
async def customer_full_name(message: Message, state: FSMContext) -> None:
    await state.update_data(full_name=message.text.strip())
    await state.set_state(CustomerRegistrationStates.city)
    await message.answer("Введите город:")


@router.message(CustomerRegistrationStates.city, F.text)
async def customer_city(message: Message, state: FSMContext) -> None:
    await state.update_data(city=message.text.strip())
    await state.set_state(CustomerRegistrationStates.phone)
    await message.answer("Введите контактный телефон (например +7 999 123-45-67):")


@router.message(CustomerRegistrationStates.phone, F.text)
async def customer_phone(
    message: Message,
    state: FSMContext,
    session: AsyncSession,
) -> None:
    await state.update_data(phone=message.text.strip())
    await _submit_customer_registration(message, state, session, message.from_user)


async def _submit_customer_registration(
    message: Message,
    state: FSMContext,
    session: AsyncSession,
    from_user,
) -> None:
    """Сохранение заказчика в БД и отправка заявки админу на модерацию."""
    data = await state.get_data()
    user = User(
        tg_id=from_user.id,
        full_name=data["full_name"],
        birth_date=None,
        city=data["city"],
        phone=data["phone"],
        role=UserRole.CUSTOMER.value,
        skills=[],
        documents=None,
        status=UserStatus.PENDING_MODERATION.value,
    )
    session.add(user)
    await session.flush()
    await state.clear()
    text = (
        "🆕 Новая заявка на регистрацию <b>заказчика</b>:\n\n"
        f"ФИО/Организация: {data['full_name']}\n"
        f"Город: {data['city']}\n"
        f"Телефон: {data['phone']}\n"
        f"TG ID: {from_user.id}"
    )
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="✅ Одобрить", callback_data=f"mod_approve:{user.id}"),
            InlineKeyboardButton(text="❌ Отклонить", callback_data=f"mod_reject:{user.id}"),
        ]
    ])
    await message.bot.send_message(settings.ADMIN_ID, text, reply_markup=kb)
    await message.answer(
        "Заявка заказчика отправлена на модерацию. Ожидайте решения администратора."
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
        "Выберите ваши навыки (можно несколько). Нажмите по одному, затем «Готово»:",
        reply_markup=_skills_kb(),
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
            await callback.answer("Выберите хотя бы один навык.", show_alert=True)
            return
        await state.update_data(skills=skills)
        await state.set_state(RegistrationStates.documents)
        await callback.message.edit_text(
            "Загрузить фото или документы? (по желанию)\n"
            "Отправьте файл или нажмите «Пропустить».",
            reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="Пропустить", callback_data="doc:skip")]
            ]),
        )
        await callback.answer()
        return
    if value not in skills:
        skills.append(value)
    await state.update_data(skills=skills)
    await callback.answer(f"Добавлено: {value}. Всего: {len(skills)}. Нажмите «Готово», когда закончите.")


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
    """Сохранение исполнителя (или both) в БД и отправка заявки админу на модерацию."""
    data = await state.get_data()
    birth_date = data.get("birth_date")
    role = data.get("role") or UserRole.EXECUTOR.value  # executor или both
    user = User(
        tg_id=from_user.id,
        full_name=data["full_name"],
        birth_date=birth_date,
        city=data["city"],
        phone=data["phone"],
        role=role,
        skills=data["skills"],
        documents=data.get("documents"),
        status=UserStatus.PENDING_MODERATION.value,
    )
    session.add(user)
    await session.flush()  # чтобы получить user.id до коммита (коммит сделает middleware)
    await state.clear()

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
    await message.answer(
        "Заявка отправлена на модерацию. Ожидайте решения администратора."
    )


# ——— Профиль и мои отклики (исполнитель) ———
@router.message(Command("profile"))
async def cmd_profile(message: Message, session: AsyncSession) -> None:
    """Просмотр своего профиля."""
    result = await session.execute(select(User).where(User.tg_id == message.from_user.id))
    user = result.scalar_one_or_none()
    if not user:
        await message.answer("Сначала пройдите регистрацию (/register).")
        return
    skills_str = ", ".join(user.skills) if user.skills else "—"
    role_str = {"executor": "Исполнитель", "customer": "Заказчик", "both": "Исполнитель и заказчик"}.get(user.role, user.role)
    text = (
        f"<b>Ваш профиль</b>\n\n"
        f"ФИО: {user.full_name}\n"
        f"Город: {user.city}\n"
        f"Телефон: {user.phone}\n"
        f"Роль: {role_str}\n"
        f"Навыки: {skills_str}\n"
        f"Статус: {user.status}\n\n"
        "Изменить: /edit_profile"
    )
    await message.answer(text)


@router.message(Command("edit_profile"))
async def cmd_edit_profile(message: Message, session: AsyncSession, state: FSMContext) -> None:
    """Начало редактирования профиля: город, телефон, навыки."""
    result = await session.execute(select(User).where(User.tg_id == message.from_user.id))
    user = result.scalar_one_or_none()
    if not user:
        await message.answer("Сначала пройдите регистрацию (/register).")
        return
    await state.set_state(ProfileEditStates.city)
    await message.answer("Введите новый город (текущий: " + user.city + "):")


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
        "Выберите навыки (можно несколько). Нажмите по одному, затем «Готово»:",
        reply_markup=_skills_kb(),
    )


@router.callback_query(ProfileEditStates.skills, F.data.startswith("skill:"))
async def edit_skills_callback(callback: CallbackQuery, state: FSMContext, session: AsyncSession) -> None:
    data = await state.get_data()
    skills: list = data.get("skills") or []
    value = callback.data.replace("skill:", "")
    if value == "done":
        if not skills:
            await callback.answer("Выберите хотя бы один навык.", show_alert=True)
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
        await callback.message.edit_text("Профиль обновлён.")
        await callback.answer()
        return
    if value not in skills:
        skills.append(value)
    await state.update_data(skills=skills)
    await callback.answer(f"Добавлено: {value}. Всего: {len(skills)}. Нажмите «Готово», когда закончите.")


@router.message(Command("my_applications"))
async def cmd_my_applications(message: Message, session: AsyncSession) -> None:
    """Мои отклики: список откликов исполнителя со статусами."""
    result = await session.execute(select(User).where(User.tg_id == message.from_user.id))
    user = result.scalar_one_or_none()
    if not user:
        await message.answer("Сначала пройдите регистрацию (/register).")
        return
    result = await session.execute(
        select(TenderApplication)
        .options(selectinload(TenderApplication.tender))
        .where(TenderApplication.user_id == user.id)
        .order_by(TenderApplication.id.desc())
    )
    apps = result.scalars().all()
    if not apps:
        await message.answer("У вас пока нет откликов.")
        return
    status_emoji = {"applied": "⏳", "selected": "✅", "rejected": "❌", "completed": "✔"}
    lines = []
    for a in apps[:15]:
        em = status_emoji.get(a.status, "•")
        lines.append(f"{em} Тендер «{a.tender.title}» | {a.status}")
    text = "📋 <b>Мои отклики</b>\n\n" + "\n".join(lines)
    if len(apps) > 15:
        text += "\n\n… показаны последние 15."
    await message.answer(text)
