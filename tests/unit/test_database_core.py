"""Test the core functionality of the Database."""

import asyncio
from _asyncio import Task
from collections.abc import AsyncGenerator
from sqlite3 import Row

import pytest
from _pytest.mark.structures import MarkDecorator

from database import Database

pytestmark: MarkDecorator = pytest.mark.asyncio


@pytest.fixture(autouse=True)
def reset_singleton() -> None:
    """Ensure a fresh Singleton instance for every test.

    Rationale:
        Prevents state leakage between tests since the Database class utilizes the Singleton pattern.
    """
    Database.instance = None


@pytest.fixture
async def db() -> AsyncGenerator[Database, None]:
    """Provide a connected database with a test table.

    Rationale:
        Provides an isolated, in-memory/temporary database setup and teardown for tests requiring database interactions.

    Yields:
        Database: A connected database instance initialized with a test table.
    """
    db_instance = Database()
    await db_instance.connect(":memory:")
    await db_instance.execute("CREATE TABLE test_table (id INTEGER PRIMARY KEY AUTOINCREMENT, val TEXT)")

    yield db_instance

    await db_instance.close()


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
