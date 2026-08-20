"""Integration Testing Configuration of a Bot."""

import json
import logging
import logging.config
import os
import re
from collections.abc import AsyncGenerator
from typing import Any

import pytest

from database.core import Database

_UNSAFE_NAME_CHARS: re.Pattern[str] = re.compile(r"[^A-Za-z0-9_.-]+")

log: logging.Logger = logging.getLogger(f"App.{__name__}")
with open("logging.json", "r", encoding="utf-8") as f:
    _config: dict[str, Any] = json.load(f)
    _config["loggers"]["App"]["handlers"] = ["app_file", "console_debug"]
    _config["handlers"]["console_debug"] = {"class": "logging.StreamHandler", "level": "DEBUG", "formatter": "console"}
    _config["handlers"]["app_file"]["filename"] = "logs/app.testing.log"
    _config["handlers"]["discord_file"]["filename"] = "logs/discord.testing.log"
    config: str = json.dumps(_config)
logging.config.dictConfig(_config)

def pytest_addoption(parser: pytest.Parser) -> None:
    """Register the --db-debug CLI option for on-disk test database inspection.
 
    Args:
        parser: The pytest argument parser to register the option on.
    """
    parser.addoption(
        "--db-debug",
        action="store",
        default=None,
        help="Base path to write test databases to disk (auto-suffixed per test), instead of using :memory:.",
    )

@pytest.fixture(autouse=True)
def reset_singleton() -> None:
    """Ensure a fresh Singleton instance for every test.

    Rationale:
        Prevents state leakage between tests since the Database class utilizes the Singleton pattern.
    """
    Database.instance = None


@pytest.fixture
def db_path(request: pytest.FixtureRequest) -> str:
    """Resolve the database path to use for the current test.

    If --db-debug was passed on the CLI, the base path is suffixed with a sanitized version of the test's node name so that parallel or sequential tests do not stomp on the same file.
    Otherwise, an in-memory database is used.

    Returns:
        The on-disk database path for this test, or ':memory:'.
    """
    base: str | None = request.config.getoption("--db-debug")
    if base is None: 
        return ":memory:"

    safe_name: str = _UNSAFE_NAME_CHARS.sub("_", request.node.name)
    root, ext = os.path.splitext(base)
    ext: str = ext or ".db"
    return f"{root}.{safe_name}{ext}"


@pytest.fixture
async def db(db_path: str) -> AsyncGenerator[Database, None]:
    """Provide a connected database with a test table.

    Rationale:
        Provides an isolated, in-memory/temporary database setup and teardown for tests requiring database interactions.

    Yields:
        Database: A connected database instance initialized with a test table.
    """
    db_instance: Database = Database()
    await db_instance.connect(db_path)
    await db_instance.execute("CREATE TABLE test_table (id INTEGER PRIMARY KEY AUTOINCREMENT, val TEXT)")

    yield db_instance

    await db_instance.close()
