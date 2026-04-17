"""Общие функции форматирования сообщений.

Вынесены из handlers/client.py, чтобы избежать циклических импортов между
client.py и driver.py.
"""

from locations import location_name

STATUS_MAP = {
    "new": "🔎 Ищем водителя…",
    "assigned": "✅ Водитель назначен",
    "in_progress": "🚗 Вы в поездке",
    "completed": "🏁 Поездка завершена",
    "cancelled": "✖️ Отменён",
}


def format_order_for_client(order: dict, driver: dict | None = None) -> str:
    text = (
        f"<b>Заказ №{order['id']}</b>\n"
        f"Откуда: {location_name(order['pickup'])}\n"
        f"Куда: {location_name(order['destination'])}\n"
    )
    if order.get("comment"):
        text += f"Комментарий: {order['comment']}\n"
    text += f"Статус: {STATUS_MAP.get(order['status'], order['status'])}"
    if driver:
        text += f"\n\n<b>Водитель</b>\n{driver['full_name']}"
        if driver.get("car"):
            text += f"\nАвто: {driver['car']}"
        if driver.get("phone"):
            text += f"\nТел.: {driver['phone']}"
    return text


def format_order_for_driver(order: dict, client: dict | None = None) -> str:
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
