"""Dataclass models for database rows, with an identity map for shared relations."""

from __future__ import annotations

import contextvars
import json
import logging
from dataclasses import dataclass, field, fields
from sqlite3 import Row
from typing import TYPE_CHECKING, Any, ClassVar, Protocol, TypeVar, overload

from .core import Database

if TYPE_CHECKING:
    from collections.abc import Callable, Iterable

    import aiosqlite

log: logging.Logger = logging.getLogger(f"App.{__name__}")


class DataclassInstance(Protocol):
    """Structural type matching any dataclass, used to bound row_to_dataclass."""

    __dataclass_fields__: ClassVar[dict[str, Any]]


T = TypeVar("T", bound=DataclassInstance)


@overload
def row_to_dataclass(cls: type[T], row: aiosqlite.Row) -> T: ...
@overload
def row_to_dataclass(cls: type[T], row: None) -> None: ...
def row_to_dataclass(cls: type[T], row: aiosqlite.Row | None) -> T | None:
    """Convert a database row into a dataclass object.

    This function maps matching field names from the row to the dataclass parameters.

    Args:
        cls: The dataclass type to create.
        row: The database row to convert. If this value is None, the function returns None.

    Returns:
        An object of type `cls` created from the row, or None if the input row is None.
    """
    if row is None:
        return None
    field_names: set[str] = {f.name for f in fields(cls)}
    params: dict[str, Any] = {key: row[key] for key in set(row.keys()) if key in field_names}
    return cls(**params)


@dataclass
class StaffMember:
    """Store data for one row from the `staff_staff` table."""

    staff_id: int
    name: str
    title: str | None
    timezone: str | None
    discord_id: int
    is_active: bool
    is_blacklisted: bool
    created_at: str
    edited_at: str
    departments: list[Department] = field(default_factory=list, repr=False, compare=False)


@dataclass
class Department:
    """Store data for one row from the `staff_department` table.

    This class parses JSON data from specific table columns.
    """

    key: str
    name: str
    head: int
    configuration: dict[str, Any]
    servers: list[int]
    created_at: str
    edited_at: str
    staffs: list[StaffMember] = field(default_factory=list, repr=False, compare=False)

    @overload
    @classmethod
    def from_row(cls, row: aiosqlite.Row) -> Department: ...
    @overload
    @classmethod
    def from_row(cls, row: None) -> None: ...
    @classmethod
    def from_row(cls, row: aiosqlite.Row | None) -> Department | None:
        """Create a Department object from a database row.

        This method parses the `configuration` and `servers` JSON columns.

        Args:
            row: A row from a query. The database query must convert the `configuration` and `servers` BLOB columns to JSON by using the `json()` function.

        Returns:
            Department | None: A new Department object, or None if the input row is None.
        """
        if row is None:
            return None
        return cls(
            key=row["key"],
            name=row["name"],
            head=row["head"],
            configuration=json.loads(row["configuration"]),
            servers=json.loads(row["servers"]),
            created_at=row["created_at"],
            edited_at=row["edited_at"],
        )


class ModelRegistry:
    """Store active objects to ensure one shared instance exists per identifier.

    Create one instance of this class for each operation or top-level call. Do not use a module-level global instance, or memory usage will increase continuously.
    """

    def __init__(self) -> None:
        self._staff: dict[int, StaffMember] = {}
        self._departments: dict[str, Department] = {}

    def get_staff(self, staff_id: int, factory: Callable[[], StaffMember]) -> StaffMember:
        """Return the saved StaffMember object for the specified ID.

        If the object does not exist in memory, this method creates a new object by using the factory function.

        Args:
            staff_id: The unique identifier for the staff member.
            factory: A function with no parameters that creates a new StaffMember object.

        Returns:
            StaffMember: The shared StaffMember object for the specified ID.
        """
        if staff_id not in self._staff:
            self._staff[staff_id] = factory()
        return self._staff[staff_id]

    def get_department(self, key: str, factory: Callable[[], Department]) -> Department:
        """Return the saved Department object for the specified key.

        If the object does not exist in memory, this method creates a new object by using the factory function.

        Args:
            key: The unique key for the department.
            factory: A function with no parameters that creates a new Department object.

        Returns:
            Department: The shared Department object for the specified key.
        """
        if key not in self._departments:
            self._departments[key] = factory()
        return self._departments[key]


_registry_ctx: contextvars.ContextVar[ModelRegistry] = contextvars.ContextVar("model_registry")


def get_registry() -> ModelRegistry:
    """Get or create the model registry for the current asynchronous task.

    This function gets the registry from the current task context. If no registry exists, the function creates a new registry and saves it to the task context.

    Note:
        Discord.py runs each command or event in a separate asyncio task. Context variables are passed to child tasks, but they are not shared between sibling tasks.
        This behavior ensures that each top-level call has an isolated registry that does not leak into other commands.

    Returns:
        ModelRegistry: The registry for the current context.
    """
    try:
        return _registry_ctx.get()
    except LookupError:
        registry = ModelRegistry()
        _registry_ctx.set(registry)
        return registry


async def load_staff_with_departments(discord_id: int) -> StaffMember | None:
    """Load a StaffMember and its active departments, sharing instances within this task.

    Args:
        discord_id: The Discord user ID of the staff member to load.

    Returns:
        The populated StaffMember with `departments` filled in, or None if not found.
    """
    registry: ModelRegistry = get_registry()
    row: Row | None = await Database().fetchone("SELECT * FROM staff_staff WHERE discord_id = :d", {"d": discord_id})
    if row is None:
        return None

    staff: StaffMember = registry.get_staff(row["staff_id"], lambda: row_to_dataclass(StaffMember, row))

    dept_rows: Iterable[Row] = await Database().fetchall(
        "SELECT json(d.configuration) as configuration, json(d.servers) as servers, "
        "d.key, d.name, d.head, d.created_at, d.edited_at "
        "FROM staff_department d "
        "JOIN staff_staff_department sd ON sd.department_key = d.key "
        "WHERE sd.staff_id = :sid AND sd.is_active = 1",
        {"sid": staff.staff_id},
    )
    for drow in dept_rows:
        dept: Department = registry.get_department(drow["key"], lambda drow=drow: Department.from_row(drow))
        if dept not in staff.departments:
            staff.departments.append(dept)
        if staff not in dept.staffs:
            dept.staffs.append(staff)

    return staff
