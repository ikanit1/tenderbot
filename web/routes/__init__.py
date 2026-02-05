# web/routes — роуты веб-админки
from web.routes.login import router as login_router
from web.routes.dashboard import router as dashboard_router
from web.routes.users import router as users_router
from web.routes.tenders import router as tenders_router
from web.routes.applications import router as applications_router
from web.routes.reviews import router as reviews_router
from web.routes.support import router as support_router
from web.routes.health import router as health_router

__all__ = [
    "login_router",
    "dashboard_router",
    "users_router",
    "tenders_router",
    "applications_router",
    "reviews_router",
    "support_router",
    "health_router",
]
