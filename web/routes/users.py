# web/routes/users.py
from fastapi import APIRouter, Request, Depends, Query
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy import select, func
from sqlalchemy.orm import Session
from pathlib import Path

from web.database import get_db
from web.auth import get_session_user
from database.models import User, Review

router = APIRouter()
templates = Jinja2Templates(directory=Path(__file__).parent.parent / "templates")


@router.get("", response_class=HTMLResponse)
async def users_list(
    request: Request,
    db: Session = Depends(get_db),
    role: str | None = Query(None),
    status: str | None = Query(None),
):
    if get_session_user(request) is None:
        return RedirectResponse(url="/login", status_code=302)
    q = select(User).order_by(User.id.desc())
    if role:
        q = q.where(User.role == role)
    if status:
        q = q.where(User.status == status)
    users = db.execute(q).scalars().all()
    result = db.execute(
        select(Review.to_user_id, func.avg(Review.rating), func.count(Review.id))
        .group_by(Review.to_user_id)
    )
    ratings = {row[0]: (float(row[1]) if row[1] else 0, row[2]) for row in result.all()}
    return templates.TemplateResponse(
        "users.html",
        {"request": request, "users": users, "ratings": ratings},
    )


@router.get("/{user_id}", response_class=HTMLResponse)
async def user_detail(
    request: Request,
    user_id: int,
    db: Session = Depends(get_db),
):
    if get_session_user(request) is None:
        return RedirectResponse(url="/login", status_code=302)
    user = db.execute(select(User).where(User.id == user_id)).scalar_one_or_none()
    if not user:
        return RedirectResponse(url="/users", status_code=302)
    return templates.TemplateResponse("user_detail.html", {"request": request, "user": user})
