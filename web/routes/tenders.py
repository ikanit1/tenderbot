# web/routes/tenders.py
import logging
from datetime import datetime, timezone
from typing import Annotated

from fastapi import APIRouter, Request, Depends, Query, Form, HTTPException
from fastapi.responses import HTMLResponse, RedirectResponse
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, selectinload

from web.database import get_db
from web.auth import get_session_user
from web.templates_loader import templates
from database.models import Tender, User, TenderStatus, TenderApplication
from config import settings
from utils.validators import validate_string_length, validate_date_range

logger = logging.getLogger(__name__)

router = APIRouter()


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
    
    # Валидация длины полей
    if title:
        is_valid, error_msg = validate_string_length(title, max_length=256, field_name="Название")
        if not is_valid:
            return templates.TemplateResponse(
                "tender_form.html",
                {
                    "request": request,
                    "tender": None,
                    "skill_tags": settings.SKILL_TAGS,
                    "statuses": [s.value for s in TenderStatus],
                    "error": error_msg,
                },
            )
    
    if category:
        is_valid, error_msg = validate_string_length(category, max_length=128, field_name="Категория")
        if not is_valid:
            return templates.TemplateResponse(
                "tender_form.html",
                {
                    "request": request,
                    "tender": None,
                    "skill_tags": settings.SKILL_TAGS,
                    "statuses": [s.value for s in TenderStatus],
                    "error": error_msg,
                },
            )
    
    if city:
        is_valid, error_msg = validate_string_length(city, max_length=128, field_name="Город")
        if not is_valid:
            return templates.TemplateResponse(
                "tender_form.html",
                {
                    "request": request,
                    "tender": None,
                    "skill_tags": settings.SKILL_TAGS,
                    "statuses": [s.value for s in TenderStatus],
                    "error": error_msg,
                },
            )
    
    if budget:
        is_valid, error_msg = validate_string_length(budget, max_length=128, field_name="Бюджет")
        if not is_valid:
            return templates.TemplateResponse(
                "tender_form.html",
                {
                    "request": request,
                    "tender": None,
                    "skill_tags": settings.SKILL_TAGS,
                    "statuses": [s.value for s in TenderStatus],
                    "error": error_msg,
                },
            )
    
    deadline_dt = None
    if deadline:
        try:
            deadline_dt = datetime.strptime(deadline, "%Y-%m-%dT%H:%M").replace(tzinfo=timezone.utc)
            # Валидация: deadline не должен быть в прошлом
            now_utc = datetime.now(timezone.utc)
            if deadline_dt < now_utc:
                return templates.TemplateResponse(
                    "tender_form.html",
                    {
                        "request": request,
                        "tender": None,
                        "skill_tags": settings.SKILL_TAGS,
                        "statuses": [s.value for s in TenderStatus],
                        "error": "Срок приёма откликов не может быть в прошлом",
                    },
                )
        except ValueError:
            return templates.TemplateResponse(
                "tender_form.html",
                {
                    "request": request,
                    "tender": None,
                    "skill_tags": settings.SKILL_TAGS,
                    "statuses": [s.value for s in TenderStatus],
                    "error": "Неверный формат даты",
                },
            )
    
    try:
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
        logger.info(f"Tender {tender.id} created via web interface")
        return RedirectResponse(url=f"/tenders/{tender.id}", status_code=302)
    except IntegrityError as e:
        db.rollback()
        logger.error(f"Database error creating tender: {e}")
        return templates.TemplateResponse(
            "tender_form.html",
            {
                "request": request,
                "tender": None,
                "skill_tags": settings.SKILL_TAGS,
                "statuses": [s.value for s in TenderStatus],
                "error": "Ошибка сохранения тендера. Попробуйте снова.",
            },
        )


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
        logger.warning(f"Attempt to edit non-existent tender {tender_id}")
        return RedirectResponse(url="/tenders", status_code=302)
    
    # Валидация длины полей
    if title:
        is_valid, error_msg = validate_string_length(title, max_length=256, field_name="Название")
        if not is_valid:
            return templates.TemplateResponse(
                "tender_form.html",
                {
                    "request": request,
                    "tender": tender,
                    "skill_tags": settings.SKILL_TAGS,
                    "statuses": [s.value for s in TenderStatus],
                    "error": error_msg,
                },
            )
    
    if category:
        is_valid, error_msg = validate_string_length(category, max_length=128, field_name="Категория")
        if not is_valid:
            return templates.TemplateResponse(
                "tender_form.html",
                {
                    "request": request,
                    "tender": tender,
                    "skill_tags": settings.SKILL_TAGS,
                    "statuses": [s.value for s in TenderStatus],
                    "error": error_msg,
                },
            )
    
    if city:
        is_valid, error_msg = validate_string_length(city, max_length=128, field_name="Город")
        if not is_valid:
            return templates.TemplateResponse(
                "tender_form.html",
                {
                    "request": request,
                    "tender": tender,
                    "skill_tags": settings.SKILL_TAGS,
                    "statuses": [s.value for s in TenderStatus],
                    "error": error_msg,
                },
            )
    
    if budget:
        is_valid, error_msg = validate_string_length(budget, max_length=128, field_name="Бюджет")
        if not is_valid:
            return templates.TemplateResponse(
                "tender_form.html",
                {
                    "request": request,
                    "tender": tender,
                    "skill_tags": settings.SKILL_TAGS,
                    "statuses": [s.value for s in TenderStatus],
                    "error": error_msg,
                },
            )
    
    try:
        tender.title = title
        tender.category = category
        tender.city = city
        tender.budget = budget
        tender.description = description
        
        if deadline:
            try:
                deadline_dt = datetime.strptime(deadline, "%Y-%m-%dT%H:%M").replace(tzinfo=timezone.utc)
                # Валидация: deadline не должен быть в прошлом
                now_utc = datetime.now(timezone.utc)
                if deadline_dt < now_utc:
                    return templates.TemplateResponse(
                        "tender_form.html",
                        {
                            "request": request,
                            "tender": tender,
                            "skill_tags": settings.SKILL_TAGS,
                            "statuses": [s.value for s in TenderStatus],
                            "error": "Срок приёма откликов не может быть в прошлом",
                        },
                    )
                tender.deadline = deadline_dt
            except ValueError:
                return templates.TemplateResponse(
                    "tender_form.html",
                    {
                        "request": request,
                        "tender": tender,
                        "skill_tags": settings.SKILL_TAGS,
                        "statuses": [s.value for s in TenderStatus],
                        "error": "Неверный формат даты",
                    },
                )
        else:
            tender.deadline = None
        
        if status:
            tender.status = status
        
        db.commit()
        logger.info(f"Tender {tender_id} updated via web interface")
        return RedirectResponse(url=f"/tenders/{tender.id}", status_code=302)
    except IntegrityError as e:
        db.rollback()
        logger.error(f"Database error updating tender {tender_id}: {e}")
        return templates.TemplateResponse(
            "tender_form.html",
            {
                "request": request,
                "tender": tender,
                "skill_tags": settings.SKILL_TAGS,
                "statuses": [s.value for s in TenderStatus],
                "error": "Ошибка сохранения изменений. Попробуйте снова.",
            },
        )


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
        try:
            db.delete(tender)
            db.commit()
            logger.info(f"Tender {tender_id} deleted via web interface")
        except Exception as e:
            db.rollback()
            logger.error(f"Error deleting tender {tender_id}: {e}")
    else:
        logger.warning(f"Attempt to delete non-existent tender {tender_id}")
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
