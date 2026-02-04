# handlers — регистрация, админ, тендеры, поддержка
from aiogram import Router

from handlers import user, admin, tender, support

router = Router()
router.include_router(user.router)
router.include_router(admin.router)
router.include_router(tender.router)
router.include_router(support.router)
