# web/routes/reviews.py
from fastapi import APIRouter, Request, Depends
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy import select, func
from sqlalchemy.orm import Session
from pathlib import Path

from web.database import get_db
from web.auth import get_session_user
from database.models import Review, User

router = APIRouter()
templates = Jinja2Templates(directory=Path(__file__).parent.parent / "templates")


@router.get("", response_class=HTMLResponse)
async def reviews_list(
    request: Request,
    db: Session = Depends(get_db),
):
    if get_session_user(request) is None:
        return RedirectResponse(url="/login", status_code=302)
    reviews = db.execute(
        select(Review).order_by(Review.created_at.desc()).limit(100)
    ).scalars().all()
    result = db.execute(
        select(Review.to_user_id, func.avg(Review.rating), func.count(Review.id))
        .group_by(Review.to_user_id)
    )
    avg_by_user = {row[0]: (float(row[1]) if row[1] else 0, row[2]) for row in result.all()}
    return templates.TemplateResponse(
        "reviews.html",
        {"request": request, "reviews": reviews, "avg_by_user": avg_by_user},
    )
