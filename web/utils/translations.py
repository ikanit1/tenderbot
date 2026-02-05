# web/utils/translations.py — Переводы статусов и ролей на русский язык

# Словари переводов
STATUS_TRANSLATIONS = {
    # Статусы пользователей
    "active": "Активен",
    "pending_moderation": "На модерации",
    "banned": "Заблокирован",
    # Статусы тендеров
    "draft": "Черновик",
    "open": "Открыт",
    "in_progress": "В работе",
    "closed": "Закрыт",
    # Статусы откликов
    "applied": "Подано",
    "selected": "Выбран",
    "rejected": "Отклонён",
    # Статусы тикетов
    "new": "Новый",
    "in_progress": "В процессе",
    "closed": "Закрыт",
}

ROLE_TRANSLATIONS = {
    "executor": "Исполнитель",
    "customer": "Заказчик",
    "admin": "Администратор",
}

# Человекочитаемые названия полей
FIELD_LABELS = {
    "id": "ID",
    "tg_id": "Telegram ID",
    "full_name": "ФИО",
    "role": "Роль",
    "status": "Статус",
    "city": "Город",
    "phone": "Телефон",
    "birth_date": "Дата рождения",
    "skills": "Навыки",
    "created_at": "Дата регистрации",
    "title": "Название",
    "category": "Категория",
    "budget": "Бюджет",
    "description": "Описание",
    "deadline": "Дедлайн",
    "rating": "Оценка",
    "comment": "Комментарий",
    "text": "Текст",
    "author": "Автор",
}


def translate_status(status: str) -> str:
    """Переводит статус на русский язык."""
    if not status:
        return "—"
    return STATUS_TRANSLATIONS.get(status.lower(), status)


def translate_role(role: str) -> str:
    """Переводит роль на русский язык."""
    if not role:
        return "—"
    return ROLE_TRANSLATIONS.get(role.lower(), role)


def translate_field(field_name: str) -> str:
    """Переводит название поля на русский язык."""
    return FIELD_LABELS.get(field_name.lower(), field_name)


def humanize_status(status: str) -> str:
    """Делает статус более читаемым (с заглавной буквы)."""
    translated = translate_status(status)
    return translated.capitalize() if translated else "—"


def humanize_role(role: str) -> str:
    """Делает роль более читаемой."""
    return translate_role(role)


def format_datetime(dt, format_str="%d.%m.%Y %H:%M"):
    """Форматирует datetime в читаемый формат."""
    if not dt:
        return "—"
    try:
        return dt.strftime(format_str)
    except:
        return str(dt)


def format_date(dt, format_str="%d.%m.%Y"):
    """Форматирует дату в читаемый формат."""
    if not dt:
        return "—"
    try:
        return dt.strftime(format_str)
    except:
        return str(dt)
