# web/main.py — FastAPI веб-админка для тендеров
from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.responses import RedirectResponse
from fastapi.staticfiles import StaticFiles

from web.auth import get_session_user
from web.routes import (
    login_router, dashboard_router, users_router, tenders_router,
    applications_router, reviews_router, support_router,
)
from web.routes.moderation import router as moderation_router
from web.routes.applications_manage import router as applications_manage_router
from web.routes.health import router as health_router
from web.miniapp.routes import router as miniapp_router

app = FastAPI(title="TenderBot Admin")
app.mount("/static", StaticFiles(directory=Path(__file__).parent / "static"), name="static")

app.include_router(health_router, tags=["health"])
app.include_router(login_router, tags=["auth"])
app.include_router(dashboard_router, tags=["dashboard"])
app.include_router(users_router, prefix="/users", tags=["users"])
app.include_router(tenders_router, prefix="/tenders", tags=["tenders"])
app.include_router(applications_router, prefix="/applications", tags=["applications"])
app.include_router(support_router, prefix="/support", tags=["support"])
app.include_router(reviews_router, prefix="/reviews", tags=["reviews"])
app.include_router(moderation_router, tags=["moderation"])
app.include_router(applications_manage_router, tags=["applications_manage"])
app.include_router(miniapp_router)


@app.get("/")
async def index(request: Request):
    if get_session_user(request) is None:
        return RedirectResponse(url="/login", status_code=302)
    return RedirectResponse(url="/dashboard", status_code=302)
