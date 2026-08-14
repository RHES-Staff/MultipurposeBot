"""Core Logic of the Database Interface."""

from __future__ import annotations

import logging
import time
from typing import TYPE_CHECKING, Any, Self

import aiosqlite

from . import _migrations

if TYPE_CHECKING:
    from collections.abc import Iterable

log: logging.Logger = logging.getLogger(f"App.{__name__}")


class Database:
    """Database Interface."""

    instance = None
    _path: str = "app.db"

    def __new__(cls) -> Self:
        """Get the Singleton Instance of Database."""
        if cls.instance is None:
            cls.instance = super().__new__(cls)
        return cls.instance

    def __init__(self, path: str = _path) -> None:
        if getattr(self, "_initialized", False):
            return

    async def connect(self, path: str = _path) -> None:
        """Connect to the database."""
        if getattr(self, "_initialized", False):
            return

        self.conn: aiosqlite.Connection = await aiosqlite.connect(path)
        self.conn.row_factory = aiosqlite.Row

        await self.conn.execute("PRAGMA foreign_keys = ON")
        await self.conn.execute("PRAGMA journal_mode = WAL")
        await self.conn.execute("PRAGMA busy_timeout = 5000")
        await self.conn.execute("PRAGMA cache_size = -32767;")
        await self.conn.execute("PRAGMA temp_store = MEMORY;")
        await self.conn.execute("PRAGMA mmap_size = 33554432;")
        await self.conn.execute("PRAGMA synchronous = NORMAL")
        await self.conn.execute("PRAGMA wal_autocheckpoint = 500")
        await self._migrate()

        self._initialized = True
        log.info(f"Connected to DB {path}")

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
        start: int | float = time.perf_counter()
        try:
            cur: aiosqlite.Cursor = await self.conn.execute(sql, params)
            await self.conn.commit()
        except:
            log.error("Query returned an error.", extra={"sql": " ".join(sql.split()), "params": params})
            raise
        elapsed: int | float = time.perf_counter() - start
        log.debug("Query executed.", extra={"sql": " ".join(sql.split()), "params": params, "exec_time": elapsed})
        return cur

    async def fetchone(self, sql: str, params: tuple[str, ...] | dict[str, Any] = ()) -> aiosqlite.Row | None:
        """Execute the given query and get 1 result back."""
        start: int | float = time.perf_counter()
        try:
            cur: aiosqlite.Cursor = await self.conn.execute(sql, params)
            result: aiosqlite.Row | None = await cur.fetchone()
        except:
            log.error("Query returned an error.", extra={"sql": " ".join(sql.split()), "params": params})
            raise
        elapsed: int | float = time.perf_counter() - start
        log.debug("Query executed.", extra={"sql": " ".join(sql.split()), "params": params, "exec_time": elapsed})
        return result

    async def fetchall(self, sql: str, params: tuple[str, ...] | dict[str, Any] = ()) -> Iterable[aiosqlite.Row]:
        """Execute the given query and get all results back."""
        start: int | float = time.perf_counter()
        try:
            cur: aiosqlite.Cursor = await self.conn.execute(sql, params)
            result: Iterable[aiosqlite.Row] = await cur.fetchall()
        except:
            log.error("Query returned an error.", extra={"sql": " ".join(sql.split()), "params": params})
            raise
        elapsed: int | float = time.perf_counter() - start
        log.debug("Query executed.", extra={"sql": " ".join(sql.split()), "params": params, "exec_time": elapsed})
        return result

    async def close(self) -> None:
        """Close the Database Connection."""
        if getattr(self, "_initialized", False):
            await self.conn.close()
            self._initialized = False
