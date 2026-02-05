# handlers/user.py — регистрация исполнителя (FSM)
from datetime import datetime

import phonenumbers
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
from aiogram.utils.keyboard import InlineKeyboardBuilder
from utils.chat_utils import answer_with_cleanup, clear_user_messages
from utils.ui_manager import answer_ui
from utils.validators import validate_string_length, validate_date_range, parse_callback_id
from utils.menu_updater import ensure_menu_visible

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
            "Ожидайте решения администратора. Доступ к функциям бота будет после одобрения.",
            reply_markup=get_main_menu_kb(user.role, is_admin, is_pending_moderation=True),
        )
        return
    
    if user.status == UserStatus.BANNED.value:
        await message.answer(
            "❌ <b>Ваш аккаунт заблокирован</b>\n\n"
            "Обратитесь к администратору для выяснения причин."
        )
        return
    
    # Пользователь активен — всё в Mini App, уведомления приходят в чат
    welcome_back = (
        "👷 <b>Добро пожаловать!</b>\n\n"
        "Весь функционал — заказы, отклики, профиль — в приложении.\n\n"
        "Нажмите <b>«📱 Открыть приложение»</b> в меню.\n\n"
        "💡 Уведомления о новых заказах и статусе откликов будут приходить сюда в чат."
    )
    await ensure_menu_visible(
        bot=message.bot,
        user_tg_id=message.from_user.id,
        session=session,
        welcome_text=welcome_back,
    )


@router.message(Command("register"))
@router.message(F.text == "📝 Пройти регистрацию")
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
        is_admin = message.from_user.id == settings.ADMIN_ID
        if existing.status == UserStatus.PENDING_MODERATION.value:
            await answer_with_cleanup(
                message,
                "⏳ <b>Вы уже подали заявку</b>\n\n"
                "Ожидайте модерации. Доступ к боту будет после одобрения.",
                reply_markup=get_main_menu_kb(existing.role, is_admin, is_pending_moderation=True),
            )
            return
        if existing.status == UserStatus.ACTIVE.value:
            await answer_with_cleanup(
                message,
                "✅ <b>Вы уже зарегистрированы</b>\n\n"
                "Используйте меню для навигации.",
                reply_markup=get_main_menu_kb(existing.role, is_admin, is_pending_moderation=False),
            )
            return
    
    # Сразу начинаем регистрацию исполнителя (answer_ui сохраняет last_msg_id для редактирования на следующих шагах)
    await state.set_state(RegistrationStates.full_name)
    await answer_ui(
        message,
        "👷 <b>Регистрация исполнителя</b>\n\n"
        "Введите ваше ФИО (полностью):",
        state=state,
    )








@router.message(RegistrationStates.full_name, F.text)
async def step_full_name(message: Message, state: FSMContext) -> None:
    full_name = message.text.strip()
    is_valid, error_msg = validate_string_length(full_name, max_length=256, field_name="ФИО")
    if not is_valid:
        await answer_ui(message, f"❌ {error_msg}", state=state)
        return
    await state.update_data(full_name=full_name)
    await state.set_state(RegistrationStates.birth_date)
    await answer_ui(message, "Введите дату рождения в формате ДД.ММ.ГГГГ (например 15.05.1990):", state=state)


@router.message(RegistrationStates.birth_date, F.text)
async def step_birth_date(message: Message, state: FSMContext) -> None:
    text = message.text.strip()
    try:
        dt = datetime.strptime(text, "%d.%m.%Y").date()
    except ValueError:
        await answer_ui(message, "Неверный формат. Введите дату как ДД.ММ.ГГГГ:", state=state)
        return
    
    # Валидация диапазона даты рождения (не в будущем, не слишком давно)
    from datetime import date
    today = date.today()
    min_date = date(1900, 1, 1)
    max_date = today
    
    is_valid, error_msg = validate_date_range(dt, min_date=min_date, max_date=max_date, field_name="Дата рождения")
    if not is_valid:
        await answer_ui(message, f"❌ {error_msg}", state=state)
        return
    
    await state.update_data(birth_date=dt)
    await state.set_state(RegistrationStates.city)
    await answer_ui(message, "Введите город:", state=state)


@router.message(RegistrationStates.city, F.text)
async def step_city(message: Message, state: FSMContext) -> None:
    city = message.text.strip()
    is_valid, error_msg = validate_string_length(city, max_length=128, field_name="Город")
    if not is_valid:
        await answer_ui(message, f"❌ {error_msg}", state=state)
        return
    await state.update_data(city=city)
    await state.set_state(RegistrationStates.phone)
    await answer_ui(message, "Введите номер телефона (например +7 999 123-45-67):", state=state)


def _validate_phone(phone: str) -> tuple[bool, str | None]:
    """Проверка формата номера телефона. Возвращает (ok, normalized_or_error_message)."""
    try:
        parsed = phonenumbers.parse(phone.strip(), "RU")
        if not phonenumbers.is_valid_number(parsed):
            return False, "Номер телефона недействителен. Введите корректный номер, например +7 999 123-45-67."
        normalized = phonenumbers.format_number(parsed, phonenumbers.PhoneNumberFormat.INTERNATIONAL)
        return True, normalized
    except phonenumbers.NumberParseException:
        return False, "Неверный формат номера. Укажите номер с кодом страны, например +7 999 123-45-67."
    except Exception:
        return False, "Не удалось проверить номер. Укажите номер в формате +7 999 123-45-67."


@router.message(RegistrationStates.phone, F.text)
async def step_phone(message: Message, state: FSMContext) -> None:
    phone_raw = message.text.strip()
    ok, result = _validate_phone(phone_raw)
    if not ok:
        await answer_ui(message, result, state=state)
        return
    await state.update_data(phone=result)
    await state.set_state(RegistrationStates.skills)
    await answer_ui(
        message,
        "🛠️ <b>Выбор навыков</b>\n\n"
        "Выберите ваши навыки (можно несколько). Нажмите на навык для выбора, затем нажмите <b>«✅ Готово»</b>:",
        reply_markup=get_skills_kb(),
        state=state,
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
        await state.update_data(skills=skills, documents_list=[])
        await state.set_state(RegistrationStates.documents)
        skills_str = ", ".join(skills)
        await callback.message.edit_text(
            f"✅ <b>Навыки выбраны:</b> {skills_str}\n\n"
            "📎 <b>Документы</b> (необязательно)\n\n"
            "Можно загрузить несколько фото или документов для подтверждения квалификации.\n"
            "Отправьте файлы по одному, затем нажмите «Готово» или «Пропустить».\n\n"
            "💡 <i>Файлы нужны только для модерации и не хранятся дольше недели.</i>",
            reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="✅ Отправить заявку", callback_data="doc:done"), InlineKeyboardButton(text="⏭️ Без документов", callback_data="doc:skip")]
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


def _documents_list_to_save(docs_list: list) -> list | None:
    """Формат для БД: список {type, file_id, file_name?, mime_type?}."""
    if not docs_list:
        return None
    return docs_list


@router.callback_query(RegistrationStates.documents, F.data == "doc:skip")
async def step_documents_skip(
    callback: CallbackQuery,
    state: FSMContext,
    session: AsyncSession,
) -> None:
    await state.update_data(documents=None, documents_list=[])
    await _submit_registration(callback.message, state, session, callback.from_user)
    await callback.message.delete()
    await callback.answer()


@router.callback_query(RegistrationStates.documents, F.data == "doc:done")
async def step_documents_done(
    callback: CallbackQuery,
    state: FSMContext,
    session: AsyncSession,
) -> None:
    """Завершить добавление документов и отправить заявку."""
    data = await state.get_data()
    docs_list = data.get("documents_list") or []
    documents = _documents_list_to_save(docs_list)
    await state.update_data(documents=documents, documents_list=[])
    await _submit_registration(callback.message, state, session, callback.from_user)
    await callback.message.delete()
    await callback.answer()


@router.message(RegistrationStates.documents, F.text)
async def step_documents_text(message: Message) -> None:
    """Если пользователь написал текст — напоминаем про файл или кнопки."""
    await message.answer(
        "Отправьте фото/документ или нажмите «Готово» / «Пропустить» в сообщении выше."
    )


def _check_document_allowed(
    file_name: str | None,
    mime_type: str | None,
    file_size: int | None,
) -> str | None:
    """Проверка типа и размера файла. Возвращает None если ок, иначе текст ошибки."""
    max_bytes = settings.MAX_DOCUMENT_SIZE_MB * 1024 * 1024
    if file_size is not None and file_size > max_bytes:
        return (
            f"Файл слишком большой. Максимум: {settings.MAX_DOCUMENT_SIZE_MB} МБ. "
            f"Ваш файл: {file_size / (1024*1024):.1f} МБ."
        )
    if file_name:
        ext = "." + file_name.rsplit(".", 1)[-1].lower() if "." in file_name else ""
        if ext and ext not in settings.ALLOWED_DOCUMENT_EXTENSIONS:
            return (
                f"Недопустимый тип файла. Разрешены: "
                f"{', '.join(settings.ALLOWED_DOCUMENT_EXTENSIONS)}"
            )
    if mime_type and settings.ALLOWED_DOCUMENT_MIME_PREFIXES:
        if not any(mime_type.lower().startswith(p.lower()) for p in settings.ALLOWED_DOCUMENT_MIME_PREFIXES):
            return (
                "Недопустимый тип файла. Разрешены: фото (JPEG, PNG) и PDF."
            )
    return None


def _get_documents_kb() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="✅ Отправить заявку", callback_data="doc:done"), InlineKeyboardButton(text="⏭️ Без документов", callback_data="doc:skip")]
    ])


@router.message(RegistrationStates.documents, F.photo)
async def step_documents_photo(
    message: Message,
    state: FSMContext,
) -> None:
    photo = message.photo[-1]
    err = _check_document_allowed(
        file_name="photo.jpg",
        mime_type="image/jpeg",
        file_size=getattr(photo, "file_size", None),
    )
    if err:
        await message.answer(f"❌ {err}")
        return
    data = await state.get_data()
    docs_list = list(data.get("documents_list") or [])
    docs_list.append({
        "type": "photo",
        "file_id": photo.file_id,
        "file_name": None,
        "mime_type": "image/jpeg",
    })
    await state.update_data(documents_list=docs_list)
    await message.answer(
        f"✅ Добавлено фото (всего файлов: {len(docs_list)}). Отправьте ещё или нажмите «Готово».",
        reply_markup=_get_documents_kb(),
    )


@router.message(RegistrationStates.documents, F.document)
async def step_documents_doc(
    message: Message,
    state: FSMContext,
) -> None:
    doc = message.document
    err = _check_document_allowed(
        file_name=doc.file_name,
        mime_type=getattr(doc, "mime_type", None),
        file_size=getattr(doc, "file_size", None),
    )
    if err:
        await message.answer(f"❌ {err}")
        return
    data = await state.get_data()
    docs_list = list(data.get("documents_list") or [])
    docs_list.append({
        "type": "document",
        "file_id": doc.file_id,
        "file_name": doc.file_name,
        "mime_type": getattr(doc, "mime_type", None),
    })
    await state.update_data(documents_list=docs_list)
    await message.answer(
        f"✅ Добавлен документ (всего файлов: {len(docs_list)}). Отправьте ещё или нажмите «Готово».",
        reply_markup=_get_documents_kb(),
    )


async def _submit_registration(
    message: Message,
    state: FSMContext,
    session: AsyncSession,
    from_user,
) -> None:
    """Сохранение исполнителя в БД и отправка заявки админу на модерацию."""
    # Проверяем, не существует ли уже пользователь с таким tg_id
    result = await session.execute(select(User).where(User.tg_id == from_user.id))
    existing_user = result.scalar_one_or_none()
    if existing_user:
        await answer_with_cleanup(
            message,
            "❌ <b>Ошибка регистрации</b>\n\n"
            "Пользователь с таким Telegram ID уже зарегистрирован.",
            reply_markup=get_main_menu_kb(existing_user.role, message.from_user.id == settings.ADMIN_ID, is_pending_moderation=existing_user.status == UserStatus.PENDING_MODERATION.value),
        )
        await state.clear()
        return
    
    data = await state.get_data()
    birth_date = data.get("birth_date")
    
    # Финальная валидация длины полей перед сохранением
    full_name_valid, full_name_error = validate_string_length(data.get("full_name", ""), max_length=256, field_name="ФИО")
    city_valid, city_error = validate_string_length(data.get("city", ""), max_length=128, field_name="Город")
    phone_valid, phone_error = validate_string_length(data.get("phone", ""), max_length=64, field_name="Телефон")
    
    if not (full_name_valid and city_valid and phone_valid):
        error_msg = full_name_error or city_error or phone_error
        await answer_with_cleanup(message, f"❌ {error_msg}")
        return
    
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
    # Отправляем подтверждение и обновляем меню
    await answer_with_cleanup(
        message,
        "✅ <b>Заявка отправлена на модерацию</b>\n\n"
        "Ожидайте решения администратора. Доступ к функциям бота будет после одобрения.\n\n"
        "💡 Меню обновится автоматически после модерации.",
        reply_markup=get_main_menu_kb(user.role, message.from_user.id == settings.ADMIN_ID, is_pending_moderation=True),
    )
    
    # Убеждаемся, что меню видно
    await ensure_menu_visible(
        bot=message.bot,
        user_tg_id=from_user.id,
        session=session,
    )


async def _require_active_user(
    message: Message,
    user: User | None,
    is_admin: bool,
) -> bool:
    """Если пользователь на модерации — отвечает «Доступ после модерации» и возвращает True (прервать)."""
    if user and user.status == UserStatus.PENDING_MODERATION.value:
        await answer_with_cleanup(
            message,
            "⏳ <b>Доступ после модерации</b>\n\n"
            "Функции бота будут доступны после одобрения вашей заявки администратором.",
            reply_markup=get_main_menu_kb(user.role, is_admin, is_pending_moderation=True),
        )
        return True
    return False


# ——— Профиль и мои отклики (исполнитель) ———
@router.message(Command("profile"))
@router.message(F.text == "👤 Мой профиль")
@router.message(F.text == "📋 Мои отклики")
@router.message(F.text == "🔍 Искать заказы")
async def cmd_redirect_to_app(message: Message, session: AsyncSession, state: FSMContext) -> None:
    """Редирект: профиль, отклики и заказы — в Mini App."""
    current_state = await state.get_state()
    if current_state:
        await state.clear()
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
    await answer_with_cleanup(
        message,
        "📱 <b>Откройте приложение</b>\n\n"
        "Профиль, заказы и отклики доступны в Mini App.\n\n"
        "Нажмите кнопку <b>«📱 Открыть приложение»</b> в меню ниже.",
        reply_markup=get_main_menu_kb(user.role, is_admin, is_pending_moderation=(user.status == UserStatus.PENDING_MODERATION.value)),
    )


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
    is_admin = tg_id == settings.ADMIN_ID
    if not user:
        await answer_with_cleanup(
            message,
            "❌ <b>Профиль не найден</b>\n\n"
            "Сначала пройдите регистрацию.",
            reply_markup=get_main_menu_kb(None, is_admin),
        )
        return
    if await _require_active_user(message, user, is_admin):
        return
    await state.set_state(ProfileEditStates.city)
    await message.answer(
        f"✏️ <b>Редактирование профиля</b>\n\n"
        f"Введите новый город (текущий: <b>{user.city}</b>):"
    )


@router.message(ProfileEditStates.city, F.text)
async def edit_city(message: Message, state: FSMContext) -> None:
    city = message.text.strip()
    is_valid, error_msg = validate_string_length(city, max_length=128, field_name="Город")
    if not is_valid:
        await message.answer(f"❌ {error_msg}")
        return
    await state.update_data(city=city)
    await state.set_state(ProfileEditStates.phone)
    await message.answer("Введите новый телефон:")


@router.message(ProfileEditStates.phone, F.text)
async def edit_phone(message: Message, state: FSMContext) -> None:
    ok, result = _validate_phone(message.text)
    if not ok:
        await message.answer(result)
        return
    await state.update_data(phone=result)
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
            reply_markup=get_main_menu_kb(user.role, callback.from_user.id == settings.ADMIN_ID, is_pending_moderation=False),
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
    is_admin = tg_id == settings.ADMIN_ID
    if not user:
        await answer_with_cleanup(
            message,
            "❌ <b>Профиль не найден</b>\n\n"
            "Сначала пройдите регистрацию.",
            reply_markup=get_main_menu_kb(None, is_admin),
        )
        return
    if await _require_active_user(message, user, is_admin):
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
            "💡 Используйте кнопку <b>«🔍 Искать заказы»</b> для поиска подходящих проектов.",
            reply_markup=get_main_menu_kb(user.role, is_admin, is_pending_moderation=False),
        )
        return
    
    # Создаем развернутое меню с кнопками для каждого отклика
    from handlers.keyboards import get_application_detail_kb
    from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
    
    status_emoji = {
        "applied": "⏳",
        "selected": "✅",
        "rejected": "❌",
        "completed": "✔️"
    }
    status_text = {
        "applied": "Ожидает рассмотрения",
        "selected": "Выбран исполнителем",
        "rejected": "Отклонён",
        "completed": "Завершён"
    }
    
    text = "📋 <b>Мои отклики</b>\n\n"
    text += f"Всего откликов: <b>{len(apps)}</b>\n\n"
    
    # Показываем первые 5 откликов с подробной информацией
    for i, app in enumerate(apps[:5], 1):
        em = status_emoji.get(app.status, "•")
        status_display = status_text.get(app.status, app.status)
        created_at_str = ""
        if app.created_at:
            from datetime import datetime, timezone
            now = datetime.now(timezone.utc)
            delta = now - app.created_at.replace(tzinfo=timezone.utc) if app.created_at.tzinfo is None else now - app.created_at
            if delta.days > 0:
                created_at_str = f" ({delta.days} дн. назад)"
            elif delta.seconds > 3600:
                created_at_str = f" ({delta.seconds // 3600} ч. назад)"
            else:
                created_at_str = f" ({delta.seconds // 60} мин. назад)"
        
        text += (
            f"{i}. {em} <b>{app.tender.title}</b>\n"
            f"   Статус: {status_display}{created_at_str}\n"
            f"   Город: {app.tender.city} | Категория: {app.tender.category}\n\n"
        )
    
    if len(apps) > 5:
        text += f"\n... и ещё {len(apps) - 5} откликов\n"
    
    # Создаем клавиатуру с кнопками для просмотра деталей каждого отклика
    builder = InlineKeyboardBuilder()
    for app in apps[:5]:
        em = status_emoji.get(app.status, "•")
        builder.button(
            text=f"{em} {app.tender.title[:30]}...",
            callback_data=f"app_detail:{app.id}"
        )
    
    if len(apps) > 5:
        builder.button(
            text="📄 Показать все отклики",
            callback_data="app_list_all"
        )
    
    builder.button(
        text="🔄 Обновить",
        callback_data="my_applications"
    )
    builder.adjust(1)
    
    await answer_with_cleanup(
        message,
        text,
        reply_markup=builder.as_markup()
    )


@router.callback_query(F.data.startswith("app_detail:"))
async def application_detail_callback(
    callback: CallbackQuery,
    session: AsyncSession,
) -> None:
    """Детальный просмотр отклика пользователем."""
    app_id = parse_callback_id(callback.data, "app_detail:")
    if app_id is None:
        await callback.answer("Ошибка обработки запроса.", show_alert=True)
        return
    
    tg_id = callback.from_user.id
    result = await session.execute(select(User).where(User.tg_id == tg_id))
    user = result.scalar_one_or_none()
    
    if not user:
        await callback.answer("Пользователь не найден.", show_alert=True)
        return
    
    result = await session.execute(
        select(TenderApplication)
        .options(selectinload(TenderApplication.tender))
        .where(
            TenderApplication.id == app_id,
            TenderApplication.user_id == user.id,
        )
    )
    app = result.scalar_one_or_none()
    
    if not app:
        await callback.answer("Отклик не найден.", show_alert=True)
        return
    
    tender = app.tender
    
    status_emoji = {
        "applied": "⏳",
        "selected": "✅",
        "rejected": "❌",
        "completed": "✔️"
    }
    status_text = {
        "applied": "Ожидает рассмотрения",
        "selected": "Выбран исполнителем",
        "rejected": "Отклонён",
        "completed": "Завершён"
    }
    
    em = status_emoji.get(app.status, "•")
    status_display = status_text.get(app.status, app.status)
    
    # Форматируем даты
    created_at_str = "Не указана"
    if app.created_at:
        from datetime import datetime, timezone
        now = datetime.now(timezone.utc)
        app_date = app.created_at.replace(tzinfo=timezone.utc) if app.created_at.tzinfo is None else app.created_at
        created_at_str = app_date.strftime("%d.%m.%Y %H:%M")
    
    deadline_str = "Не указан"
    if tender.deadline:
        deadline_utc = tender.deadline
        if deadline_utc.tzinfo is None:
            deadline_utc = deadline_utc.replace(tzinfo=timezone.utc)
        deadline_str = deadline_utc.strftime("%d.%m.%Y %H:%M")
    
    text = (
        f"{em} <b>Детали отклика</b>\n\n"
        f"📋 <b>Тендер:</b> {tender.title}\n"
        f"📍 <b>Город:</b> {tender.city}\n"
        f"🏷️ <b>Категория:</b> {tender.category}\n"
        f"💰 <b>Бюджет:</b> {tender.budget or 'по договорённости'}\n"
        f"⏰ <b>Дедлайн тендера:</b> {deadline_str}\n\n"
        f"📊 <b>Статус отклика:</b> {status_display}\n"
        f"📅 <b>Дата отклика:</b> {created_at_str}\n\n"
        f"📝 <b>Описание тендера:</b>\n{tender.description}\n\n"
    )
    
    if app.status == "selected":
        text += "✅ <b>В скором времени с вами свяжется модератор</b> для уточнения деталей."
    elif app.status == "rejected":
        text += "❌ К сожалению, ваш отклик был отклонён. Попробуйте откликнуться на другие тендеры."
    elif app.status == "applied":
        text += "⏳ Ваш отклик находится на рассмотрении. Ожидайте решения заказчика."
    
    from handlers.keyboards import get_application_detail_kb
    kb = get_application_detail_kb(app.id, tender.id)
    
    await callback.message.edit_text(
        text=text,
        reply_markup=kb,
        parse_mode="HTML",
    )
    await callback.answer()


@router.callback_query(F.data == "app_list_all")
async def application_list_all_callback(
    callback: CallbackQuery,
    session: AsyncSession,
) -> None:
    """Показать все отклики пользователя."""
    # Просто вызываем обработчик "Мои отклики"
    await cmd_my_applications(callback, session, None)


@router.message(F.text == "🔍 Искать заказы")
async def cmd_find_tenders(message: Message, session: AsyncSession, state: FSMContext) -> None:
    """Поиск доступных тендеров для исполнителя."""
    # Отменяем FSM состояние, если оно активно
    current_state = await state.get_state()
    if current_state:
        await state.clear()
    
    result = await session.execute(select(User).where(User.tg_id == message.from_user.id))
    user = result.scalar_one_or_none()
    is_admin = message.from_user.id == settings.ADMIN_ID
    if not user:
        await answer_with_cleanup(
            message,
            "❌ <b>Профиль не найден</b>\n\n"
            "Сначала пройдите регистрацию.",
            reply_markup=get_main_menu_kb(None, is_admin),
        )
        return
    if await _require_active_user(message, user, is_admin):
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
            reply_markup=get_main_menu_kb(user.role, is_admin, is_pending_moderation=False),
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
            "Используйте команду /register или кнопку «📝 Пройти регистрацию» в меню.\n\n"
            "<b>Сколько времени занимает модерация?</b>\n"
            "Обычно модерация занимает от нескольких минут до 24 часов.\n\n"
            "<b>Как создать тендер?</b>\n"
            "Создание тендеров — через веб-админку (доступно администратору).\n\n"
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
