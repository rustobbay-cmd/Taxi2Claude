from aiogram import Bot, F, Router
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Contact, Message

import database as db
from config import DRIVER_REG_CODE
from keyboards import (
    client_main_kb,
    driver_active_kb,
    driver_main_kb,
    remove_kb,
    share_phone_kb,
)
from locations import location_name
from states import DriverRegStates

router = Router()


# ---------- регистрация водителя ----------

@router.message(Command("driver"))
async def driver_entry(message: Message, state: FSMContext) -> None:
    existing = await db.get_driver(message.from_user.id)
    if existing:
        await message.answer(
            "Вы уже зарегистрированы как водитель.",
            reply_markup=driver_main_kb(bool(existing["is_online"])),
        )
        return
    await state.set_state(DriverRegStates.code)
    await message.answer(
        "Регистрация водителя.\nВведите код доступа (выдаётся администратором):",
        reply_markup=remove_kb(),
    )


@router.message(DriverRegStates.code)
async def driver_code(message: Message, state: FSMContext) -> None:
    if (message.text or "").strip() != DRIVER_REG_CODE:
        await message.answer("Неверный код. Попробуйте ещё раз или /cancel.")
        return
    await state.set_state(DriverRegStates.full_name)
    await message.answer("Введите ваше имя и фамилию:")


@router.message(DriverRegStates.full_name)
async def driver_name(message: Message, state: FSMContext) -> None:
    name = (message.text or "").strip()
    if len(name) < 2 or len(name) > 80:
        await message.answer("Имя должно быть от 2 до 80 символов.")
        return
    await state.update_data(full_name=name)
    await state.set_state(DriverRegStates.phone)
    await message.answer(
        "Отправьте номер телефона или нажмите «Поделиться номером».",
        reply_markup=share_phone_kb(),
    )


@router.message(DriverRegStates.phone, F.contact)
async def driver_phone_contact(message: Message, state: FSMContext) -> None:
    contact: Contact = message.contact
    if contact.user_id != message.from_user.id:
        await message.answer("Пришлите свой номер, не чужой.")
        return
    await state.update_data(phone=contact.phone_number)
    await state.set_state(DriverRegStates.car)
    await message.answer("Укажите марку и госномер автомобиля (например «Lada Granta, А123ВС»):", reply_markup=remove_kb())


@router.message(DriverRegStates.phone)
async def driver_phone_text(message: Message, state: FSMContext) -> None:
    text = (message.text or "").strip()
    if text.lower() == "пропустить":
        await state.update_data(phone=None)
    elif len(text) < 5 or len(text) > 20:
        await message.answer("Введите корректный номер или «Пропустить».")
        return
    else:
        await state.update_data(phone=text)
    await state.set_state(DriverRegStates.car)
    await message.answer("Укажите марку и госномер автомобиля:", reply_markup=remove_kb())


@router.message(DriverRegStates.car)
async def driver_car(message: Message, state: FSMContext) -> None:
    car = (message.text or "").strip()
    if len(car) < 2 or len(car) > 80:
        await message.answer("От 2 до 80 символов.")
        return
    data = await state.get_data()
    await db.add_driver(
        user_id=message.from_user.id,
        full_name=data["full_name"],
        phone=data.get("phone"),
        car=car,
    )
    await state.clear()
    await message.answer(
        "✅ Регистрация завершена. Нажмите «🟢 Выйти на линию», чтобы получать заказы.",
        reply_markup=driver_main_kb(False),
    )


# ---------- онлайн/оффлайн ----------

@router.message(F.text.in_({"🟢 Выйти на линию", "🔴 Уйти с линии"}))
async def toggle_online(message: Message, bot: Bot) -> None:
    driver = await db.get_driver(message.from_user.id)
    if not driver:
        return
    new_online = not bool(driver["is_online"])
    await db.set_driver_online(message.from_user.id, new_online)
    await message.answer(
        "🟢 Вы на линии. Ждите заказов." if new_online else "🔴 Вы ушли с линии.",
        reply_markup=driver_main_kb(new_online),
    )
    if new_online:
        # Если в очереди есть заказы без водителя — предложить
        for order in await db.list_new_orders():
            await _offer_order_to_driver(bot, order["id"], message.from_user.id)


async def _offer_order_to_driver(bot: Bot, order_id: int, driver_id: int) -> None:
    from handlers.client import _format_order_for_driver  # локальный импорт против циклов
    from keyboards import driver_offer_kb

    order = await db.get_order(order_id)
    if not order or order["status"] != "new":
        return
    client = await db.get_user(order["client_id"])
    try:
        await bot.send_message(
            driver_id,
            "🆕 <b>Новый заказ</b>\n\n" + _format_order_for_driver(order, client),
            reply_markup=driver_offer_kb(order_id),
        )
    except Exception:
        pass


# ---------- принятие заказа ----------

@router.callback_query(F.data.startswith("accept:"))
async def accept_order(cb: CallbackQuery, bot: Bot) -> None:
    order_id = int(cb.data.split(":", 1)[1])
    driver = await db.get_driver(cb.from_user.id)
    if not driver:
        await cb.answer("Вы не зарегистрированы как водитель.", show_alert=True)
        return
    if not driver["is_online"]:
        await cb.answer("Сначала выйдите на линию.", show_alert=True)
        return
    if await db.driver_has_active_order(cb.from_user.id):
        await cb.answer("У вас уже есть активный заказ.", show_alert=True)
        return
    success = await db.claim_order(order_id, cb.from_user.id)
    if not success:
        await cb.answer("Заказ уже взят другим водителем.", show_alert=True)
        try:
            await cb.message.edit_text(cb.message.html_text + "\n\n❌ Заказ забрал другой водитель.")
        except Exception:
            pass
        return
    order = await db.get_order(order_id)
    client = await db.get_user(order["client_id"])
    from handlers.client import _format_order_for_driver
    await cb.message.edit_text(
        "✅ Заказ принят\n\n" + _format_order_for_driver(order, client),
        reply_markup=driver_active_kb(order_id, in_progress=False),
    )
    await cb.answer("Заказ ваш!")
    # Уведомить клиента
    try:
        text = (
            f"✅ Водитель принял ваш заказ №{order_id}.\n\n"
            f"<b>{driver['full_name']}</b>"
        )
        if driver.get("car"):
            text += f"\nАвто: {driver['car']}"
        if driver.get("phone"):
            text += f"\nТел.: {driver['phone']}"
        await bot.send_message(order["client_id"], text)
    except Exception:
        pass


# ---------- старт / финиш / отказ ----------

@router.callback_query(F.data.startswith("start:"))
async def start_trip(cb: CallbackQuery, bot: Bot) -> None:
    order_id = int(cb.data.split(":", 1)[1])
    ok = await db.set_order_in_progress(order_id, cb.from_user.id)
    if not ok:
        await cb.answer("Действие недоступно.", show_alert=True)
        return
    order = await db.get_order(order_id)
    client = await db.get_user(order["client_id"])
    from handlers.client import _format_order_for_driver
    await cb.message.edit_text(
        "🚗 Поездка началась\n\n" + _format_order_for_driver(order, client),
        reply_markup=driver_active_kb(order_id, in_progress=True),
    )
    await cb.answer("Поехали!")
    try:
        await bot.send_message(order["client_id"], f"🚗 Водитель начал поездку по заказу №{order_id}.")
    except Exception:
        pass


@router.callback_query(F.data.startswith("finish:"))
async def finish_trip(cb: CallbackQuery, bot: Bot) -> None:
    order_id = int(cb.data.split(":", 1)[1])
    ok = await db.complete_order(order_id, cb.from_user.id)
    if not ok:
        await cb.answer("Действие недоступно.", show_alert=True)
        return
    order = await db.get_order(order_id)
    await cb.message.edit_text(f"🏁 Заказ №{order_id} завершён. Спасибо!")
    await cb.answer("Готово!")
    driver = await db.get_driver(cb.from_user.id)
    await bot.send_message(
        cb.from_user.id,
        "Вы снова свободны и готовы принимать заказы.",
        reply_markup=driver_main_kb(bool(driver["is_online"])),
    )
    try:
        await bot.send_message(
            order["client_id"],
            f"🏁 Поездка по заказу №{order_id} завершена. Спасибо, что воспользовались!",
            reply_markup=client_main_kb(),
        )
    except Exception:
        pass


@router.callback_query(F.data.startswith("dcancel:"))
async def driver_cancel(cb: CallbackQuery, bot: Bot) -> None:
    order_id = int(cb.data.split(":", 1)[1])
    cancelled = await db.cancel_order(order_id, cb.from_user.id)
    if not cancelled:
        await cb.answer("Нельзя отменить.", show_alert=True)
        return
    await cb.message.edit_text(f"✖️ Вы отказались от заказа №{order_id}.")
    await cb.answer()
    driver = await db.get_driver(cb.from_user.id)
    await bot.send_message(
        cb.from_user.id,
        "Вы свободны.",
        reply_markup=driver_main_kb(bool(driver["is_online"])),
    )
    try:
        await bot.send_message(
            cancelled["client_id"],
            f"⚠️ Водитель отказался от заказа №{order_id}. Ищем другого водителя…",
        )
    except Exception:
        pass
    # Перевыставляем как новый и оповещаем
    import aiosqlite
    from config import DB_PATH
    async with aiosqlite.connect(DB_PATH) as conn:
        await conn.execute(
            "UPDATE orders SET status='new', driver_id=NULL, assigned_at=NULL WHERE id=?",
            (order_id,),
        )
        await conn.commit()
    from handlers.client import broadcast_order_to_drivers
    await broadcast_order_to_drivers(bot, order_id)


# ---------- мой заказ / свободные заказы ----------

@router.message(F.text == "📦 Мой заказ")
async def driver_my_order(message: Message) -> None:
    driver = await db.get_driver(message.from_user.id)
    if not driver:
        return
    order = await db.active_order_for_driver(message.from_user.id)
    if not order:
        await message.answer("У вас нет активного заказа.")
        return
    client = await db.get_user(order["client_id"])
    from handlers.client import _format_order_for_driver
    await message.answer(
        _format_order_for_driver(order, client),
        reply_markup=driver_active_kb(order["id"], in_progress=(order["status"] == "in_progress")),
    )


@router.message(F.text == "📋 Свободные заказы")
async def free_orders(message: Message) -> None:
    driver = await db.get_driver(message.from_user.id)
    if not driver:
        return
    if not driver["is_online"]:
        await message.answer("Выйдите на линию, чтобы видеть и брать заказы.")
        return
    if await db.driver_has_active_order(message.from_user.id):
        await message.answer("Сначала завершите текущий заказ.")
        return
    orders = await db.list_new_orders()
    if not orders:
        await message.answer("Свободных заказов нет.")
        return
    from handlers.client import _format_order_for_driver
    from keyboards import driver_offer_kb
    for order in orders:
        client = await db.get_user(order["client_id"])
        await message.answer(
            _format_order_for_driver(order, client),
            reply_markup=driver_offer_kb(order["id"]),
        )
