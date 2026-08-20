"""Test the core functionality of the Database."""

import asyncio
from _asyncio import Task
from pathlib import Path

import pytest
from _pytest.mark.structures import MarkDecorator
from aiosqlite import Row

from database import Database

pytestmark: MarkDecorator = pytest.mark.asyncio


class TestDatabasePersistence:
    """Test that data is actually written to disk, not just to an in-memory connection."""

    async def test_data_persists_across_reconnect(self, tmp_path: Path) -> None:
        """Test that a committed row survives closing and reopening the same on-disk file.

        Rationale:
            The `db` fixture uses `:memory:`, which cannot catch persistence bugs since its data disappears on close regardless of whether writes were flushed.
            This test uses a real file so a reconnect can only see data that was actually persisted to disk.

        Args:
            tmp_path: Pytest's built-in temporary directory fixture.

        Assertions:
            - Asserts the row inserted before closing is still readable after a full close/reopen cycle on the same file.
        """
        db_file: str = str(tmp_path / "persistence_test.db")

        writer: Database = Database()
        await writer.connect(db_file)
        await writer.execute("CREATE TABLE test_table (id INTEGER PRIMARY KEY AUTOINCREMENT, val TEXT)")

        query: str = "INSERT INTO test_table (val) VALUES (:val)"  # Insert a row to check for later.
        await writer.execute(query, {"val": "persisted"})
        await writer.close()

        Database.instance = None  # Force a fresh Singleton, simulating a real process restart.
        reader: Database = Database()
        await reader.connect(db_file)

        query = "SELECT val FROM test_table WHERE val = :val"  # Confirm the row survived the reconnect.
        row: Row | None = await reader.fetchone(query, {"val": "persisted"})
        await reader.close()

        assert row is not None, "Expected the row inserted before close() to still exist after reopening the on-disk file"
        assert row["val"] == "persisted", "Expected the persisted value to be unchanged after the reconnect"

    async def test_transaction_commit_persists_across_reconnect(self, tmp_path: Path) -> None:
        """Test that a `transaction()` block's commit is actually flushed to disk, not just to the live connection.

        Rationale:
            `test_transaction_commits` (above) only proves the row is visible on the same connection, which in-memory SQLite would also pass with no disk write. This isolates whether `transaction()`'s commit reaches disk.

        Args:
            tmp_path: Pytest's built-in temporary directory fixture.

        Assertions:
            - Asserts exactly 1 row exists after reconnecting to the file used by the transaction.
        """
        db_file: str = str(tmp_path / "persistence_transaction_test.db")

        writer: Database = Database()
        await writer.connect(db_file)
        await writer.execute("CREATE TABLE test_table (id INTEGER PRIMARY KEY AUTOINCREMENT, val TEXT)")

        query: str = "INSERT INTO test_table (val) VALUES (:val)"  # Insert inside a transaction block.
        async with writer.transaction():
            await writer.execute(query, {"val": "committed"})
        await writer.close()

        Database.instance = None
        reader: Database = Database()
        await reader.connect(db_file)

        query = "SELECT COUNT(*) as count FROM test_table"  # Confirm the transaction's row survived the reconnect.
        row: Row | None = await reader.fetchone(query)
        await reader.close()

        assert row is not None, "Expected a count row to be returned from the reopened database"
        assert row["count"] == 1, "Expected the transaction-committed row to persist to disk after reconnecting"


class TestDatabaseTransaction:
    """Test that transactions are being successfully handled."""

    async def test_transaction_commits(self, db: Database) -> None:
        """Test that a transaction successfully commits on successful execution.

        Rationale:
            Verifies the base functionality (happy path) of the transaction context manager, ensuring queries inside the block are permanently saved upon exit.

        Args:
            db (Database): The injected database fixture.

        Assertions:
            - Asserts that exactly 1 row exists in the table, confirming the insert query within the transaction was committed.
        """
        async with db.transaction():
            await db.execute("INSERT INTO test_table (val) VALUES ('A')")

        row: Row | None = await db.fetchone("SELECT COUNT(*) FROM test_table")
        assert row and row[0] == 1

    async def test_transaction_rolls_back_on_exception(self, db: Database) -> None:
        """Test that a transaction rolls back if an exception occurs.

        Rationale:
            Ensures the atomicity guarantee of the database. If an error is encountered during a transaction block, all prior changes in that block must be undone to prevent partial states.

        Args:
            db (Database): The injected database fixture.

        Assertions:
            - Asserts that a `ValueError` is correctly re-raised out of the block.
            - Asserts that exactly 0 rows exist in the table, confirming the insert query was successfully rolled back.
        """
        with pytest.raises(ValueError, match="Abort"):
            async with db.transaction():
                await db.execute("INSERT INTO test_table (val) VALUES ('A')")
                raise ValueError("Abort")

        row: Row | None = await db.fetchone("SELECT COUNT(*) FROM test_table")
        assert row and row[0] == 0

    async def test_nested_transaction_flattens_and_commits(self, db: Database) -> None:
        """Test that nested transactions flatten and commit together.

        Rationale:
            Verifies the transaction implementation correctly handles savepoints or context flattening from the same async task, avoiding deadlock and committing everything when the outermost block exits safely.

        Args:
            db (Database): The injected database fixture.

        Assertions:
            - Asserts that exactly 2 rows exist, proving that queries from both the outer and inner transaction blocks were committed.
        """
        async with db.transaction():
            await db.execute("INSERT INTO test_table (val) VALUES ('Outer')")

            async with db.transaction():
                await db.execute("INSERT INTO test_table (val) VALUES ('Inner')")

        row: Row | None = await db.fetchone("SELECT COUNT(*) FROM test_table")
        assert row and row[0] == 2

    async def test_nested_transaction_rolls_back_entirely_from_inner(self, db: Database) -> None:
        """Test that an exception in an inner transaction rolls back everything.

        Rationale:
            Ensures that flattened transactions behave as a single atomic unit. A failure deep inside nested blocks must trigger a complete rollback of the outermost transaction.

        Args:
            db (Database): The injected database fixture.

        Assertions:
            - Asserts that a `RuntimeError` propagates correctly.
            - Asserts that exactly 0 rows exist, proving the outer insert was rolled back along with the aborted inner transaction.
        """
        with pytest.raises(RuntimeError):
            async with db.transaction():
                await db.execute("INSERT INTO test_table (val) VALUES ('Outer')")

                async with db.transaction():
                    await db.execute("INSERT INTO test_table (val) VALUES ('Inner')")
                    raise RuntimeError("Fail inner")

        row: Row | None = await db.fetchone("SELECT COUNT(*) FROM test_table")
        assert row and row[0] == 0

    async def test_concurrent_transactions_maintain_isolation(self, db: Database) -> None:
        """Test that multiple async tasks respect database locks.

        Rationale:
            Asynchronous database connections require strict locking mechanisms (`_acquire`/`_release`) to prevent distinct async tasks from interfering with each other's transactions via connection sharing.

        Args:
            db (Database): The injected database fixture.

        Assertions:
            - Asserts that exactly 10 rows exist, confirming all 10 concurrent tasks acquired the lock securely and committed their inserts without dropping data or deadlocking.
        """

        async def worker(worker_id: int) -> None:
            async with db.transaction():
                await asyncio.sleep(0.01)
                await db.execute(f"INSERT INTO test_table (val) VALUES ('{worker_id}')")
                await asyncio.sleep(0.01)

        tasks: list[Task[None]] = [asyncio.create_task(worker(i)) for i in range(10)]
        await asyncio.gather(*tasks)

        row: Row | None = await db.fetchone("SELECT COUNT(*) FROM test_table")
        assert row and row[0] == 10

    async def test_stress_concurrent_mixed_transactions(self, db: Database) -> None:
        """Stress test the transaction block with concurrent mixed outcomes.

        Rationale:
            Simulates real-world high load where multiple async queries are firing simultaneously, yielding to the event loop, and randomly failing. Proves the lock mechanism and rollback functionality are stable under pressure.

        Args:
            db (Database): The injected database fixture.

        Assertions:
            - Asserts that exactly 160 rows exist. 100 workers are spawned; 20 fail and rollback (0 rows), 80 succeed and commit 2 inserts each (160 rows).
        """

        async def stress_worker(worker_id: int) -> None:
            try:
                async with db.transaction():
                    await db.execute(f"INSERT INTO test_table (val) VALUES ('{worker_id}')")
                    await asyncio.sleep(0)

                    if worker_id % 5 == 0:
                        raise CustomError("Simulated failure")

                    await db.execute(f"INSERT INTO test_table (val) VALUES ('{worker_id}_second')")
            except CustomError:
                pass

        class CustomError(Exception):
            pass

        tasks: list[Task[None]] = [asyncio.create_task(stress_worker(i)) for i in range(100)]
        await asyncio.gather(*tasks)

        row: Row | None = await db.fetchone("SELECT COUNT(*) FROM test_table")
        assert row and row[0] == 160


class TestReturningClausePersistence:
    """Test that INSERT ... RETURNING statements are both fetchable and actually committed to disk."""

    async def test_returning_clause_row_is_immediately_fetchable(self, tmp_path: Path) -> None:
        """Test that the cursor from an INSERT ... RETURNING statement yields the inserted row.

        Rationale:
            Confirms the RETURNING data itself is readable off the cursor, independent of whether the write was persisted.
            Isolates "can I read RETURNING" from "did RETURNING break the commit" (covered by the other tests).

        Args:
            tmp_path: Pytest's built-in temporary directory fixture.

        Assertions:
            - Asserts the cursor returns exactly one row matching the inserted value.
        """
        db_file: str = str(tmp_path / "returning_fetch_test.db")

        db_instance: Database = Database()
        await db_instance.connect(db_file)
        await db_instance.execute("CREATE TABLE test_table (id INTEGER PRIMARY KEY AUTOINCREMENT, val TEXT)")

        query: str = "INSERT INTO test_table (val) VALUES (:val) RETURNING id, val"  # Insert and read back in one statement.
        row: Row | None = await db_instance.fetchone(query, {"val": "returned"})
        await db_instance.close()

        assert row is not None, "Expected the RETURNING clause to yield the inserted row on the cursor"
        assert row["val"] == "returned", "Expected the returned row to match the value that was inserted"

    async def test_returning_clause_persists_within_transaction(self, tmp_path: Path) -> None:
        """Test that an INSERT ... RETURNING inside a transaction() block is committed on block exit.

        Rationale:
            Verifies RETURNING doesn't interfere with the outer transaction's commit logic when used as part of a larger atomic operation.

        Args:
            tmp_path: Pytest's built-in temporary directory fixture.

        Assertions:
            - Asserts the RETURNING row persists to disk after the transaction block exits and the connection is reopened.
        """
        db_file: str = str(tmp_path / "returning_transaction_persist_test.db")

        writer: Database = Database()
        await writer.connect(db_file)
        await writer.execute("CREATE TABLE test_table (id INTEGER PRIMARY KEY AUTOINCREMENT, val TEXT)")

        query: str = "INSERT INTO test_table (val) VALUES (:val) RETURNING id, val"  # RETURNING nested inside an explicit transaction.
        async with writer.transaction():
            row: Row | None = await writer.fetchone(query, {"val": "tx_returned"})
            assert row is not None, "Expected the RETURNING row to be readable while still inside the transaction block"
        await writer.close()

        Database.instance = None
        reader: Database = Database()
        await reader.connect(db_file)

        query = "SELECT val FROM test_table WHERE val = :val"  # Confirm the transaction committed the RETURNING insert.
        persisted_row: Row | None = await reader.fetchone(query, {"val": "tx_returned"})
        await reader.close()

        assert persisted_row is not None, "Expected the INSERT ... RETURNING row to persist after the transaction() block committed"

    async def test_returning_clause_rolls_back_on_exception(self, tmp_path: Path) -> None:
        """Test that an INSERT ... RETURNING inside a failed transaction is rolled back, not persisted.

        Rationale:
            Guards against the opposite failure mode: RETURNING accidentally forcing an early/independent commit that survives even when the surrounding transaction raises and should roll everything back.

        Args:
            tmp_path: Pytest's built-in temporary directory fixture.

        Assertions:
            - Asserts the `ValueError` propagates out of the transaction block.
            - Asserts no row exists on disk after reconnecting, confirming the RETURNING insert was rolled back.
        """
        db_file: str = str(tmp_path / "returning_rollback_test.db")

        writer: Database = Database()
        await writer.connect(db_file)
        await writer.execute("CREATE TABLE test_table (id INTEGER PRIMARY KEY AUTOINCREMENT, val TEXT)")

        query: str = "INSERT INTO test_table (val) VALUES (:val) RETURNING id, val"  # Insert that should be undone by the rollback.
        with pytest.raises(ValueError, match="boom"):
            async with writer.transaction():
                await writer.fetchone(query, {"val": "should_not_persist"})
                raise ValueError("boom")
        await writer.close()

        Database.instance = None
        reader: Database = Database()
        await reader.connect(db_file)

        query = "SELECT COUNT(*) as count FROM test_table"  # Confirm the RETURNING insert was rolled back, not just uncommitted in memory.
        row: Row | None = await reader.fetchone(query)
        await reader.close()

        assert row is not None, "Expected a count row to be returned from the reopened database"
        assert row["count"] == 0, "Expected the RETURNING insert to be rolled back and absent after reconnecting"

    async def test_multiple_sequential_returning_inserts_all_persist(self, tmp_path: Path) -> None:
        """Test that several independent INSERT ... RETURNING calls each persist, not just the last one.

        Rationale:
            Checks for a bug where only the final statement's commit (or none at all) actually reaches disk when RETURNING statements are issued back-to-back outside a shared transaction.

        Args:
            tmp_path: Pytest's built-in temporary directory fixture.

        Assertions:
            - Asserts all 3 independently inserted rows are present after reconnecting.
        """
        db_file: str = str(tmp_path / "returning_multi_insert_test.db")

        writer: Database = Database()
        await writer.connect(db_file)
        await writer.execute("CREATE TABLE test_table (id INTEGER PRIMARY KEY AUTOINCREMENT, val TEXT)")

        query: str = "INSERT INTO test_table (val) VALUES (:val) RETURNING id, val"  # Three separate auto-commit statements.
        for val in ("first", "second", "third"):
            result: Row | None = await writer.fetchone(query, {"val": val})
            assert result, "RETURNING did not return anything."
            assert result["val"] == val, "RETURNING did not return the correct values."
        await writer.close()

        Database.instance = None
        reader: Database = Database()
        await reader.connect(db_file)

        query = "SELECT COUNT(*) as count FROM test_table"  # Confirm every prior RETURNING insert persisted, not just the latest.
        row: Row | None = await reader.fetchone(query)
        await reader.close()

        assert row is not None, "Expected a count row to be returned from the reopened database"
        assert row["count"] == 3, "Expected all three RETURNING inserts to persist independently to disk"


class TestExecuteRejectsReturning:
    """Test that execute() refuses RETURNING statements instead of silently dropping the write."""

    async def test_execute_raises_on_returning_clause(self, db: Database) -> None:
        """Test that execute() raises ValueError for any statement containing RETURNING.

        Rationale:
            execute() commits before draining the cursor, so RETURNING statements either
            raise `sqlite3.OperationalError` or, if swallowed upstream, silently fail to
            commit. This guard turns that failure mode into an explicit, immediate error.

        Args:
            db: The injected database fixture.

        Assertions:
            - Asserts a `ValueError` is raised for an INSERT ... RETURNING statement.
        """
        query: str = "INSERT INTO test_table (val) VALUES (:val) RETURNING id, val"  # Disallowed by execute().

        with pytest.raises(ValueError, match="RETURNING"):
            await db.execute(query, {"val": "should_be_rejected"})

    async def test_execute_raises_on_lowercase_returning_clause(self, db: Database) -> None:
        """Test that the RETURNING guard is case-insensitive.

        Rationale:
            SQL keywords are case-insensitive in SQLite; the guard must not be bypassable
            just by writing the clause in lowercase.

        Args:
            db: The injected database fixture.

        Assertions:
            - Asserts a `ValueError` is raised for a lowercase `returning` clause.
        """
        query: str = "insert into test_table (val) values (:val) returning id, val"  # Lowercase variant.

        with pytest.raises(ValueError, match="RETURNING"):
            await db.execute(query, {"val": "should_be_rejected"})

    async def test_rejected_returning_statement_is_not_committed(self, tmp_path: Path) -> None:
        """Test that a rejected RETURNING statement leaves no partial write on disk.

        Rationale:
            Confirms the guard fires before the write reaches the database, not after —
            so no half-committed row is left behind by the raise.

        Args:
            tmp_path: Pytest's built-in temporary directory fixture.

        Assertions:
            - Asserts no row exists on disk after reconnecting, following the rejected call.
        """
        db_file: str = str(tmp_path / "returning_guard_test.db")

        writer: Database = Database()
        await writer.connect(db_file)
        await writer.execute("CREATE TABLE test_table (id INTEGER PRIMARY KEY AUTOINCREMENT, val TEXT)")

        query: str = "INSERT INTO test_table (val) VALUES (:val) RETURNING id, val"  # Expected to raise, not write.
        with pytest.raises(ValueError, match="RETURNING"):
            await writer.execute(query, {"val": "should_not_persist"})
        await writer.close()

        Database.instance = None
        reader: Database = Database()
        await reader.connect(db_file)

        query = "SELECT COUNT(*) as count FROM test_table"  # Confirm nothing was written before the raise.
        row: Row | None = await reader.fetchone(query)
        await reader.close()

        assert row is not None, "Expected a count row to be returned from the reopened database"
        assert row["count"] == 0, "Expected the rejected RETURNING statement to leave no row on disk"
