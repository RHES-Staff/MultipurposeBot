"""Core Logic of the Database Interface."""

from __future__ import annotations

import asyncio
import logging
import re
import time
from contextlib import asynccontextmanager
from typing import TYPE_CHECKING, Any, Self

import aiosqlite

from . import _migrations

if TYPE_CHECKING:
    from collections.abc import AsyncIterator, Iterable

log: logging.Logger = logging.getLogger(f"App.{__name__}")


class Database:
    """Database Interface."""

    instance = None
    _path: str = "app.db"
    _RETURNING_PATTERN: re.Pattern[str] = re.compile(r"\bRETURNING\b", re.IGNORECASE)

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

        self._lock: asyncio.Lock = asyncio.Lock()
        self._lock_owner: asyncio.Task | None = None
        self._txn_depth: int = 0

        self._initialized = True
        log.info(f"Connected to DB {path}")

    async def _migrate(self) -> None:
        cur: aiosqlite.Cursor = await self.conn.execute("PRAGMA user_version")
        _ver = await cur.fetchone()
        cur_version: int = _ver[0] if _ver else 0
        target_version: int = len(_migrations.MIGRATIONS)

        assert cur_version <= target_version, f"DB schema version {cur_version} is newer than app expects ({target_version}). Refusing to run."

        for i in range(cur_version, target_version):
            log.debug(f"Applying migration {i + 1}/{target_version}")
            await self.conn.executescript(_migrations.MIGRATIONS[i])
            await self.conn.execute(f"PRAGMA user_version = {i + 1}")
            log.debug(f"Applied migration {i + 1}/{target_version} successfully")

        await self.conn.commit()

    async def _acquire(self) -> bool:
        """Acquire the connection lock, unless the current task already owns it.

        Returns:
            bool: True if this call acquired the lock and is responsible for releasing it. False if the current task already holds it (e.g. a query running inside its own `transaction()` block).
        """
        if self._lock_owner is asyncio.current_task():
            return False
        await self._lock.acquire()
        self._lock_owner = asyncio.current_task()
        return True

    def _release(self) -> None:
        """Release the connection lock and clear ownership."""
        self._lock_owner = None
        self._lock.release()

    @asynccontextmanager
    async def transaction(self) -> AsyncIterator[Self]:
        """Group one or more queries into a single atomic transaction.

        Nested calls from the same task flatten into the outermost transaction: only the outermost block commits or rolls back.

        Yields:
            Self: The database instance, so `execute`/`fetchone`/`fetchall` run within the transaction.

        Raises:
            Exception: Re-raised after rolling back all changes made in the outermost transaction block.
        """
        acquired: bool = await self._acquire()
        self._txn_depth += 1
        try:
            yield self
            if self._txn_depth == 1:
                await self.conn.commit()
        except Exception:
            if self._txn_depth == 1:
                await self.conn.rollback()
            raise
        finally:
            self._txn_depth -= 1
            if acquired:
                self._release()

    async def execute(self, sql: str, params: tuple[str, ...] | dict[str, Any] = ()) -> aiosqlite.Cursor:
        """Execute the given query.

        Raises:
            ValueError: The SQL has a RETURNING clause. Commit runs before rows are read, so this fails or drops the write. Use `fetchone` or `fetchall` instead.
        """
        if self._RETURNING_PATTERN.search(sql):
            raise ValueError("execute() does not support RETURNING clauses; use fetchone() or fetchall() instead.")

        acquired: bool = await self._acquire()
        try:
            start: int | float = time.perf_counter()
            cur: aiosqlite.Cursor = await self.conn.execute(sql, params)
            if self._txn_depth == 0:
                await self.conn.commit()
            elapsed: int | float = time.perf_counter() - start
            log.debug("Query executed.", extra={"sql": " ".join(sql.split()), "params": params, "exec_time": elapsed, "in_transaction": self._txn_depth > 0})
            return cur
        finally:
            if acquired:
                self._release()

    async def fetchone(self, sql: str, params: tuple[str, ...] | dict[str, Any] = ()) -> aiosqlite.Row | None:
        """Execute the given query and get 1 result back."""
        acquired: bool = await self._acquire()
        try:
            start: int | float = time.perf_counter()
            cur: aiosqlite.Cursor = await self.conn.execute(sql, params)
            result: aiosqlite.Row | None = await cur.fetchone()
            if self._txn_depth == 0:
                await self.conn.commit()
            elapsed: int | float = time.perf_counter() - start
            log.debug("Query executed.", extra={"sql": " ".join(sql.split()), "params": params, "exec_time": elapsed, "in_transaction": self._txn_depth > 0})
            return result
        finally:
            if acquired:
                self._release()

    async def fetchall(self, sql: str, params: tuple[str, ...] | dict[str, Any] = ()) -> Iterable[aiosqlite.Row]:
        """Execute the given query and get all results back."""
        acquired: bool = await self._acquire()
        try:
            start: int | float = time.perf_counter()
            cur: aiosqlite.Cursor = await self.conn.execute(sql, params)
            result: Iterable[aiosqlite.Row] = await cur.fetchall()
            if self._txn_depth == 0:
                await self.conn.commit()
            elapsed: int | float = time.perf_counter() - start
            log.debug("Query executed.", extra={"sql": " ".join(sql.split()), "params": params, "exec_time": elapsed, "in_transaction": self._txn_depth > 0})
            return result
        finally:
            if acquired:
                self._release()

    async def close(self) -> None:
        """Close the Database Connection."""
        if getattr(self, "_initialized", False):
            await self.conn.close()
            self._initialized = False
