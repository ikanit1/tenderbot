# web/auth.py — простая авторизация по паролю и сессия (cookie)
from typing import Optional

from fastapi import Depends, Request, Response
from fastapi.responses import RedirectResponse
from itsdangerous import URLSafeTimedSerializer, BadSignature

from config import settings

SECRET = settings.WEB_SECRET_KEY
serializer = URLSafeTimedSerializer(SECRET, salt="web-admin-session")


def get_session_user(request: Request) -> Optional[str]:
    """Возвращает логин из cookie или None."""
    token = request.cookies.get("session")
    if not token:
        return None
    try:
        data = serializer.loads(token, max_age=86400 * 7)  # 7 дней
        return data.get("user")
    except BadSignature:
        return None


def set_session(response: Response, user: str) -> None:
    response.set_cookie(
        "session",
        serializer.dumps({"user": user}),
        max_age=86400 * 7,
        httponly=True,
        samesite="lax",
    )


def clear_session(response: Response) -> None:
    response.delete_cookie("session")


def require_admin(request: Request) -> Optional[RedirectResponse]:
    """Проверка авторизации; при отсутствии — редирект на /login."""
    if get_session_user(request) is None:
        return RedirectResponse(url="/login", status_code=302)
    return None
