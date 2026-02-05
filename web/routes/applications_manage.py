# web/routes/applications_manage.py — управление откликами
import logging
from fastapi import APIRouter, Request, Depends, Form
from fastapi.responses import HTMLResponse, RedirectResponse
from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload
from typing import Annotated

from web.database import get_db
from web.auth import get_session_user
from web.miniapp.notify import send_telegram_message
from database.models import TenderApplication, Tender, TenderStatus

logger = logging.getLogger(__name__)

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
        logger.warning(f"Attempt to select non-existent application {application_id}")
        return RedirectResponse(url="/applications", status_code=302)
    
    try:
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
        logger.info(f"Application {application_id} selected for tender {app.tender_id}")
        return RedirectResponse(url=f"/tenders/{app.tender_id}", status_code=302)
    except Exception as e:
        db.rollback()
        logger.error(f"Error selecting application {application_id}: {e}")
        return RedirectResponse(url=f"/tenders/{app.tender_id}?error=Ошибка выбора исполнителя", status_code=302)


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
        .options(selectinload(TenderApplication.tender), selectinload(TenderApplication.user))
        .where(TenderApplication.id == application_id)
    ).scalar_one_or_none()
    
    if not app:
        logger.warning(f"Attempt to reject non-existent application {application_id}")
        return RedirectResponse(url="/applications", status_code=302)
    
    try:
        app.status = "rejected"
        db.commit()
        # Уведомление в чат исполнителю
        send_telegram_message(
            app.user.tg_id,
            f"❌ <b>Отклик отклонён</b>\n\n"
            f"К сожалению, ваш отклик на тендер «{app.tender.title}» не принят.\n\n"
            f"Откройте приложение и откликнитесь на другие заказы.",
        )
        logger.info(f"Application {application_id} rejected")
        return RedirectResponse(url=f"/tenders/{app.tender_id}", status_code=302)
    except Exception as e:
        db.rollback()
        logger.error(f"Error rejecting application {application_id}: {e}")
        return RedirectResponse(url=f"/tenders/{app.tender_id}?error=Ошибка отклонения отклика", status_code=302)

