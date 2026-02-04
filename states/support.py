# states/support.py — FSM для чата поддержки
from aiogram.fsm.state import State, StatesGroup


class SupportStates(StatesGroup):
    """Чат с поддержкой: пользователь пишет сообщения в тикет."""
    active_chat = State()
