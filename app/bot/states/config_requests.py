"""FSM states for user config request flow."""

from aiogram.fsm.state import State, StatesGroup


class ConfigRequestStates(StatesGroup):
    waiting_for_comment = State()
