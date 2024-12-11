from aiogram.fsm.state import State, StatesGroup


class SendAdminMessage(StatesGroup):
    admin_message = State()


class AddFlower(StatesGroup):
    name = State()
    price = State()


class Payment(StatesGroup):
    amount = State()


class EditFlower(StatesGroup):
    select_flower = State()
    select_field = State()
    update_value = State()


class BuyFlower(StatesGroup):
    select_quantity = State()
