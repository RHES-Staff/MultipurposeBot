"""Dataclass models for database rows."""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any, overload

from . import department, notes, staff, tags

if TYPE_CHECKING:
    import aiosqlite

log: logging.Logger = logging.getLogger(f"App.{__name__}")


@dataclass
class StaffMember:
    """Store data for one row from the staff table.

    Attributes:
        staff_id: The unique identifier for the staff member.
        name: The display name of the staff member.
        title: The job title or role description, if assigned.
        timezone: The primary timezone string, if set.
        discord_id: The unique Discord account identifier.
        is_active: Whether the staff account is currently active.
        is_blacklisted: Whether the staff member is restricted from system access.
        created_at: The timestamp string when the record was created.
        edited_at: The timestamp string when the record was last updated.
        departments: A list of summarized departments associated with the
            staff member.
    """

    staff_id: int
    name: str
    title: str | None
    timezone: str | None
    discord_id: int
    is_active: bool
    is_blacklisted: bool
    created_at: str
    edited_at: str
    departments: list[DepartmentSummary] = field(default_factory=list, repr=False, compare=False)
    tags: list[TagSummary] = field(default_factory=list, repr=False, compare=False)

    @overload
    @classmethod
    async def from_row(cls, row: aiosqlite.Row) -> StaffMember: ...
    @overload
    @classmethod
    async def from_row(cls, row: None) -> None: ...
    @classmethod
    async def from_row(cls, row: aiosqlite.Row | None):
        """Create a staff member instance from a database row.

        Args:
            row: A database query result row, or None.

        Returns:
            A populated StaffMember instance, or None if the input row is None.
        """
        if row is None:
            return None
        departments: list[DepartmentSummary] = await staff.get_staff_departments(staff_id=row["staff_id"], shallow=True)
        staff_tags: list[TagSummary] = await tags.get_staff_tags(staff_id=row["staff_id"], shallow=True)
        return cls(
            staff_id=row["staff_id"],
            name=row["name"],
            title=row["title"],
            timezone=row["timezone"],
            discord_id=row["discord_id"],
            is_active=bool(row["is_active"]),
            is_blacklisted=bool(row["is_blacklisted"]),
            created_at=row["created_at"],
            edited_at=row["edited_at"],
            departments=departments,
            tags=staff_tags,
        )

    async def get_all_departments(self) -> list[Department]:
        """Fetch full department data for the staff member.

        Returns:
            A list of complete Department objects associated with this staff member.
        """
        return await staff.get_staff_departments(staff_id=self.staff_id, shallow=False)

    @property
    async def notes(self) -> list[Note]:
        """Fetch full note data for the staff member.

        Returns:
            A list of all notes made for the staff member.
        """
        return await notes.get_notes(self.staff_id)


@dataclass
class StaffSummary:
    """Store summary data for a staff member.

    Attributes:
        staff_id: The unique identifier for the staff member.
        name: The display name of the staff member.
        discord_id: The unique Discord account identifier.
    """

    staff_id: int
    name: str
    discord_id: str

    @overload
    @classmethod
    def from_row(cls, row: aiosqlite.Row) -> StaffSummary: ...
    @overload
    @classmethod
    def from_row(cls, row: None) -> None: ...
    @classmethod
    def from_row(cls, row: aiosqlite.Row | None):
        """Create a staff summary instance from a database row.

        Args:
            row: A database query result row, or None.

        Returns:
            A populated StaffSummary instance, or None if the input row is None.
        """
        if row is None:
            return None
        return cls(staff_id=row["staff_id"], name=row["name"], discord_id=row["discord_id"])

    async def hydrate(self) -> StaffMember | None:
        """Fetch full staff details using the summary identifier.

        Returns:
            The complete StaffMember instance if found, or None.
        """
        return await staff.get_staff(staff_id=self.staff_id)


@dataclass
class Department:
    """Store data for one row from the department table.

    Attributes:
        key: The unique string identifier for the department.
        name: The display name of the department.
        head: A summarized staff record representing the department lead.
        configuration: Settings and rules defined for the department.
        servers: A list of associated Discord server identifiers.
        created_at: The timestamp string when the record was created.
        edited_at: The timestamp string when the record was last updated.
        staffs: A list of summarized staff members belonging to the
            department.
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
    async def from_row(cls, row: aiosqlite.Row) -> Department: ...
    @overload
    @classmethod
    async def from_row(cls, row: None) -> None: ...
    @classmethod
    async def from_row(cls, row: aiosqlite.Row | None) -> Department | None:
        """Create a department instance from a database row.

        Args:
            row: A database query result row, or None. The row must contain JSON string columns for configuration and servers, alongside department head details.

        Returns:
            A populated Department instance, or None if the input row is None.
        """
        if row is None:
            return None
        staffs: list[StaffSummary] = await department.get_department_staffs(row["key"], shallow=True)
        return cls(
            key=row["key"],
            name=row["name"],
            head=StaffSummary(staff_id=row["head_id"], name=row["head_name"], discord_id=str(row["head_discord_id"])),
            configuration=json.loads(row["configuration"]),
            servers=json.loads(row["servers"]),
            created_at=row["created_at"],
            edited_at=row["edited_at"],
            staffs=staffs,
        )

    async def get_all_staffs(self) -> list[StaffMember]:
        """Fetch full staff data for all members in the department.

        Returns:
            A list of complete StaffMember objects belonging to this department.
        """
        return await department.get_department_staffs(self.key, shallow=False)


@dataclass
class DepartmentSummary:
    """Store summary data for a department.

    Attributes:
        key: The unique string identifier for the department.
        name: The display name of the department.
    """

    key: str
    name: str

    @classmethod
    def from_row(cls, row: aiosqlite.Row) -> DepartmentSummary:
        """Create a department summary instance from a database row.

        Args:
            row: A database query result row containing key and name fields.

        Returns:
            A populated DepartmentSummary instance.
        """
        return cls(key=row["key"], name=row["name"])

    async def hydrate(self) -> Department | None:
        """Fetch full department details using the summary key.

        Returns:
            The complete Department instance if found, or None.
        """
        return await department.get_department(self.key)


@dataclass
class Note:
    """Store data for one row from the staff_notes table.

    Attributes:
        id: The unique ID of the note.
        staff_id: The staff member the note is about.
        note: The text content of the note.
        noter: The staff ID of the author.
        created_at: The timestamp string when the note was made.
        edited_at: The timestamp string when the note was last changed.
    """

    id: int
    staff_id: int
    note: str
    noter: int
    created_at: str
    edited_at: str

    @classmethod
    def from_row(cls, row: aiosqlite.Row) -> Note:
        """Create a note instance from a database row.

        Args:
            row: A database query result row.

        Returns:
            A populated Note instance.
        """
        return cls(**dict(row))


@dataclass
class Tag:
    """Store data for one row from the asset_tags table.

    Attributes:
        id: The unique ID of the tag.
        name: The display name of the tag.
        color: The hex color code of the tag.
        created_at: The timestamp string when the tag was made.
        edited_at: The timestamp string when the tag was last changed.
    """

    id: int
    name: str
    color: str
    created_at: str
    edited_at: str

    @classmethod
    def from_row(cls, row: aiosqlite.Row) -> Tag:
        """Create a tag instance from a database row.

        Args:
            row: A database query result row.

        Returns:
            A populated Tag instance.
        """
        return cls(**dict(row))


@dataclass
class TagSummary:
    """Store summary data for a tag.

    Attributes:
        id: The unique ID of the tag.
        name: The display name of the tag.
        color: The hex color code of the tag.
    """

    id: int
    name: str
    color: str

    @classmethod
    def from_row(cls, row: aiosqlite.Row) -> TagSummary:
        """Create a tag summary instance from a database row.

        Args:
            row: A database query result row containing id, name, and color fields.

        Returns:
            A populated TagSummary instance.
        """
        return cls(id=row["id"], name=row["name"], color=row["color"])

    async def hydrate(self) -> Tag | None:
        """Fetch full tag details using the summary ID.

        Returns:
            The complete Tag instance if found, or None.
        """
        staff_tags: list[Tag] = await tags.get_all_tags()
        return next((t for t in staff_tags if t.id == self.id), None)
