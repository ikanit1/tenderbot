# utils — общие утилиты
from config import settings


def is_admin(tg_id: int) -> bool:
    """Проверка, является ли пользователь администратором."""
    return tg_id == settings.ADMIN_ID

