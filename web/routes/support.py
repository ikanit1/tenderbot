# web/routes/support.py — тикеты поддержки в веб-админке
import httpx

from fastapi import APIRouter, Request, Depends, Query, Form
from fastapi.responses import HTMLResponse, RedirectResponse, JSONResponse
from sqlalchemy import select, func
from sqlalchemy.orm import Session, selectinload

from config import settings
from web.database import get_db
from web.auth import get_session_user
from web.templates_loader import templates
from database.models import User, SupportTicket, SupportMessage, TicketStatus

router = APIRouter()


@router.get("", response_class=HTMLResponse)
async def support_list(
    request: Request,
    db: Session = Depends(get_db),
    status: str | None = Query(None),
):
    """Список тикетов: новые (красные), в процессе (жёлтые), закрытые (архив)."""
    if get_session_user(request) is None:
        return RedirectResponse(url="/login", status_code=302)

    q = (
        select(SupportTicket)
        .options(selectinload(SupportTicket.user))
        .order_by(SupportTicket.id.desc())
    )
    if status and status in ("new", "in_progress", "closed"):
        q = q.where(SupportTicket.status == status)
    tickets = db.execute(q).scalars().all()

    # Последнее сообщение по каждому тикету
    last_msgs = {}
    for t in tickets:
        last = (
            db.execute(
                select(SupportMessage.text, SupportMessage.created_at)
                .where(SupportMessage.ticket_id == t.id)
                .order_by(SupportMessage.created_at.desc())
                .limit(1)
            )
        ).first()
        last_msgs[t.id] = last

    return templates.TemplateResponse(
        "support.html",
        {
            "request": request,
            "tickets": tickets,
            "last_msgs": last_msgs,
            "status_filter": status,
            "statuses": [
                ("new", "Новые"),
                ("in_progress", "В процессе"),
                ("closed", "Закрытые"),
            ],
        },
    )


@router.get("/{ticket_id}", response_class=HTMLResponse)
async def support_chat(
    request: Request,
    ticket_id: int,
    db: Session = Depends(get_db),
):
    """Страница чата с пользователем по тикету."""
    if get_session_user(request) is None:
        return RedirectResponse(url="/login", status_code=302)

    ticket = (
        db.execute(
            select(SupportTicket)
            .options(
                selectinload(SupportTicket.user),
                selectinload(SupportTicket.messages),
            )
            .where(SupportTicket.id == ticket_id)
        )
    ).scalar_one_or_none()
    if not ticket:
        return RedirectResponse(url="/support", status_code=302)

    messages = sorted(ticket.messages, key=lambda m: m.created_at or 0)
    return templates.TemplateResponse(
        "support_chat.html",
        {
            "request": request,
            "ticket": ticket,
            "messages": messages,
        },
    )


@router.post("/{ticket_id}/reply", response_class=RedirectResponse)
async def support_reply(
    request: Request,
    ticket_id: int,
    db: Session = Depends(get_db),
    text: str = Form(""),
):
    """Ответ админа: сохраняем в БД и отправляем в Telegram пользователю."""
    if get_session_user(request) is None:
        return RedirectResponse(url="/login", status_code=302)

    ticket = (
        db.execute(
            select(SupportTicket).options(selectinload(SupportTicket.user)).where(SupportTicket.id == ticket_id)
        )
    ).scalar_one_or_none()
    if not ticket:
        return RedirectResponse(url="/support", status_code=302)

    text = (text or "").strip()
    if not text:
        return RedirectResponse(url=f"/support/{ticket_id}", status_code=302)

    msg = SupportMessage(ticket_id=ticket_id, author="admin", text=text)
    db.add(msg)
    ticket.status = TicketStatus.IN_PROGRESS.value
    db.commit()

    # Отправка в Telegram через Bot API
    tg_id = ticket.user.tg_id
    url = f"https://api.telegram.org/bot{settings.BOT_TOKEN}/sendMessage"
    payload = {"chat_id": tg_id, "text": text, "parse_mode": "HTML"}
    try:
        async with httpx.AsyncClient() as client:
            r = await client.post(url, json=payload, timeout=10.0)
            if r.status_code != 200:
                pass  # логировать при необходимости
    except Exception:
        pass

    return RedirectResponse(url=f"/support/{ticket_id}", status_code=302)


@router.post("/{ticket_id}/close", response_class=RedirectResponse)
async def support_close(
    request: Request,
    ticket_id: int,
    db: Session = Depends(get_db),
):
    """Закрыть тикет."""
    if get_session_user(request) is None:
        return RedirectResponse(url="/login", status_code=302)
    ticket = db.execute(select(SupportTicket).where(SupportTicket.id == ticket_id)).scalar_one_or_none()
    if ticket:
        ticket.status = TicketStatus.CLOSED.value
        db.commit()
    return RedirectResponse(url="/support", status_code=302)


@router.post("/{ticket_id}/delete", response_class=RedirectResponse)
async def support_ticket_delete(
    request: Request,
    ticket_id: int,
    db: Session = Depends(get_db),
):
    """Удалить тикет и все сообщения (освободить место, не копить архив)."""
    if get_session_user(request) is None:
        return RedirectResponse(url="/login", status_code=302)
    ticket = db.execute(select(SupportTicket).where(SupportTicket.id == ticket_id)).scalar_one_or_none()
    if ticket:
        db.delete(ticket)
        db.commit()
    return RedirectResponse(url="/support", status_code=302)


# Шаблоны быстрых ответов (опционально)
REPLY_TEMPLATES = [
    "Здравствуйте! Чем могу помочь?",
    "Ваш вопрос принят в работу.",
    "Пожалуйста, приложите скриншот или уточните детали.",
    "Спасибо за обращение. Тикет закрыт.",
]


@router.get("/api/templates", response_class=JSONResponse)
async def support_templates_api(request: Request):
    if get_session_user(request) is None:
        return JSONResponse({"templates": []})
    return JSONResponse({"templates": REPLY_TEMPLATES})


@router.get("/api/new_count", response_class=JSONResponse)
async def support_new_count(request: Request, db: Session = Depends(get_db)):
    """Количество тикетов со статусом «новый» — для уведомлений админа (polling + звук)."""
    if get_session_user(request) is None:
        return JSONResponse({"count": 0})
    r = db.execute(select(func.count(SupportTicket.id)).where(SupportTicket.status == TicketStatus.NEW.value))
    n = r.scalar() or 0
    return JSONResponse({"count": n})
