# web/routes/applications.py
from fastapi import APIRouter, Request, Depends, Query
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload
from pathlib import Path

from web.database import get_db
from web.auth import get_session_user
from database.models import TenderApplication

router = APIRouter()
templates = Jinja2Templates(directory=Path(__file__).parent.parent / "templates")


@router.get("", response_class=HTMLResponse)
async def applications_list(
    request: Request,
    db: Session = Depends(get_db),
    status: str | None = Query(None),
):
    if get_session_user(request) is None:
        return RedirectResponse(url="/login", status_code=302)
    q = (
        select(TenderApplication)
        .options(
            selectinload(TenderApplication.tender),
            selectinload(TenderApplication.user),
        )
        .order_by(TenderApplication.id.desc())
    )
    if status:
        q = q.where(TenderApplication.status == status)
    applications = db.execute(q).scalars().all()
    return templates.TemplateResponse(
        "applications.html",
        {"request": request, "applications": applications},
    )
