from aiogram import Router, F
from aiogram.filters import CommandStart, Command
from aiogram.fsm.context import FSMContext
from aiogram.types import Message

import database as db
from keyboards import client_main_kb, driver_main_kb

router = Router()
# common-роутер не ограничивает по роли — обрабатывает всех пользователей.


HELP_CLIENT = (
    "<b>Как заказать такси</b>\n"
    "1. Нажмите «🚕 Заказать такси»\n"
    "2. Выберите точку подачи\n"
    "3. Выберите точку назначения\n"
    "4. При необходимости добавьте комментарий (номер дома, телефон, кол-во пассажиров)\n"
    "5. Подтвердите заказ\n\n"
    "Когда водитель примет заказ — пришлём его контакты.\n\n"
    "Водитель? Команда /driver для регистрации."
)

HELP_DRIVER = (
    "<b>Вы — водитель</b>\n"
    "• «🟢 Выйти на линию» — получать заказы\n"
    "• «🔴 Уйти с линии» — не беспокоить\n"
    "• Новые заказы приходят всем онлайн-водителям. Первый принявший забирает заказ.\n"
    "• После принятия — «🚗 Начать поездку», затем «🏁 Завершить»."
)


@router.message(CommandStart())
async def cmd_start(message: Message, state: FSMContext) -> None:
    await state.clear()
    user = message.from_user
    await db.upsert_user(user.id, user.username, user.full_name)
    driver = await db.get_driver(user.id)
    if driver:
        await message.answer(
            f"С возвращением, {driver['full_name']}!",
            reply_markup=driver_main_kb(bool(driver["is_online"])),
        )
    else:
        await message.answer(
            "Здравствуйте! Это бот заказа такси.\n"
            "Нажмите «🚕 Заказать такси», чтобы начать.",
            reply_markup=client_main_kb(),
        )


@router.message(Command("help"))
@router.message(F.text == "ℹ️ Помощь")
async def cmd_help(message: Message) -> None:
    driver = await db.get_driver(message.from_user.id)
    await message.answer(HELP_DRIVER if driver else HELP_CLIENT)


@router.message(Command("cancel"))
async def cmd_cancel(message: Message, state: FSMContext) -> None:
    current = await state.get_state()
    if current is None:
        await message.answer("Нечего отменять.")
        return
    await state.clear()
    driver = await db.get_driver(message.from_user.id)
    kb = driver_main_kb(bool(driver["is_online"])) if driver else client_main_kb()
    await message.answer("Действие отменено.", reply_markup=kb)
