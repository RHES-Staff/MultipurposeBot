"""Common Notes Operations on Database."""

from __future__ import annotations

from typing import TYPE_CHECKING, cast

from aiosqlite import Cursor, Row

from . import models
from .core import Database

if TYPE_CHECKING:
    from collections.abc import Iterable


async def add_note(staff_id: int, note: str, noter: int) -> models.Note:
    """Add a note to a staff member's record.

    Args:
        staff_id: The staff member the note is about.
        note: The text content of the note.
        noter: The staff ID of the author who writes the note.

    Returns:
        models.Note: The new note.
    """
    query = "INSERT INTO staff_notes (staff_id, note, noter) VALUES (:staff_id, :note, :noter) RETURNING *;"
    db = Database()
    result: Row = cast(Row, await db.fetchone(query, {"staff_id": staff_id, "note": note, "noter": noter}))
    return models.Note.from_row(result)


async def get_notes(staff_id: int) -> list[models.Note]:
    """Get all notes recorded for a staff member.

    Args:
        staff_id: The staff member to fetch notes for.

    Returns:
        list[models.Note]: All notes for the staff member, newest first.
    """
    db = Database()
    rows: Iterable[Row] = await db.fetchall(
        "SELECT * FROM staff_notes WHERE staff_id = :staff_id ORDER BY created_at DESC;",
        {"staff_id": staff_id},
    )
    return [models.Note.from_row(row) for row in rows]


async def edit_note(note_id: int, note: str) -> models.Note:
    """Edit the text of an existing note.

    Args:
        note_id: The unique ID of the note to edit.
        note: The new text content for the note.

    Returns:
        models.Note: The updated note.

    Raises:
        ValueError: If no note with the given ID exists.
    """
    db = Database()
    result: Row | None = await db.fetchone("UPDATE staff_notes SET note = :note WHERE id = :id RETURNING *;", {"id": note_id, "note": note})
    if result is None:
        raise ValueError(f"No note found with ID {note_id}.")
    return models.Note.from_row(result)


async def delete_note(note_id: int) -> None:
    """Delete a note from a staff member's record.

    Args:
        note_id: The unique ID of the note to delete.

    Raises:
        ValueError: If no note with the given ID exists.
    """
    db = Database()
    cur: Cursor = await db.execute("DELETE FROM staff_notes WHERE id = :id;", {"id": note_id})
    if cur.rowcount == 0:
        raise ValueError(f"No note found with ID {note_id}.")
