"""Список стандартных точек населённого пункта.

Отредактируйте под свой город/посёлок. Ключ используется как идентификатор,
значение — отображаемое название.
"""

LOCATIONS: list[tuple[str, str]] = [
    ("center", "Центр"),
    ("station", "Ж/Д вокзал"),
    ("bus_station", "Автостанция"),
    ("market", "Рынок"),
    ("hospital", "Больница"),
    ("school", "Школа"),
    ("kindergarten", "Детский сад"),
    ("shop_magnit", "Магнит"),
    ("shop_pyaterochka", "Пятёрочка"),
    ("post", "Почта"),
    ("admin_building", "Администрация"),
    ("park", "Парк"),
    ("cemetery", "Кладбище"),
    ("gas_station", "АЗС"),
]

LOCATION_MAP: dict[str, str] = dict(LOCATIONS)


def location_name(key: str) -> str:
    """Вернуть человекочитаемое имя. Если ключ начинается с 'custom:',
    то остаток — свободный адрес, введённый пользователем."""
    if key.startswith("custom:"):
        return key[len("custom:"):]
    return LOCATION_MAP.get(key, key)
