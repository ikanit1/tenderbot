# web/miniapp/auth.py — проверка initData от Telegram Web App
import hmac
import hashlib
import json
from urllib.parse import parse_qsl
from typing import Optional

from config import settings


def validate_init_data(init_data: str, max_age_sec: Optional[int] = 86400) -> Optional[dict]:
    """
    Проверяет подпись initData от Telegram Web App.
    https://core.telegram.org/bots/webapps#validating-data-received-via-the-mini-app

    Возвращает распарсенный dict с полями user, auth_date, hash и т.д. или None при ошибке.
    """
    if not init_data or not settings.BOT_TOKEN:
        return None
    try:
        parsed = dict(parse_qsl(init_data, keep_blank_values=True))
        received_hash = parsed.pop("hash", None)
        if not received_hash:
            return None
        # Сортируем и склеиваем key=value через \n
        data_check = "\n".join(
            f"{k}={v}" for k, v in sorted(parsed.items(), key=lambda x: x[0])
        )
        # secret_key = HMAC_SHA256(bot_token, "WebAppData")
        secret_key = hmac.new(
            b"WebAppData",
            settings.BOT_TOKEN.encode(),
            hashlib.sha256,
        ).digest()
        # calculated_hash = HMAC_SHA256(secret_key, data_check)
        calculated_hash = hmac.new(
            secret_key,
            data_check.encode(),
            hashlib.sha256,
        ).hexdigest()
        if not hmac.compare_digest(calculated_hash, received_hash):
            return None
        # Опционально проверка auth_date (не старше max_age_sec)
        if max_age_sec is not None:
            auth_date = parsed.get("auth_date")
            if auth_date:
                import time
                try:
                    ts = int(auth_date)
                    if abs(time.time() - ts) > max_age_sec:
                        return None
                except (ValueError, TypeError):
                    return None
        # user приходит как JSON-строка
        if "user" in parsed:
            try:
                parsed["user"] = json.loads(parsed["user"])
            except (json.JSONDecodeError, TypeError):
                pass
        return parsed
    except Exception:
        return None


def get_tg_id_from_init_data(init_data: str) -> Optional[int]:
    """Из валидного initData извлекает Telegram ID пользователя."""
    data = validate_init_data(init_data)
    if not data:
        return None
    user = data.get("user")
    if isinstance(user, dict) and "id" in user:
        return int(user["id"])
    return None
