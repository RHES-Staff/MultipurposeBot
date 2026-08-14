"""Common Tag Operations on Database."""

from __future__ import annotations

from typing import TYPE_CHECKING, cast

from aiosqlite import Row

from . import models
from .core import Database

if TYPE_CHECKING:
    from collections.abc import Iterable

    import aiosqlite


# Create
async def create_tag(name: str, color: str = "#808080") -> models.Tag:
    """Create a new tag in the tag catalog.

    Args:
        name: The display name of the tag.
        color: The hex color code for the tag.

    Returns:
        models.Tag: The new tag.
    """
    db = Database()
    result: Row = cast(Row, await db.fetchone("INSERT INTO asset_tags (name, color) VALUES (:name, :color) RETURNING *;", {"name": name, "color": color}))
    return models.Tag.from_row(result)


async def tag_staff(staff_id: int, tag_id: int, tagged_by: int) -> None:
    """Assign a tag to a staff member.

    Args:
        staff_id: The staff member to tag.
        tag_id: The unique ID of the tag to assign.
        tagged_by: The staff ID of the member who assigns the tag.

    Raises:
        ValueError: If the staff member already has the tag.
    """
    db = Database()
    existing: aiosqlite.Row | None = await db.fetchone(
        "SELECT id FROM staff_tags WHERE staff_id = :staff_id AND tag_id = :tag_id;",
        {"staff_id": staff_id, "tag_id": tag_id},
    )
    if existing is not None:
        raise ValueError(f"Staff ID {staff_id} already has tag ID {tag_id}.")
    await db.execute(
        "INSERT INTO staff_tags (staff_id, tag_id, tagged_by) VALUES (:staff_id, :tag_id, :tagged_by);",
        {"staff_id": staff_id, "tag_id": tag_id, "tagged_by": tagged_by},
    )


# Read
async def get_all_tags() -> list[models.Tag]:
    """Get every tag in the tag catalog.

    Returns:
        list[models.Tag]: All registered tags.
    """
    query = "SELECT * FROM asset_tags ORDER BY name;"
    db = Database()
    rows: Iterable[aiosqlite.Row] = await db.fetchall(query)
    return [models.Tag.from_row(row) for row in rows]


async def get_staff_tags(staff_id: int) -> list[models.Tag]:
    """Get all tags assigned to a staff member.

    Args:
        staff_id: The staff member to fetch tags for.

    Returns:
        list[models.Tag]: All tags assigned to the staff member.
    """
    query = """
    SELECT asset_tags.* FROM asset_tags
    JOIN staff_tags ON staff_tags.tag_id = asset_tags.id
    WHERE staff_tags.staff_id = :staff_id
    ORDER BY asset_tags.name;
    """
    db = Database()
    rows: Iterable[aiosqlite.Row] = await db.fetchall(query, {"staff_id": staff_id})
    return [models.Tag.from_row(row) for row in rows]


# Delete
async def delete_tag(tag_id: int) -> None:
    """Delete a tag and remove it from every staff member.

    Args:
        tag_id: The unique ID of the tag to delete.

    Raises:
        ValueError: If no tag with the given ID exists.
    """
    query = "DELETE FROM staff_tags WHERE tag_id = :tag_id;"
    db = Database()
    await db.execute(query, {"tag_id": tag_id})
    cur: aiosqlite.Cursor = await db.execute(query, {"tag_id": tag_id})
    if cur.rowcount == 0:
        raise ValueError(f"No tag found with ID {tag_id}.")


async def untag_staff(staff_id: int, tag_id: int) -> None:
    """Remove a tag from a staff member.

    Args:
        staff_id: The staff member to untag.
        tag_id: The unique ID of the tag to remove.

    Raises:
        ValueError: If the staff member does not have the tag.
    """
    query = "DELETE FROM staff_tags WHERE staff_id = :staff_id AND tag_id = :tag_id;"
    db = Database()
    cur: aiosqlite.Cursor = await db.execute(
        query,
        {"staff_id": staff_id, "tag_id": tag_id},
    )
    if cur.rowcount == 0:
        raise ValueError(f"Staff ID {staff_id} does not have tag ID {tag_id}.")
