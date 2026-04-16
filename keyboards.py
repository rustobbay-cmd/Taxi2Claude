from aiogram.types import (
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    KeyboardButton,
    ReplyKeyboardMarkup,
    ReplyKeyboardRemove,
)

from locations import LOCATIONS


def client_main_kb() -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="🚕 Заказать такси")],
            [KeyboardButton(text="📦 Мой заказ"), KeyboardButton(text="❌ Отменить заказ")],
            [KeyboardButton(text="ℹ️ Помощь")],
        ],
        resize_keyboard=True,
    )


def driver_main_kb(is_online: bool) -> ReplyKeyboardMarkup:
    toggle = "🔴 Уйти с линии" if is_online else "🟢 Выйти на линию"
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text=toggle)],
            [KeyboardButton(text="📦 Мой заказ"), KeyboardButton(text="📋 Свободные заказы")],
            [KeyboardButton(text="ℹ️ Помощь")],
        ],
        resize_keyboard=True,
    )


def locations_kb(prefix: str, include_custom: bool = True) -> InlineKeyboardMarkup:
    rows: list[list[InlineKeyboardButton]] = []
    row: list[InlineKeyboardButton] = []
    for key, name in LOCATIONS:
        row.append(InlineKeyboardButton(text=name, callback_data=f"{prefix}:{key}"))
        if len(row) == 2:
            rows.append(row)
            row = []
    if row:
        rows.append(row)
    if include_custom:
        rows.append([InlineKeyboardButton(text="✍️ Другой адрес", callback_data=f"{prefix}:__custom__")])
    rows.append([InlineKeyboardButton(text="✖️ Отмена", callback_data=f"{prefix}:__cancel__")])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def confirm_kb() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(text="✅ Подтвердить", callback_data="order:confirm"),
                InlineKeyboardButton(text="✖️ Отмена", callback_data="order:abort"),
            ],
        ]
    )


def skip_comment_kb() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="➡️ Без комментария", callback_data="order:nocomment")],
            [InlineKeyboardButton(text="✖️ Отмена", callback_data="order:abort")],
        ]
    )


def driver_offer_kb(order_id: int) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="✅ Принять", callback_data=f"accept:{order_id}")],
        ]
    )


def driver_active_kb(order_id: int, in_progress: bool) -> InlineKeyboardMarkup:
    rows: list[list[InlineKeyboardButton]] = []
    if not in_progress:
        rows.append([InlineKeyboardButton(text="🚗 Начать поездку", callback_data=f"start:{order_id}")])
    rows.append([InlineKeyboardButton(text="🏁 Завершить", callback_data=f"finish:{order_id}")])
    rows.append([InlineKeyboardButton(text="✖️ Отказаться", callback_data=f"dcancel:{order_id}")])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def remove_kb() -> ReplyKeyboardRemove:
    return ReplyKeyboardRemove()


def share_phone_kb() -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="📱 Поделиться номером", request_contact=True)],
            [KeyboardButton(text="Пропустить")],
        ],
        resize_keyboard=True,
        one_time_keyboard=True,
    )
