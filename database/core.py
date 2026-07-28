"""Core Logic of the Database Interface."""

import logging
from collections.abc import Iterable
from typing import Any, Self

import aiosqlite

from . import _migrations

log = logging.getLogger(f"App.{__name__}")


class Database:
    """Database Interface."""

    instance = None
    _path: str = "app.db"

    def __new__(cls) -> Self:
        """Get the Singleton Instance of Database."""
        if cls.instance is None:
            cls.instance = super().__new__(cls)
        return cls.instance

    async def connect(self, path: str = _path) -> None:
        """Connect to the database."""
        if getattr(self, "_initialized", False):
            return

        log.debug(f"Connecting to DB {path}")
        self.conn = await aiosqlite.connect(path)
        self.conn.row_factory = aiosqlite.Row
        await self.conn.execute("PRAGMA integrity_check")

        await self.conn.execute("PRAGMA foreign_keys = ON")
        await self.conn.execute("PRAGMA journal_mode = WAL")
        await self.conn.execute("PRAGMA busy_timeout = 5000")

        await self._migrate()

        self._initialized = True
        log.info(f"Connected to DB {self._path}")

    async def _migrate(self) -> None:
        cur: aiosqlite.Cursor = await self.conn.execute("PRAGMA user_version")
        _ver = await cur.fetchone()
        cur_version = _ver[0] if _ver else 0
        target_version = len(_migrations.MIGRATIONS)

        assert cur_version <= target_version, f"DB schema version {cur_version} is newer than app expects ({target_version}). Refusing to run."

        for i in range(cur_version, target_version):
            log.debug(f"Applying migration {i + 1}/{target_version}")
            await self.conn.executescript(_migrations.MIGRATIONS[i])
            await self.conn.execute(f"PRAGMA user_version = {i + 1}")
            log.debug(f"Applied migration {i + 1}/{target_version} successfully")

        await self.conn.commit()

    async def execute(self, sql: str, params: tuple[str, ...] | dict[str, Any] = ()) -> aiosqlite.Cursor:
        """Execute the given query."""
        cur = await self.conn.execute(sql, params)
        await self.conn.commit()
        return cur

    async def fetchone(self, sql: str, params: tuple[str, ...] = ()) -> aiosqlite.Row | None:
        """Execute the given query and get 1 result back."""
        cur = await self.conn.execute(sql, params)
        return await cur.fetchone()

    async def fetchall(self, sql: str, params: tuple[str, ...] = ()) -> Iterable[aiosqlite.Row]:
        """Execute the given query and get all results back."""
        cur = await self.conn.execute(sql, params)
        return await cur.fetchall()

    async def close(self) -> None:
        """Close the Database Connection."""
        if getattr(self, "_initialized", False):
            await self.conn.close()
            self._initialized = False
