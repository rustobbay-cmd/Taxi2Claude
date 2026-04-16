from aiogram import Bot, Router, F
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message

import database as db
from keyboards import (
    client_main_kb,
    confirm_kb,
    locations_kb,
    skip_comment_kb,
    driver_offer_kb,
)
from locations import location_name
from states import OrderStates

router = Router()


def _format_order_for_client(order: dict, driver: dict | None = None) -> str:
    status_map = {
        "new": "🔎 Ищем водителя…",
        "assigned": "✅ Водитель назначен",
        "in_progress": "🚗 Вы в поездке",
        "completed": "🏁 Поездка завершена",
        "cancelled": "✖️ Отменён",
    }
    text = (
        f"<b>Заказ №{order['id']}</b>\n"
        f"Откуда: {location_name(order['pickup'])}\n"
        f"Куда: {location_name(order['destination'])}\n"
    )
    if order.get("comment"):
        text += f"Комментарий: {order['comment']}\n"
    text += f"Статус: {status_map.get(order['status'], order['status'])}"
    if driver:
        text += (
            f"\n\n<b>Водитель</b>\n"
            f"{driver['full_name']}"
        )
        if driver.get("car"):
            text += f"\nАвто: {driver['car']}"
        if driver.get("phone"):
            text += f"\nТел.: {driver['phone']}"
    return text


def _format_order_for_driver(order: dict, client: dict | None = None) -> str:
    text = (
        f"<b>Заказ №{order['id']}</b>\n"
        f"Откуда: {location_name(order['pickup'])}\n"
        f"Куда: {location_name(order['destination'])}\n"
    )
    if order.get("comment"):
        text += f"Комментарий: {order['comment']}\n"
    if client:
        name = client.get("full_name") or "Клиент"
        text += f"\nКлиент: {name}"
        if client.get("phone"):
            text += f"\nТел.: {client['phone']}"
        if client.get("username"):
            text += f"\n@{client['username']}"
    return text


# ---------- start order ----------

@router.message(F.text == "🚕 Заказать такси")
async def new_order(message: Message, state: FSMContext) -> None:
    driver = await db.get_driver(message.from_user.id)
    if driver:
        await message.answer(
            "Вы зарегистрированы как водитель. Клиентский заказ недоступен."
        )
        return
    active = await db.active_order_for_client(message.from_user.id)
    if active:
        await message.answer(
            "У вас уже есть активный заказ. Сначала завершите или отмените его.\n\n"
            + _format_order_for_client(active)
        )
        return
    await state.set_state(OrderStates.pickup)
    await message.answer(
        "<b>Откуда подать машину?</b>",
        reply_markup=locations_kb("pickup"),
    )


# ---------- pickup ----------

@router.callback_query(F.data.startswith("pickup:"), OrderStates.pickup)
async def pickup_chosen(cb: CallbackQuery, state: FSMContext) -> None:
    key = cb.data.split(":", 1)[1]
    if key == "__cancel__":
        await state.clear()
        await cb.message.edit_text("Заказ отменён.")
        await cb.answer()
        return
    if key == "__custom__":
        await state.set_state(OrderStates.pickup_custom)
        await cb.message.edit_text("Напишите адрес подачи одним сообщением:")
        await cb.answer()
        return
    await state.update_data(pickup=key)
    await state.set_state(OrderStates.destination)
    await cb.message.edit_text(
        f"Откуда: <b>{location_name(key)}</b>\n\n<b>Куда едем?</b>",
        reply_markup=locations_kb("dest"),
    )
    await cb.answer()


@router.message(OrderStates.pickup_custom)
async def pickup_custom(message: Message, state: FSMContext) -> None:
    text = (message.text or "").strip()
    if not text or len(text) > 200:
        await message.answer("Введите адрес текстом (до 200 символов).")
        return
    key = f"custom:{text}"
    await state.update_data(pickup=key)
    await state.set_state(OrderStates.destination)
    await message.answer(
        f"Откуда: <b>{location_name(key)}</b>\n\n<b>Куда едем?</b>",
        reply_markup=locations_kb("dest"),
    )


# ---------- destination ----------

@router.callback_query(F.data.startswith("dest:"), OrderStates.destination)
async def dest_chosen(cb: CallbackQuery, state: FSMContext) -> None:
    key = cb.data.split(":", 1)[1]
    if key == "__cancel__":
        await state.clear()
        await cb.message.edit_text("Заказ отменён.")
        await cb.answer()
        return
    if key == "__custom__":
        await state.set_state(OrderStates.destination_custom)
        await cb.message.edit_text("Напишите адрес назначения одним сообщением:")
        await cb.answer()
        return
    await state.update_data(destination=key)
    await state.set_state(OrderStates.comment)
    data = await state.get_data()
    await cb.message.edit_text(
        f"Откуда: <b>{location_name(data['pickup'])}</b>\n"
        f"Куда: <b>{location_name(key)}</b>\n\n"
        "Комментарий для водителя (номер дома, подъезд, телефон, кол-во пассажиров) "
        "или нажмите «Без комментария».",
        reply_markup=skip_comment_kb(),
    )
    await cb.answer()


@router.message(OrderStates.destination_custom)
async def destination_custom(message: Message, state: FSMContext) -> None:
    text = (message.text or "").strip()
    if not text or len(text) > 200:
        await message.answer("Введите адрес текстом (до 200 символов).")
        return
    key = f"custom:{text}"
    await state.update_data(destination=key)
    await state.set_state(OrderStates.comment)
    data = await state.get_data()
    await message.answer(
        f"Откуда: <b>{location_name(data['pickup'])}</b>\n"
        f"Куда: <b>{location_name(key)}</b>\n\n"
        "Комментарий для водителя или нажмите «Без комментария».",
        reply_markup=skip_comment_kb(),
    )


# ---------- comment ----------

@router.callback_query(F.data == "order:nocomment", OrderStates.comment)
async def no_comment(cb: CallbackQuery, state: FSMContext) -> None:
    await state.update_data(comment=None)
    await _show_confirm(cb.message, state, edit=True)
    await cb.answer()


@router.callback_query(F.data == "order:abort")
async def order_abort(cb: CallbackQuery, state: FSMContext) -> None:
    await state.clear()
    await cb.message.edit_text("Заказ отменён.")
    await cb.answer()


@router.message(OrderStates.comment)
async def set_comment(message: Message, state: FSMContext) -> None:
    text = (message.text or "").strip()
    if len(text) > 300:
        await message.answer("Слишком длинный комментарий (до 300 символов).")
        return
    await state.update_data(comment=text or None)
    await _show_confirm(message, state, edit=False)


async def _show_confirm(message: Message, state: FSMContext, edit: bool) -> None:
    data = await state.get_data()
    await state.set_state(OrderStates.confirm)
    text = (
        "<b>Проверьте заказ</b>\n"
        f"Откуда: {location_name(data['pickup'])}\n"
        f"Куда: {location_name(data['destination'])}\n"
    )
    if data.get("comment"):
        text += f"Комментарий: {data['comment']}\n"
    text += "\nПодтвердить?"
    if edit:
        await message.edit_text(text, reply_markup=confirm_kb())
    else:
        await message.answer(text, reply_markup=confirm_kb())


# ---------- confirm ----------

@router.callback_query(F.data == "order:confirm", OrderStates.confirm)
async def order_confirm(cb: CallbackQuery, state: FSMContext, bot: Bot) -> None:
    data = await state.get_data()
    await state.clear()
    order_id = await db.create_order(
        client_id=cb.from_user.id,
        pickup=data["pickup"],
        destination=data["destination"],
        comment=data.get("comment"),
    )
    await cb.message.edit_text(
        f"✅ Заказ №{order_id} создан. Ищем водителя…\n\n"
        "Вы получите уведомление, как только водитель примет заказ."
    )
    await cb.answer()
    # Оповещаем водителей
    await broadcast_order_to_drivers(bot, order_id)


async def broadcast_order_to_drivers(bot: Bot, order_id: int) -> None:
    order = await db.get_order(order_id)
    if not order or order["status"] != "new":
        return
    client = await db.get_user(order["client_id"])
    drivers = await db.list_online_drivers()
    if not drivers:
        # Никого на линии — сообщим клиенту
        try:
            await bot.send_message(
                order["client_id"],
                "⚠️ Сейчас нет свободных водителей на линии. "
                "Как только кто-то выйдет — ваш заказ будет предложен первым.",
            )
        except Exception:
            pass
        return
    text = "🆕 <b>Новый заказ</b>\n\n" + _format_order_for_driver(order, client)
    for d in drivers:
        if await db.driver_has_active_order(d["user_id"]):
            continue
        try:
            await bot.send_message(
                d["user_id"],
                text,
                reply_markup=driver_offer_kb(order_id),
            )
        except Exception:
            # Водитель мог заблокировать бота — игнорируем
            continue


# ---------- my order / cancel ----------

@router.message(F.text == "📦 Мой заказ")
async def my_order(message: Message) -> None:
    driver = await db.get_driver(message.from_user.id)
    if driver:
        return  # у водителей своя кнопка обрабатывается в driver.py
    active = await db.active_order_for_client(message.from_user.id)
    if not active:
        await message.answer("У вас нет активных заказов.", reply_markup=client_main_kb())
        return
    driver_info = None
    if active.get("driver_id"):
        driver_info = await db.get_driver(active["driver_id"])
    await message.answer(_format_order_for_client(active, driver_info))


@router.message(F.text == "❌ Отменить заказ")
async def cancel_active(message: Message, bot: Bot) -> None:
    if await db.get_driver(message.from_user.id):
        return
    active = await db.active_order_for_client(message.from_user.id)
    if not active:
        await message.answer("Нет активного заказа для отмены.")
        return
    cancelled = await db.cancel_order(active["id"], message.from_user.id)
    if not cancelled:
        await message.answer("Не удалось отменить.")
        return
    await message.answer(f"Заказ №{active['id']} отменён.", reply_markup=client_main_kb())
    if cancelled.get("driver_id"):
        try:
            await bot.send_message(
                cancelled["driver_id"],
                f"⚠️ Клиент отменил заказ №{cancelled['id']}.",
            )
        except Exception:
            pass
