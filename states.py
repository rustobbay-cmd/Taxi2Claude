from aiogram.fsm.state import State, StatesGroup


class OrderStates(StatesGroup):
    pickup = State()
    pickup_custom = State()
    destination = State()
    destination_custom = State()
    comment = State()
    confirm = State()


class DriverRegStates(StatesGroup):
    code = State()
    full_name = State()
    phone = State()
    car = State()


class ClientRegStates(StatesGroup):
    phone = State()
