# web/miniapp/routes.py — API для Telegram Mini App
from datetime import datetime, timezone
from typing import Optional

from fastapi import APIRouter, Depends, Header, HTTPException, Body
from fastapi.responses import FileResponse
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload
from pathlib import Path

from config import settings
from web.database import get_db
from web.miniapp.auth import get_tg_id_from_init_data
from web.miniapp.notify import send_telegram_message
from database.models import (
    User,
    Tender,
    TenderApplication,
    Review,
    UserStatus,
    UserRole,
    TenderStatus,
)

router = APIRouter(prefix="/miniapp", tags=["miniapp"])

# Зависимость: текущий пользователь по X-Telegram-Init-Data
def get_current_tg_id(
    x_telegram_init_data: Optional[str] = Header(None, alias="X-Telegram-Init-Data"),
) -> int:
    tg_id = get_tg_id_from_init_data(x_telegram_init_data or "")
    if tg_id is None:
        raise HTTPException(status_code=401, detail="Invalid or missing initData")
    return tg_id


def get_current_user(
    tg_id: int = Depends(get_current_tg_id),
    db: Session = Depends(get_db),
) -> User:
    result = db.execute(select(User).where(User.tg_id == tg_id))
    user = result.scalar_one_or_none()
    if not user:
        raise HTTPException(status_code=404, detail="User not found. Complete registration in the bot first.")
    return user


def require_active(user: User = Depends(get_current_user)) -> User:
    if user.status == UserStatus.BANNED.value:
        raise HTTPException(status_code=403, detail="Account blocked")
    return user


# ——— Раздача главной страницы Mini App ———
_MINIAPP_STATIC = Path(__file__).parent.parent / "static" / "miniapp"


@router.get("/", response_class=FileResponse)
def miniapp_index():
    """Отдаёт index.html Mini App."""
    index_path = _MINIAPP_STATIC / "index.html"
    if not index_path.exists():
        raise HTTPException(status_code=404, detail="Mini App not found")
    return FileResponse(index_path, media_type="text/html")


@router.get("/styles.css", response_class=FileResponse)
def miniapp_css():
    p = _MINIAPP_STATIC / "styles.css"
    if not p.exists():
        raise HTTPException(status_code=404)
    return FileResponse(p, media_type="text/css")


@router.get("/app.js", response_class=FileResponse)
def miniapp_js():
    p = _MINIAPP_STATIC / "app.js"
    if not p.exists():
        raise HTTPException(status_code=404)
    return FileResponse(p, media_type="application/javascript")


# ——— API: я (текущий пользователь) ———
@router.get("/api/me")
def api_me(
    user: User = Depends(get_current_user),
):
    """Текущий пользователь: есть ли в БД, статус, роль."""
    return {
        "id": user.id,
        "tg_id": user.tg_id,
        "full_name": user.full_name,
        "city": user.city,
        "phone": user.phone,
        "role": user.role,
        "status": user.status,
        "skills": user.skills or [],
        "birth_date": user.birth_date.isoformat() if user.birth_date else None,
        "created_at": user.created_at.isoformat() if user.created_at else None,
    }


# ——— API: профиль (GET/PATCH) ———
@router.get("/api/profile")
def api_profile_get(user: User = Depends(require_active)):
    return {
        "full_name": user.full_name,
        "city": user.city,
        "phone": user.phone,
        "skills": user.skills or [],
        "birth_date": user.birth_date.isoformat() if user.birth_date else None,
        "status": user.status,
        "role": user.role,
    }


class ProfileUpdate(BaseModel):
    full_name: Optional[str] = None
    city: Optional[str] = None
    phone: Optional[str] = None
    skills: Optional[list[str]] = None


@router.patch("/api/profile")
def api_profile_patch(
    body: ProfileUpdate = Body(default=ProfileUpdate()),
    user: User = Depends(require_active),
    db: Session = Depends(get_db),
):
    if body.full_name is not None:
        user.full_name = body.full_name.strip()[:256]
    if body.city is not None:
        user.city = body.city.strip()[:128]
    if body.phone is not None:
        user.phone = body.phone.strip()[:64]
    if body.skills is not None:
        user.skills = [s for s in body.skills if s][:20] or None
    db.commit()
    return {"ok": True}


# ——— API: список тендеров (открытые, по городу пользователя) ———
@router.get("/api/tenders")
def api_tenders_list(
    city: Optional[str] = None,
    category: Optional[str] = None,
    user: User = Depends(require_active),
    db: Session = Depends(get_db),
):
    q = (
        select(Tender)
        .where(Tender.status == TenderStatus.OPEN.value)
        .order_by(Tender.id.desc())
    )
    if city:
        q = q.where(Tender.city == city)
    else:
        q = q.where(Tender.city == user.city)
    if category:
        q = q.where(Tender.category == category)
    q = q.limit(50)
    result = db.execute(q)
    tenders = result.scalars().all()
    # Проверяем, откликался ли текущий пользователь на каждый
    out = []
    for t in tenders:
        app_result = db.execute(
            select(TenderApplication.id).where(
                TenderApplication.tender_id == t.id,
                TenderApplication.user_id == user.id,
            )
        )
        has_applied = app_result.scalar_one_or_none() is not None
        deadline_str = None
        if t.deadline:
            d = t.deadline
            if d.tzinfo is None:
                d = d.replace(tzinfo=timezone.utc)
            deadline_str = d.isoformat()
        out.append({
            "id": t.id,
            "title": t.title,
            "city": t.city,
            "category": t.category,
            "budget": t.budget,
            "description": t.description[:500] if t.description else "",
            "deadline": deadline_str,
            "status": t.status,
            "has_applied": has_applied,
        })
    return {"tenders": out}


# ——— API: один тендер ———
@router.get("/api/tenders/{tender_id}")
def api_tender_detail(
    tender_id: int,
    user: User = Depends(require_active),
    db: Session = Depends(get_db),
):
    result = db.execute(
        select(Tender).where(Tender.id == tender_id)
    )
    tender = result.scalar_one_or_none()
    if not tender:
        raise HTTPException(status_code=404, detail="Tender not found")
    app_result = db.execute(
        select(TenderApplication).where(
            TenderApplication.tender_id == tender_id,
            TenderApplication.user_id == user.id,
        )
    )
    my_application = app_result.scalar_one_or_none()
    deadline_str = None
    if tender.deadline:
        d = tender.deadline
        if d.tzinfo is None:
            d = d.replace(tzinfo=timezone.utc)
        deadline_str = d.isoformat()
    return {
        "id": tender.id,
        "title": tender.title,
        "city": tender.city,
        "category": tender.category,
        "budget": tender.budget,
        "description": tender.description,
        "deadline": deadline_str,
        "status": tender.status,
        "has_applied": my_application is not None,
        "application_id": my_application.id if my_application else None,
        "application_status": my_application.status if my_application else None,
    }


# ——— API: откликнуться на тендер ———
@router.post("/api/tenders/{tender_id}/apply")
def api_tender_apply(
  tender_id: int,
  user: User = Depends(require_active),
  db: Session = Depends(get_db),
):
    if user.role not in (UserRole.EXECUTOR.value, UserRole.BOTH.value):
        raise HTTPException(status_code=403, detail="Only executors can apply")
    result = db.execute(
        select(Tender)
        .options(selectinload(Tender.creator))
        .where(Tender.id == tender_id, Tender.status == TenderStatus.OPEN.value)
    )
    tender = result.scalar_one_or_none()
    if not tender:
        raise HTTPException(status_code=404, detail="Tender not found or closed")
    if tender.deadline:
        deadline_utc = tender.deadline
        if deadline_utc.tzinfo is None:
            deadline_utc = deadline_utc.replace(tzinfo=timezone.utc)
        if datetime.now(timezone.utc) > deadline_utc:
            raise HTTPException(status_code=400, detail="Deadline passed")
    existing = db.execute(
        select(TenderApplication).where(
            TenderApplication.tender_id == tender_id,
            TenderApplication.user_id == user.id,
        )
    ).scalar_one_or_none()
    if existing:
        raise HTTPException(status_code=400, detail="Already applied")
    app = TenderApplication(
        tender_id=tender_id,
        user_id=user.id,
        status="applied",
    )
    db.add(app)
    db.commit()
    db.refresh(app)
    # Уведомление пользователю в чат
    send_telegram_message(
        user.tg_id,
        f"✅ <b>Отклик отправлен</b>\n\n"
        f"Ваш отклик на тендер «{tender.title}» принят. "
        f"Ожидайте решения заказчика.\n\n"
        f"Откройте приложение, чтобы следить за статусом.",
    )
    # Уведомление админу
    skills_str = ", ".join(user.skills) if user.skills else "—"
    admin_text = (
        f"📩 <b>Новый отклик на тендер</b> «{tender.title}»\n\n"
        f"Исполнитель: {user.full_name}\n"
        f"Город: {user.city}\n"
        f"Телефон: {user.phone}\n"
        f"Навыки: {skills_str}\n"
        f"TG ID: {user.tg_id}"
    )
    send_telegram_message(settings.ADMIN_ID, admin_text)
    if tender.creator and tender.creator.tg_id != settings.ADMIN_ID:
        send_telegram_message(tender.creator.tg_id, admin_text)
    return {"ok": True, "application_id": app.id}


# ——— API: мои отклики ———
@router.get("/api/applications")
def api_my_applications(
    user: User = Depends(require_active),
    db: Session = Depends(get_db),
):
    result = db.execute(
        select(TenderApplication, Tender)
        .join(Tender, TenderApplication.tender_id == Tender.id)
        .where(TenderApplication.user_id == user.id)
        .order_by(TenderApplication.id.desc())
    )
    rows = result.all()
    out = []
    for app, tender in rows:
        deadline_str = None
        if tender.deadline:
            d = tender.deadline
            if d.tzinfo is None:
                d = d.replace(tzinfo=timezone.utc)
            deadline_str = d.isoformat()
        out.append({
            "id": app.id,
            "tender_id": tender.id,
            "tender_title": tender.title,
            "tender_city": tender.city,
            "tender_category": tender.category,
            "tender_budget": tender.budget,
            "status": app.status,
            "created_at": app.created_at.isoformat() if app.created_at else None,
            "deadline": deadline_str,
        })
    return {"applications": out}


@router.get("/api/applications/{application_id}")
def api_application_detail(
    application_id: int,
    user: User = Depends(require_active),
    db: Session = Depends(get_db),
):
    result = db.execute(
        select(TenderApplication, Tender)
        .join(Tender, TenderApplication.tender_id == Tender.id)
        .where(
            TenderApplication.id == application_id,
            TenderApplication.user_id == user.id,
        )
    )
    row = result.one_or_none()
    if not row:
        raise HTTPException(status_code=404, detail="Application not found")
    app, tender = row
    deadline_str = None
    if tender.deadline:
        d = tender.deadline
        if d.tzinfo is None:
            d = d.replace(tzinfo=timezone.utc)
        deadline_str = d.isoformat()
    return {
        "id": app.id,
        "tender_id": tender.id,
        "tender_title": tender.title,
        "tender_city": tender.city,
        "tender_category": tender.category,
        "tender_budget": tender.budget,
        "tender_description": tender.description,
        "status": app.status,
        "created_at": app.created_at.isoformat() if app.created_at else None,
        "deadline": deadline_str,
    }


# ——— API: навыки (категории) для выбора в профиле ———
@router.get("/api/skills")
def api_skills():
    return {"skills": settings.SKILL_TAGS}
