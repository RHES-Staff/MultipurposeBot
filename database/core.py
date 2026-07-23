import logging
import aiosqlite

from . import _migrations

log = logging.getLogger(f"App.{__name__}")


class Database:
    instance = None
    _path = "app.db"

    def __new__(cls):
        if cls.instance is None:
            cls.instance = super().__new__(cls)
        return cls.instance

    async def connect(self):
        if getattr(self, "_initialized", False):
            return
        
        try:
            log.debug(f"Connecting to DB {self._path}")
            self.conn = await aiosqlite.connect(self._path)
        except Exception:
            raise Exception("Cannot connect to the database.")

        await self.conn.execute("PRAGMA foreign_keys = ON")
        await self.conn.execute("PRAGMA journal_mode = WAL")
        await self.conn.execute("PRAGMA busy_timeout = 5000")

        await self._migrate()

        self._initialized = True
        log.debug(f"Connected to DB {self._path}")

    async def _migrate(self):
        cur = await self.conn.execute("PRAGMA user_version")
        cur_version = (await cur.fetchone())[0]
        target_version = len(_migrations.MIGRATIONS)

        if cur_version > target_version:
            raise Exception(
                f"DB schema version {cur_version} is newer than app expects "
                f"({target_version}). Refusing to run."
            )

        for i in range(cur_version, target_version):
            log.debug(f"Applying migration {i + 1}/{target_version}")
            await self.conn.executescript(_migrations.MIGRATIONS[i])
            await self.conn.execute(f"PRAGMA user_version = {i + 1}")
            log.debug(f"Applied migration {i + 1}/{target_version} successfully")

        await self.conn.commit()

    async def execute(self, sql, params=()):
        cur = await self.conn.execute(sql, params)
        await self.conn.commit()
        return cur

    async def fetchone(self, sql, params=()):
        cur = await self.conn.execute(sql, params)
        return await cur.fetchone()

    async def fetchall(self, sql, params=()):
        cur = await self.conn.execute(sql, params)
        return await cur.fetchall()

    async def close(self):
        if getattr(self, "_initialized", False):
            await self.conn.close()
            self._initialized = False
