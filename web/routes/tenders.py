# web/routes/tenders.py
from datetime import datetime, timezone
from typing import Annotated

from fastapi import APIRouter, Request, Depends, Query, Form
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload
from pathlib import Path

from web.database import get_db
from web.auth import get_session_user
from database.models import Tender, User, TenderStatus, TenderApplication
from config import settings

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
        {
            "request": request,
            "tenders": tenders,
            "statuses": [s.value for s in TenderStatus],
        },
    )


@router.get("/create", response_class=HTMLResponse)
async def tender_create_form(
    request: Request,
    db: Session = Depends(get_db),
):
    if get_session_user(request) is None:
        return RedirectResponse(url="/login", status_code=302)
    return templates.TemplateResponse(
        "tender_form.html",
        {
            "request": request,
            "tender": None,
            "skill_tags": settings.SKILL_TAGS,
            "statuses": [s.value for s in TenderStatus],
        },
    )


@router.post("/create", response_class=HTMLResponse)
async def tender_create(
    request: Request,
    db: Session = Depends(get_db),
    title: Annotated[str, Form()] = None,
    category: Annotated[str, Form()] = None,
    city: Annotated[str, Form()] = None,
    budget: Annotated[str | None, Form()] = None,
    description: Annotated[str, Form()] = None,
    deadline: Annotated[str | None, Form()] = None,
    status: Annotated[str, Form()] = TenderStatus.DRAFT.value,
):
    if get_session_user(request) is None:
        return RedirectResponse(url="/login", status_code=302)
    
    deadline_dt = None
    if deadline:
        try:
            deadline_dt = datetime.strptime(deadline, "%Y-%m-%dT%H:%M").replace(tzinfo=timezone.utc)
        except ValueError:
            pass
    
    tender = Tender(
        title=title,
        category=category,
        city=city,
        budget=budget,
        description=description,
        deadline=deadline_dt,
        status=status,
        created_by_tg_id=settings.ADMIN_ID,
    )
    db.add(tender)
    db.commit()
    db.refresh(tender)
    return RedirectResponse(url=f"/tenders/{tender.id}", status_code=302)


@router.get("/{tender_id}/edit", response_class=HTMLResponse)
async def tender_edit_form(
    request: Request,
    tender_id: int,
    db: Session = Depends(get_db),
):
    if get_session_user(request) is None:
        return RedirectResponse(url="/login", status_code=302)
    tender = db.execute(select(Tender).where(Tender.id == tender_id)).scalar_one_or_none()
    if not tender:
        return RedirectResponse(url="/tenders", status_code=302)
    return templates.TemplateResponse(
        "tender_form.html",
        {
            "request": request,
            "tender": tender,
            "skill_tags": settings.SKILL_TAGS,
            "statuses": [s.value for s in TenderStatus],
        },
    )


@router.post("/{tender_id}/edit", response_class=HTMLResponse)
async def tender_update(
    request: Request,
    tender_id: int,
    db: Session = Depends(get_db),
    title: Annotated[str, Form()] = None,
    category: Annotated[str, Form()] = None,
    city: Annotated[str, Form()] = None,
    budget: Annotated[str | None, Form()] = None,
    description: Annotated[str, Form()] = None,
    deadline: Annotated[str | None, Form()] = None,
    status: Annotated[str, Form()] = None,
):
    if get_session_user(request) is None:
        return RedirectResponse(url="/login", status_code=302)
    
    tender = db.execute(select(Tender).where(Tender.id == tender_id)).scalar_one_or_none()
    if not tender:
        return RedirectResponse(url="/tenders", status_code=302)
    
    tender.title = title
    tender.category = category
    tender.city = city
    tender.budget = budget
    tender.description = description
    
    if deadline:
        try:
            tender.deadline = datetime.strptime(deadline, "%Y-%m-%dT%H:%M").replace(tzinfo=timezone.utc)
        except ValueError:
            pass
    else:
        tender.deadline = None
    
    if status:
        tender.status = status
    
    db.commit()
    return RedirectResponse(url=f"/tenders/{tender.id}", status_code=302)


@router.post("/{tender_id}/status", response_class=HTMLResponse)
async def tender_change_status(
    request: Request,
    tender_id: int,
    db: Session = Depends(get_db),
    new_status: Annotated[str, Form()] = None,
):
    if get_session_user(request) is None:
        return RedirectResponse(url="/login", status_code=302)
    
    tender = db.execute(select(Tender).where(Tender.id == tender_id)).scalar_one_or_none()
    if not tender:
        return RedirectResponse(url="/tenders", status_code=302)
    
    if new_status in [s.value for s in TenderStatus]:
        tender.status = new_status
        db.commit()
    
    return RedirectResponse(url=f"/tenders/{tender_id}", status_code=302)


@router.post("/{tender_id}/delete", response_class=RedirectResponse)
async def tender_delete(
    request: Request,
    tender_id: int,
    db: Session = Depends(get_db),
):
    """Удалить тендер (каскадно удалятся отклики)."""
    if get_session_user(request) is None:
        return RedirectResponse(url="/login", status_code=302)
    tender = db.execute(select(Tender).where(Tender.id == tender_id)).scalar_one_or_none()
    if tender:
        db.delete(tender)
        db.commit()
    return RedirectResponse(url="/tenders", status_code=302)


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
        .options(selectinload(Tender.creator), selectinload(Tender.applications).selectinload(TenderApplication.user))
        .where(Tender.id == tender_id)
    ).scalar_one_or_none()
    if not tender:
        return RedirectResponse(url="/tenders", status_code=302)
    return templates.TemplateResponse(
        "tender_detail.html",
        {
            "request": request,
            "tender": tender,
            "statuses": [s.value for s in TenderStatus],
        },
    )
