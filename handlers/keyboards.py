# handlers/keyboards.py — клавиатуры для удобного интерфейса
from aiogram.types import (
    InlineKeyboardMarkup,
    InlineKeyboardButton,
    ReplyKeyboardMarkup,
    KeyboardButton,
)
from aiogram.utils.keyboard import InlineKeyboardBuilder, ReplyKeyboardBuilder
from config import settings
from database.models import UserRole, UserStatus, TenderStatus


def get_main_menu_kb(user_role: str | None = None, is_admin: bool = False) -> ReplyKeyboardMarkup:
    """Главное меню для исполнителей."""
    builder = ReplyKeyboardBuilder()
    
    if user_role == UserRole.EXECUTOR.value:
        builder.button(text="📋 Мои отклики")
        builder.button(text="👤 Профиль")
        builder.button(text="🔍 Найти тендеры")
    else:
        builder.button(text="📝 Регистрация")
    
    if is_admin:
        builder.button(text="⚙️ Админ-панель")
    
    builder.button(text="ℹ️ Помощь")
    builder.adjust(2, 1)
    return builder.as_markup(
        resize_keyboard=True,
        is_persistent=True,  # Меню всегда видно
        one_time_keyboard=False,  # Меню не скрывается после использования
    )


def get_admin_menu_kb() -> ReplyKeyboardMarkup:
    """Меню для администратора."""
    builder = ReplyKeyboardBuilder()
    builder.button(text="👥 Модерация")
    builder.button(text="👷 Рабочие")
    builder.button(text="📊 Статистика")
    builder.button(text="🏠 Главное меню")
    builder.adjust(2, 2, 1)
    return builder.as_markup(
        resize_keyboard=True,
        is_persistent=True,  # Меню всегда видно
        one_time_keyboard=False,  # Меню не скрывается после использования
    )




def get_skills_kb(selected_skills: list[str] | None = None) -> InlineKeyboardMarkup:
    """Клавиатура выбора навыков."""
    selected_skills = selected_skills or []
    builder = InlineKeyboardBuilder()
    
    for tag in settings.SKILL_TAGS:
        prefix = "✅ " if tag in selected_skills else ""
        builder.button(
            text=f"{prefix}{tag}",
            callback_data=f"skill:{tag}"
        )
    
    builder.button(
        text="✅ Готово",
        callback_data="skill:done"
    )
    builder.adjust(2)
    return builder.as_markup()


def get_moderation_kb(user_id: int) -> InlineKeyboardMarkup:
    """Клавиатура для модерации пользователя."""
    builder = InlineKeyboardBuilder()
    builder.button(
        text="✅ Одобрить",
        callback_data=f"mod_approve:{user_id}"
    )
    builder.button(
        text="❌ Отклонить",
        callback_data=f"mod_reject:{user_id}"
    )
    builder.button(
        text="👁️ Просмотр профиля",
        callback_data=f"mod_view:{user_id}"
    )
    builder.adjust(2, 1)
    return builder.as_markup()


def get_tender_actions_kb(tender_id: int, status: str) -> InlineKeyboardMarkup:
    """Клавиатура действий с тендером."""
    builder = InlineKeyboardBuilder()
    
    if status == TenderStatus.DRAFT.value:
        builder.button(
            text="📢 Опубликовать",
            callback_data=f"publish:{tender_id}"
        )
        builder.button(
            text="✏️ Редактировать",
            callback_data=f"edit_tender:{tender_id}"
        )
    elif status == TenderStatus.OPEN.value:
        builder.button(
            text="👁️ Просмотр откликов",
            callback_data=f"view_apps:{tender_id}"
        )
        builder.button(
            text="🔒 Закрыть",
            callback_data=f"close_tender:{tender_id}"
        )
        builder.button(
            text="❌ Отменить",
            callback_data=f"cancel_tender:{tender_id}"
        )
    elif status == TenderStatus.IN_PROGRESS.value:
        builder.button(
            text="👁️ Просмотр откликов",
            callback_data=f"view_apps:{tender_id}"
        )
        builder.button(
            text="✅ Завершить",
            callback_data=f"complete_tender:{tender_id}"
        )
    
    builder.adjust(2, 1)
    return builder.as_markup()


def get_tender_list_kb(tender_id: int, can_apply: bool = True) -> InlineKeyboardMarkup:
    """Клавиатура для списка тендеров."""
    builder = InlineKeyboardBuilder()
    
    if can_apply:
        builder.button(
            text="📩 Откликнуться",
            callback_data=f"apply:{tender_id}"
        )
    
    builder.button(
        text="👁️ Подробнее",
        callback_data=f"tender_detail:{tender_id}"
    )
    builder.adjust(1)
    return builder.as_markup()


def get_pagination_kb(
    page: int,
    total_pages: int,
    prefix: str,
    item_id: int | None = None
) -> InlineKeyboardMarkup:
    """Клавиатура пагинации."""
    builder = InlineKeyboardBuilder()
    
    if page > 1:
        builder.button(
            text="◀️ Назад",
            callback_data=f"{prefix}_page:{page - 1}"
        )
    
    builder.button(
        text=f"📄 {page}/{total_pages}",
        callback_data="page_info"
    )
    
    if page < total_pages:
        builder.button(
            text="Вперёд ▶️",
            callback_data=f"{prefix}_page:{page + 1}"
        )
    
    builder.adjust(3)
    return builder.as_markup()


def get_application_actions_kb(application_id: int, tender_id: int) -> InlineKeyboardMarkup:
    """Клавиатура действий с откликом."""
    builder = InlineKeyboardBuilder()
    builder.button(
        text="✅ Выбрать исполнителя",
        callback_data=f"select_user:{application_id}"
    )
    builder.button(
        text="❌ Отклонить",
        callback_data=f"reject_app:{application_id}"
    )
    builder.button(
        text="👁️ Профиль исполнителя",
        callback_data=f"user_profile:{application_id}"
    )
    builder.button(
        text="📋 К тендеру",
        callback_data=f"tender_detail:{tender_id}"
    )
    builder.adjust(2, 1, 1)
    return builder.as_markup()


def get_profile_edit_kb() -> InlineKeyboardMarkup:
    """Клавиатура редактирования профиля."""
    builder = InlineKeyboardBuilder()
    builder.button(text="✏️ Редактировать", callback_data="edit_profile")
    builder.button(text="📋 Мои отклики", callback_data="my_applications")
    builder.adjust(1)
    return builder.as_markup()


def get_help_kb() -> InlineKeyboardMarkup:
    """Клавиатура помощи."""
    builder = InlineKeyboardBuilder()
    builder.button(text="📖 Команды", callback_data="help_commands")
    builder.button(text="❓ FAQ", callback_data="help_faq")
    builder.button(text="📞 Поддержка", callback_data="help_support")
    builder.adjust(1)
    return builder.as_markup()

