from aiogram import Bot, F, Router
from aiogram.filters import Command
from aiogram.types import CallbackQuery, InlineKeyboardButton, InlineKeyboardMarkup, Message

import database as db
from config import ADMIN_IDS

router = Router()


def _is_admin(user_id: int) -> bool:
    return user_id in ADMIN_IDS


@router.message(Command("admin"))
async def cmd_admin(message: Message) -> None:
    if not _is_admin(message.from_user.id):
        return
    await message.answer(
        "<b>Админ-меню</b>\n"
        "/stats — статистика\n"
        "/drivers — список водителей\n"
        "/orders — свободные заказы в очереди"
    )


@router.message(Command("stats"))
async def cmd_stats(message: Message) -> None:
    if not _is_admin(message.from_user.id):
        return
    s = await db.stats()
    orders = s["orders"]
    text = (
        "<b>Статистика</b>\n"
        f"Водителей всего: {s['drivers_total']}\n"
        f"На линии: {s['drivers_online']}\n\n"
        f"Заказы:\n"
        f"  🔎 новые: {orders.get('new', 0)}\n"
        f"  ✅ назначены: {orders.get('assigned', 0)}\n"
        f"  🚗 в поездке: {orders.get('in_progress', 0)}\n"
        f"  🏁 завершены: {orders.get('completed', 0)}\n"
        f"  ✖️ отменены: {orders.get('cancelled', 0)}\n"
    )
    await message.answer(text)


@router.message(Command("drivers"))
async def cmd_drivers(message: Message) -> None:
    if not _is_admin(message.from_user.id):
        return
    drivers = await db.list_all_drivers()
    if not drivers:
        await message.answer("Водителей пока нет.")
        return
    for d in drivers:
        status = "🟢 на линии" if d["is_online"] else "🔴 оффлайн"
        text = (
            f"<b>{d['full_name']}</b>\n"
            f"ID: <code>{d['user_id']}</code>\n"
            f"Авто: {d.get('car') or '-'}\n"
            f"Тел.: {d.get('phone') or '-'}\n"
            f"Статус: {status}"
        )
        kb = InlineKeyboardMarkup(
            inline_keyboard=[
                [InlineKeyboardButton(
                    text="🗑 Удалить",
                    callback_data=f"admin_del:{d['user_id']}",
                )]
            ]
        )
        await message.answer(text, reply_markup=kb)


@router.callback_query(F.data.startswith("admin_del:"))
async def admin_delete_driver(cb: CallbackQuery, bot: Bot) -> None:
    if not _is_admin(cb.from_user.id):
        await cb.answer("Нет доступа.", show_alert=True)
        return
    driver_id = int(cb.data.split(":", 1)[1])
    driver = await db.get_driver(driver_id)
    if not driver:
        await cb.answer("Водитель уже удалён.", show_alert=True)
        await cb.message.edit_reply_markup()
        return
    await db.remove_driver(driver_id)
    await cb.message.edit_text(
        cb.message.html_text + "\n\n<b>❌ Удалён</b>",
    )
    await cb.answer("Удалён.")
    try:
        await bot.send_message(
            driver_id,
            "Администратор исключил вас из числа водителей.",
        )
    except Exception:
        pass


@router.message(Command("orders"))
async def cmd_orders(message: Message) -> None:
    if not _is_admin(message.from_user.id):
        return
    orders = await db.list_new_orders()
    if not orders:
        await message.answer("Очередь пуста.")
        return
    from locations import location_name
    lines = ["<b>Свободные заказы:</b>"]
    for o in orders:
        lines.append(
            f"№{o['id']}: {location_name(o['pickup'])} → {location_name(o['destination'])}"
        )
    await message.answer("\n".join(lines))
