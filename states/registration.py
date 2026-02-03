# states/registration.py — шаги регистрации исполнителя и заказчика
from aiogram.fsm.state import State, StatesGroup


class RoleChoiceStates(StatesGroup):
    """Выбор роли перед регистрацией."""

    role = State()


class RegistrationStates(StatesGroup):
    """Пошаговое заполнение профиля исполнителя: ФИО, дата рождения, город, телефон, навыки, документы."""

    full_name = State()
    birth_date = State()
    city = State()
    phone = State()
    skills = State()
    documents = State()
    done = State()


class CustomerRegistrationStates(StatesGroup):
    """Укороченная регистрация заказчика: название/ФИО, город, контакт."""

    full_name = State()
    city = State()
    phone = State()
    done = State()


class ProfileEditStates(StatesGroup):
    """Редактирование профиля: город, телефон, навыки."""

    city = State()
    phone = State()
    skills = State()
