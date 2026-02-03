# web/routes/dashboard.py
from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Request, Depends
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy import select, func
from sqlalchemy.orm import Session
from pathlib import Path

from web.database import get_db
from web.auth import get_session_user
from database.models import User, Tender, TenderApplication, Review

router = APIRouter()
templates = Jinja2Templates(directory=Path(__file__).parent.parent / "templates")


@router.get("/dashboard", response_class=HTMLResponse)
async def dashboard(
    request: Request,
    db: Session = Depends(get_db),
):
    if get_session_user(request) is None:
        return RedirectResponse(url="/login", status_code=302)
    now = datetime.now(timezone.utc)
    today = now.replace(hour=0, minute=0, second=0, microsecond=0)
    week_ago = today - timedelta(days=7)
    users_total = db.execute(select(func.count(User.id))).scalar() or 0
    tenders_total = db.execute(select(func.count(Tender.id))).scalar() or 0
    apps_today = db.execute(
        select(func.count(TenderApplication.id)).where(TenderApplication.created_at >= today)
    ).scalar() or 0
    apps_week = db.execute(
        select(func.count(TenderApplication.id)).where(TenderApplication.created_at >= week_ago)
    ).scalar() or 0
    users_by_role = db.execute(
        select(User.role, func.count(User.id)).group_by(User.role)
    ).all()
    tenders_by_status = db.execute(
        select(Tender.status, func.count(Tender.id)).group_by(Tender.status)
    ).all()
    recent_users = db.execute(
        select(User).order_by(User.created_at.desc()).limit(5)
    ).scalars().all()
    recent_tenders = db.execute(
        select(Tender).order_by(Tender.created_at.desc()).limit(5)
    ).scalars().all()
    return templates.TemplateResponse(
        "dashboard.html",
        {
            "request": request,
            "users_total": users_total,
            "tenders_total": tenders_total,
            "apps_today": apps_today,
            "apps_week": apps_week,
            "users_by_role": users_by_role,
            "tenders_by_status": tenders_by_status,
            "recent_users": recent_users,
            "recent_tenders": recent_tenders,
        },
    )
