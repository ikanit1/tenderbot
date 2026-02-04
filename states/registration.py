# states/registration.py — шаги регистрации исполнителя
from aiogram.fsm.state import State, StatesGroup


class RegistrationStates(StatesGroup):
    """Пошаговое заполнение профиля исполнителя: ФИО, дата рождения, город, телефон, навыки, документы."""

    full_name = State()
    birth_date = State()
    city = State()
    phone = State()
    skills = State()
    documents = State()
    done = State()


class ProfileEditStates(StatesGroup):
    """Редактирование профиля: город, телефон, навыки."""

    city = State()
    phone = State()
    skills = State()
