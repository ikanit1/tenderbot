# web/routes/tenders.py
from fastapi import APIRouter, Request, Depends, Query
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload
from pathlib import Path

from web.database import get_db
from web.auth import get_session_user
from database.models import Tender, User

router = APIRouter()
templates = Jinja2Templates(directory=Path(__file__).parent.parent / "templates")


@router.get("", response_class=HTMLResponse)
async def tenders_list(
    request: Request,
    db: Session = Depends(get_db),
    status: str | None = Query(None),
):
    if get_session_user(request) is None:
        return RedirectResponse(url="/login", status_code=302)
    q = select(Tender).options(selectinload(Tender.creator)).order_by(Tender.id.desc())
    if status:
        q = q.where(Tender.status == status)
    tenders = db.execute(q).scalars().all()
    return templates.TemplateResponse(
        "tenders.html",
        {"request": request, "tenders": tenders},
    )


@router.get("/{tender_id}", response_class=HTMLResponse)
async def tender_detail(
    request: Request,
    tender_id: int,
    db: Session = Depends(get_db),
):
    if get_session_user(request) is None:
        return RedirectResponse(url="/login", status_code=302)
    tender = db.execute(
        select(Tender)
        .options(selectinload(Tender.creator), selectinload(Tender.applications))
        .where(Tender.id == tender_id)
    ).scalar_one_or_none()
    if not tender:
        return RedirectResponse(url="/tenders", status_code=302)
    return templates.TemplateResponse("tender_detail.html", {"request": request, "tender": tender})
