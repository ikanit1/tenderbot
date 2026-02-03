# web/routes/applications_manage.py — управление откликами
from fastapi import APIRouter, Request, Depends, Form
from fastapi.responses import HTMLResponse, RedirectResponse
from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload
from typing import Annotated

from web.database import get_db
from web.auth import get_session_user
from database.models import TenderApplication, Tender, TenderStatus

router = APIRouter()


@router.post("/applications/{application_id}/select", response_class=HTMLResponse)
async def select_application(
    request: Request,
    application_id: int,
    db: Session = Depends(get_db),
):
    """Выбрать исполнителя по отклику."""
    if get_session_user(request) is None:
        return RedirectResponse(url="/login", status_code=302)
    
    app = db.execute(
        select(TenderApplication)
        .options(selectinload(TenderApplication.tender), selectinload(TenderApplication.user))
        .where(TenderApplication.id == application_id)
    ).scalar_one_or_none()
    
    if not app:
        return RedirectResponse(url="/applications", status_code=302)
    
    # Обновляем статус отклика
    app.status = "selected"
    
    # Обновляем статус тендера
    app.tender.status = TenderStatus.IN_PROGRESS.value
    
    # Отклоняем остальные отклики
    other_apps = db.execute(
        select(TenderApplication).where(
            TenderApplication.tender_id == app.tender_id,
            TenderApplication.id != app.id,
        )
    ).scalars().all()
    for other in other_apps:
        other.status = "rejected"
    
    db.commit()
    return RedirectResponse(url=f"/tenders/{app.tender_id}", status_code=302)


@router.post("/applications/{application_id}/reject", response_class=HTMLResponse)
async def reject_application(
    request: Request,
    application_id: int,
    db: Session = Depends(get_db),
):
    """Отклонить отклик."""
    if get_session_user(request) is None:
        return RedirectResponse(url="/login", status_code=302)
    
    app = db.execute(
        select(TenderApplication)
        .options(selectinload(TenderApplication.tender))
        .where(TenderApplication.id == application_id)
    ).scalar_one_or_none()
    
    if not app:
        return RedirectResponse(url="/applications", status_code=302)
    
    app.status = "rejected"
    db.commit()
    
    return RedirectResponse(url=f"/tenders/{app.tender_id}", status_code=302)

