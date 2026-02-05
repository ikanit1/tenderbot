# web/routes/applications.py
from fastapi import APIRouter, Request, Depends, Query
from fastapi.responses import HTMLResponse, RedirectResponse
from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from web.database import get_db
from web.auth import get_session_user
from web.templates_loader import templates
from database.models import TenderApplication

router = APIRouter()


@router.post("/{application_id}/delete", response_class=RedirectResponse)
async def application_delete(
    request: Request,
    application_id: int,
    db: Session = Depends(get_db),
):
    """Удалить отклик (например ошибочный или спам)."""
    if get_session_user(request) is None:
        return RedirectResponse(url="/login", status_code=302)
    app = db.execute(select(TenderApplication).where(TenderApplication.id == application_id)).scalar_one_or_none()
    if app:
        tender_id = app.tender_id
        db.delete(app)
        db.commit()
        return RedirectResponse(url=f"/tenders/{tender_id}", status_code=302)
    return RedirectResponse(url="/applications", status_code=302)


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
