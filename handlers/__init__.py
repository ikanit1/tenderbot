# handlers — регистрация, админ, заказчик, тендеры и отклики
from aiogram import Router

from handlers import user, admin, customer, tender

router = Router()
router.include_router(user.router)
router.include_router(admin.router)
router.include_router(customer.router)
router.include_router(tender.router)
