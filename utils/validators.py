# utils/validators.py — валидация входных данных
import logging
from typing import Optional, Tuple

logger = logging.getLogger(__name__)


def parse_callback_id(callback_data: str, prefix: str) -> Optional[int]:
    """
    Безопасный парсинг ID из callback_data.
    Возвращает ID или None при ошибке.
    
    Args:
        callback_data: Данные callback (например, "mod_approve:123")
        prefix: Префикс для удаления (например, "mod_approve:")
    
    Returns:
        ID как int или None при ошибке
    """
    try:
        if not callback_data.startswith(prefix):
            logger.warning(f"Invalid callback prefix: {callback_data[:50]}")
            return None
        id_str = callback_data.replace(prefix, "").strip()
        if not id_str or not id_str.isdigit():
            logger.warning(f"Invalid callback ID format: {id_str}")
            return None
        return int(id_str)
    except (ValueError, AttributeError) as e:
        logger.error(f"Error parsing callback ID from '{callback_data[:50]}': {e}")
        return None


def parse_callback_parts(callback_data: str, prefix: str, expected_parts: int = 1) -> Optional[Tuple]:
    """
    Безопасный парсинг нескольких частей из callback_data.
    Возвращает кортеж частей или None при ошибке.
    
    Args:
        callback_data: Данные callback (например, "tenders_page:all:5")
        prefix: Префикс для удаления (например, "tenders_page:")
        expected_parts: Ожидаемое количество частей после префикса
    
    Returns:
        Кортеж частей или None при ошибке
    """
    try:
        if not callback_data.startswith(prefix):
            logger.warning(f"Invalid callback prefix: {callback_data[:50]}")
            return None
        data_str = callback_data.replace(prefix, "").strip()
        parts = data_str.split(":")
        if len(parts) < expected_parts:
            logger.warning(f"Not enough parts in callback: {callback_data[:50]}")
            return None
        return tuple(parts)
    except (ValueError, AttributeError) as e:
        logger.error(f"Error parsing callback parts from '{callback_data[:50]}': {e}")
        return None


def validate_string_length(value: str, max_length: int, field_name: str = "field") -> Tuple[bool, Optional[str]]:
    """
    Валидация длины строки.
    
    Args:
        value: Строка для проверки
        max_length: Максимальная длина
        field_name: Имя поля для сообщения об ошибке
    
    Returns:
        (is_valid, error_message)
    """
    if not isinstance(value, str):
        return False, f"{field_name} должно быть строкой"
    if len(value) > max_length:
        return False, f"{field_name} слишком длинное (максимум {max_length} символов)"
    if len(value.strip()) == 0:
        return False, f"{field_name} не может быть пустым"
    return True, None


def validate_date_range(date_value, min_date=None, max_date=None, field_name: str = "дата") -> Tuple[bool, Optional[str]]:
    """
    Валидация диапазона даты.
    
    Args:
        date_value: Дата для проверки
        min_date: Минимальная дата
        max_date: Максимальная дата
        field_name: Имя поля для сообщения об ошибке
    
    Returns:
        (is_valid, error_message)
    """
    if date_value is None:
        return True, None
    
    if min_date and date_value < min_date:
        return False, f"{field_name} не может быть раньше {min_date.strftime('%d.%m.%Y')}"
    if max_date and date_value > max_date:
        return False, f"{field_name} не может быть позже {max_date.strftime('%d.%m.%Y')}"
    
    return True, None
