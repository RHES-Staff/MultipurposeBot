"""Common Tag Operations on Database."""

from __future__ import annotations

from typing import TYPE_CHECKING, Literal, cast, overload

from aiosqlite import Cursor, Row

from . import models, staff
from .core import Database

if TYPE_CHECKING:
    from collections.abc import Iterable


# Create
async def create_tag(name: str, color: str = "#808080") -> models.Tag:
    """Create a tag, or update its color if the name already exists.

    Args:
        name: The display name of the tag.
        color: The hex color code for the tag.

    Returns:
        models.Tag: The created or updated tag.
    """
    db = Database()
    cur: Cursor = await db.execute(
        """
        INSERT INTO asset_tags (name, color) VALUES (:name, :color)
        ON CONFLICT (name) DO UPDATE SET color = :color
        RETURNING *;
        """,
        {"name": name, "color": color},
    )
    row: Row = cast(Row, await cur.fetchone())
    return models.Tag.from_row(row)


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
    existing: Row | None = await db.fetchone(
        "SELECT id FROM staff_tags WHERE staff_id = :staff_id AND tag_id = :tag_id;",
        {"staff_id": staff_id, "tag_id": tag_id},
    )
    if existing is not None:
        raise ValueError(f"Staff ID {staff_id} already has tag ID {tag_id}.")
    await db.execute(
        "INSERT INTO staff_tags (staff_id, tag_id, tagged_by) VALUES (:staff_id, :tag_id, :tagged_by);",
        {"staff_id": staff_id, "tag_id": tag_id, "tagged_by": tagged_by},
    )


async def sync_staff_tags(staff_id: int, tag_names: list[str], tagged_by: int) -> models.StaffMember:
    """Sync tag assignments for a staff member.

    Creates any tag names that don't already exist in the tag catalog.
    Assigns all tag names in the list and removes any assigned tags not in the list.

    Args:
        staff_id: The internal staff ID to update.
        tag_names: The list of tag names to assign.
        tagged_by: The staff ID of the member performing the sync.

    Returns:
        models.StaffMember: The updated staff member object.

    Raises:
        ValueError: If the staff member is not found after syncing.
    """
    create_missing_tags = """
        INSERT OR IGNORE INTO asset_tags (name)
            SELECT je.value FROM json_each(:tag_names) AS je
    """
    insert_new_tags = """
        INSERT INTO staff_tags (staff_id, tag_id, tagged_by)
            SELECT :staff_id, asset_tags.id, :tagged_by
                FROM json_each(:tag_names) AS je
            JOIN asset_tags ON asset_tags.name = je.value
        ON CONFLICT (staff_id, tag_id) DO NOTHING
    """
    remove_old_tags = """
        DELETE FROM staff_tags
        WHERE staff_id = :staff_id
            AND tag_id NOT IN (
                SELECT asset_tags.id
                FROM asset_tags
                JOIN json_each(:tag_names) AS je ON je.value = asset_tags.name
            )
    """
    db = Database()
    await db.execute(create_missing_tags, {"tag_names": str(tag_names)})
    await db.execute(insert_new_tags, {"staff_id": staff_id, "tag_names": str(tag_names), "tagged_by": tagged_by})
    await db.execute(remove_old_tags, {"staff_id": staff_id, "tag_names": str(tag_names)})
    staff_member: models.StaffMember | None = await staff.get_staff(staff_id=staff_id)
    if not staff_member:
        raise ValueError("Something went wrong.")
    return staff_member


# Read
async def get_all_tags() -> list[models.Tag]:
    """Get every tag in the tag catalog.

    Returns:
        list[models.Tag]: All registered tags.
    """
    query = "SELECT * FROM asset_tags ORDER BY name;"
    db = Database()
    rows: Iterable[Row] = await db.fetchall(query)
    return [models.Tag.from_row(row) for row in rows]


@overload
async def get_staff_tags(staff_id: int, *, shallow: Literal[True] = True) -> list[models.TagSummary]: ...
@overload
async def get_staff_tags(staff_id: int, *, shallow: Literal[False] = False) -> list[models.Tag]: ...
async def get_staff_tags(staff_id: int, *, shallow: Literal[True, False] = False):
    """Get all tags assigned to a staff member.

    Args:
        staff_id: The staff member to fetch tags for.
        shallow: If True, return tag summaries. If False, return full tag models.

    Returns:
        list[models.TagSummary] | list[models.Tag]: All tags assigned to the staff member.
    """
    db = Database()
    rows: Iterable[Row] = await db.fetchall(
        """
        SELECT asset_tags.*
        FROM asset_tags
        JOIN staff_tags ON staff_tags.tag_id = asset_tags.id
        WHERE staff_tags.staff_id = :staff_id
        ORDER BY asset_tags.name;
        """,
        {"staff_id": staff_id},
    )
    if shallow:
        return [models.TagSummary.from_row(row) for row in rows]
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
    cur: Cursor = await db.execute(query, {"tag_id": tag_id})
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
    cur: Cursor = await db.execute(
        query,
        {"staff_id": staff_id, "tag_id": tag_id},
    )
    if cur.rowcount == 0:
        raise ValueError(f"Staff ID {staff_id} does not have tag ID {tag_id}.")
