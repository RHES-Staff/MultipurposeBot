"""Dataclass models for database rows."""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass, field, fields
from typing import TYPE_CHECKING, Any, ClassVar, Protocol, TypeVar, overload

if TYPE_CHECKING:
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
class DepartmentSummary:
    """Store the minimal identity of a department, for shallow embedding in other rows."""

    key: str
    name: str

@dataclass
class StaffMember:
    """Store data for one row from the `staff_staff` table."""

    staff_id: int
    name: str
    title: str | None
    timezone: str | None
    discord_id: str
    is_active: bool
    is_blacklisted: bool
    created_at: str
    edited_at: str
    departments: list[Department | DepartmentSummary] = field(default_factory=list, repr=False, compare=False)


@dataclass
class StaffSummary:
    """Store the minimal identity of a staff member, for shallow embedding in other rows."""

    staff_id: int
    name: str
    discord_id: str


@dataclass
class Department:
    """Store data for one row from the `staff_department` table.

    This class parses JSON data from specific table columns.
    """

    key: str
    name: str
    head: StaffSummary
    configuration: dict[str, Any]
    servers: list[int]
    created_at: str
    edited_at: str
    staffs: list[StaffSummary] = field(default_factory=list, repr=False, compare=False)

    @overload
    @classmethod
    def from_row(cls, row: aiosqlite.Row) -> Department: ...
    @overload
    @classmethod
    def from_row(cls, row: None) -> None: ...
    @classmethod
    def from_row(cls, row: aiosqlite.Row | None) -> Department | None:
        """Create a Department object from a database row.

        This method parses the `configuration` and `servers` JSON columns, and builds a shallow `StaffSummary` for the department head.

        Args:
            row: A row from a query. The database query must convert the `configuration` and `servers` BLOB columns to JSON by using the `json()` function, and must include `head_id` and `head_name` columns (the head's `staff_id` and `name`).

        Returns:
            Department | None: A new Department object, or None if the input row is None.
        """
        if row is None:
            return None
        return cls(
            key=row["key"],
            name=row["name"],
            head=StaffSummary(staff_id=row["head_id"], name=row["head_name"], discord_id=str(row['head_discord_id'])),
            configuration=json.loads(row["configuration"]),
            servers=json.loads(row["servers"]),
            created_at=row["created_at"],
            edited_at=row["edited_at"],
        )
