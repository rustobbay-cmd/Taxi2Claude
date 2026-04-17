"""Кастомные фильтры aiogram для разграничения ролей."""

from aiogram.filters import BaseFilter
from aiogram.types import Message

import database as db


class IsDriver(BaseFilter):
    """Пропускает только зарегистрированных водителей."""

    async def __call__(self, message: Message) -> bool:
        return bool(await db.get_driver(message.from_user.id))


class IsClient(BaseFilter):
    """Пропускает только пользователей, не являющихся водителями."""

    async def __call__(self, message: Message) -> bool:
        return not bool(await db.get_driver(message.from_user.id))
