import aiosqlite
from datetime import datetime, timezone
from config import DB_PATH


SCHEMA = """
CREATE TABLE IF NOT EXISTS users (
    user_id     INTEGER PRIMARY KEY,
    username    TEXT,
    full_name   TEXT,
    phone       TEXT,
    created_at  TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS drivers (
    user_id        INTEGER PRIMARY KEY,
    full_name      TEXT NOT NULL,
    phone          TEXT,
    car            TEXT,
    is_online      INTEGER NOT NULL DEFAULT 0,
    last_order_at  TEXT,
    created_at     TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS orders (
    id           INTEGER PRIMARY KEY AUTOINCREMENT,
    client_id    INTEGER NOT NULL,
    pickup       TEXT NOT NULL,
    destination  TEXT NOT NULL,
    comment      TEXT,
    status       TEXT NOT NULL DEFAULT 'new',
    driver_id    INTEGER,
    created_at   TEXT NOT NULL,
    assigned_at  TEXT,
    completed_at TEXT
);

CREATE INDEX IF NOT EXISTS idx_orders_status ON orders(status);
CREATE INDEX IF NOT EXISTS idx_orders_client ON orders(client_id);
CREATE INDEX IF NOT EXISTS idx_orders_driver ON orders(driver_id);
"""


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


async def init_db() -> None:
    async with aiosqlite.connect(DB_PATH) as db:
        await db.executescript(SCHEMA)
        await db.commit()


# ---------- users ----------

async def upsert_user(user_id: int, username: str | None, full_name: str) -> None:
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            """INSERT INTO users(user_id, username, full_name, created_at)
               VALUES(?, ?, ?, ?)
               ON CONFLICT(user_id) DO UPDATE SET
                 username=excluded.username,
                 full_name=excluded.full_name""",
            (user_id, username, full_name, _now()),
        )
        await db.commit()


async def set_user_phone(user_id: int, phone: str) -> None:
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("UPDATE users SET phone=? WHERE user_id=?", (phone, user_id))
        await db.commit()


async def get_user(user_id: int) -> dict | None:
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute("SELECT * FROM users WHERE user_id=?", (user_id,)) as cur:
            row = await cur.fetchone()
            return dict(row) if row else None


# ---------- drivers ----------

async def add_driver(user_id: int, full_name: str, phone: str | None, car: str | None) -> None:
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            """INSERT INTO drivers(user_id, full_name, phone, car, created_at)
               VALUES(?, ?, ?, ?, ?)
               ON CONFLICT(user_id) DO UPDATE SET
                 full_name=excluded.full_name,
                 phone=excluded.phone,
                 car=excluded.car""",
            (user_id, full_name, phone, car, _now()),
        )
        await db.commit()


async def remove_driver(user_id: int) -> None:
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("DELETE FROM drivers WHERE user_id=?", (user_id,))
        await db.commit()


async def get_driver(user_id: int) -> dict | None:
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute("SELECT * FROM drivers WHERE user_id=?", (user_id,)) as cur:
            row = await cur.fetchone()
            return dict(row) if row else None


async def set_driver_online(user_id: int, online: bool) -> None:
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            "UPDATE drivers SET is_online=? WHERE user_id=?",
            (1 if online else 0, user_id),
        )
        await db.commit()


async def list_online_drivers() -> list[dict]:
    """Онлайн-водители, сортировка: сначала тот, кто дольше не брал заказ
    (или ни разу не брал). Так достигается справедливое распределение."""
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute(
            """SELECT * FROM drivers
               WHERE is_online=1
               ORDER BY COALESCE(last_order_at, '') ASC, user_id ASC"""
        ) as cur:
            rows = await cur.fetchall()
            return [dict(r) for r in rows]


async def list_all_drivers() -> list[dict]:
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute("SELECT * FROM drivers ORDER BY created_at ASC") as cur:
            rows = await cur.fetchall()
            return [dict(r) for r in rows]


async def driver_has_active_order(user_id: int) -> bool:
    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute(
            """SELECT 1 FROM orders
               WHERE driver_id=? AND status IN ('assigned','in_progress') LIMIT 1""",
            (user_id,),
        ) as cur:
            return await cur.fetchone() is not None


# ---------- orders ----------

async def create_order(client_id: int, pickup: str, destination: str, comment: str | None) -> int:
    async with aiosqlite.connect(DB_PATH) as db:
        cur = await db.execute(
            """INSERT INTO orders(client_id, pickup, destination, comment, status, created_at)
               VALUES(?, ?, ?, ?, 'new', ?)""",
            (client_id, pickup, destination, comment, _now()),
        )
        await db.commit()
        return cur.lastrowid


async def get_order(order_id: int) -> dict | None:
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute("SELECT * FROM orders WHERE id=?", (order_id,)) as cur:
            row = await cur.fetchone()
            return dict(row) if row else None


async def claim_order(order_id: int, driver_id: int) -> bool:
    """Атомарная попытка взять заказ. True — если удалось."""
    async with aiosqlite.connect(DB_PATH) as db:
        cur = await db.execute(
            """UPDATE orders
               SET driver_id=?, status='assigned', assigned_at=?
               WHERE id=? AND status='new'""",
            (driver_id, _now(), order_id),
        )
        await db.commit()
        if cur.rowcount == 1:
            await db.execute(
                "UPDATE drivers SET last_order_at=? WHERE user_id=?",
                (_now(), driver_id),
            )
            await db.commit()
            return True
        return False


async def set_order_in_progress(order_id: int, driver_id: int) -> bool:
    async with aiosqlite.connect(DB_PATH) as db:
        cur = await db.execute(
            """UPDATE orders SET status='in_progress'
               WHERE id=? AND driver_id=? AND status='assigned'""",
            (order_id, driver_id),
        )
        await db.commit()
        return cur.rowcount == 1


async def complete_order(order_id: int, driver_id: int) -> bool:
    async with aiosqlite.connect(DB_PATH) as db:
        cur = await db.execute(
            """UPDATE orders SET status='completed', completed_at=?
               WHERE id=? AND driver_id=? AND status IN ('assigned','in_progress')""",
            (_now(), order_id, driver_id),
        )
        await db.commit()
        return cur.rowcount == 1


async def cancel_order(order_id: int, by_user_id: int) -> dict | None:
    """Отменить заказ. Клиент может отменить свой заказ до завершения,
    водитель — только свой назначенный. Возвращает заказ до отмены или None."""
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute("SELECT * FROM orders WHERE id=?", (order_id,)) as cur:
            row = await cur.fetchone()
        if not row:
            return None
        order = dict(row)
        if order["status"] in ("completed", "cancelled"):
            return None
        is_client = order["client_id"] == by_user_id
        is_driver = order["driver_id"] == by_user_id
        if not (is_client or is_driver):
            return None
        await db.execute(
            "UPDATE orders SET status='cancelled', completed_at=? WHERE id=?",
            (_now(), order_id),
        )
        await db.commit()
        return order


async def active_order_for_client(client_id: int) -> dict | None:
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute(
            """SELECT * FROM orders
               WHERE client_id=? AND status IN ('new','assigned','in_progress')
               ORDER BY id DESC LIMIT 1""",
            (client_id,),
        ) as cur:
            row = await cur.fetchone()
            return dict(row) if row else None


async def active_order_for_driver(driver_id: int) -> dict | None:
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute(
            """SELECT * FROM orders
               WHERE driver_id=? AND status IN ('assigned','in_progress')
               ORDER BY id DESC LIMIT 1""",
            (driver_id,),
        ) as cur:
            row = await cur.fetchone()
            return dict(row) if row else None


async def list_new_orders() -> list[dict]:
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute(
            "SELECT * FROM orders WHERE status='new' ORDER BY id ASC"
        ) as cur:
            return [dict(r) for r in await cur.fetchall()]


async def release_order(order_id: int) -> None:
    """Вернуть заказ в статус 'new' (например, после отказа водителя).
    Используется вместо прямого SQL в обработчиках."""
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            "UPDATE orders SET status='new', driver_id=NULL, assigned_at=NULL WHERE id=?",
            (order_id,),
        )
        await db.commit()


async def stats() -> dict:
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute(
            """SELECT status, COUNT(*) AS c FROM orders GROUP BY status"""
        ) as cur:
            rows = await cur.fetchall()
        by_status = {r["status"]: r["c"] for r in rows}
        async with db.execute("SELECT COUNT(*) AS c FROM drivers") as cur:
            drivers_count = (await cur.fetchone())["c"]
        async with db.execute("SELECT COUNT(*) AS c FROM drivers WHERE is_online=1") as cur:
            online_count = (await cur.fetchone())["c"]
        return {
            "orders": by_status,
            "drivers_total": drivers_count,
            "drivers_online": online_count,
        }
