# states/admin.py — шаги создания тендера и оценки исполнителя
from aiogram.fsm.state import State, StatesGroup


class ReviewStates(StatesGroup):
    """Оценка исполнителя после закрытия тендера: рейтинг 1-5, комментарий."""

    rating = State()
    comment = State()


class AddTenderStates(StatesGroup):
    """Создание тендера: название, категория, город, бюджет, описание, дедлайн, подтверждение."""

    title = State()
    category = State()
    city = State()
    budget = State()
    description = State()
    deadline = State()  # опционально: ДД.ММ.ГГГГ ЧЧ:ММ или «нет»
    confirm = State()
