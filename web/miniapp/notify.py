# web/miniapp/notify.py — отправка уведомлений в Telegram через Bot API
import logging
from typing import Optional

import httpx
from config import settings

logger = logging.getLogger(__name__)


def send_telegram_message(
    chat_id: int,
    text: str,
    parse_mode: str = "HTML",
    reply_markup: Optional[dict] = None,
) -> bool:
    """
    Отправляет сообщение пользователю или в чат через Bot API.
    Используется для уведомлений из Mini App (отклик принят, тендер создан и т.д.).
    """
    url = f"https://api.telegram.org/bot{settings.BOT_TOKEN}/sendMessage"
    payload = {
        "chat_id": chat_id,
        "text": text[:4096],
        "parse_mode": parse_mode,
    }
    if reply_markup:
        payload["reply_markup"] = reply_markup
    try:
        with httpx.Client(timeout=10.0) as client:
            r = client.post(url, json=payload)
            if r.is_success:
                return True
            logger.warning("Telegram sendMessage failed: %s %s", r.status_code, r.text)
            return False
    except Exception as e:
        logger.exception("send_telegram_message error: %s", e)
        return False
