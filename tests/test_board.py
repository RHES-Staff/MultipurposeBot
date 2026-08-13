"""Testing Board Aggregation Queries."""

from __future__ import annotations

import database


class TestGetBoardStaff:
    """Tests for database.board.get_board_staff."""

    async def test_default_active_staff(self, db: database.Database) -> None:
        """Staff with no tags/notes should have empty tags, empty notes, active status."""
        staff = await database.board.get_board_staff()
        alice = next(s for s in staff if s["discord_id"] == "111")

        assert alice["status"] == "active"
        assert alice["tags"] == []
        assert alice["notes"] == ""
        assert alice["tasks"] == []

    async def test_tags_and_latest_note(self, db: database.Database) -> None:
        """Should attach tag names and only the most recently added note."""
        alice = await db.fetchone("SELECT staff_id FROM staff_staff WHERE name = 'Alice'")
        tag_cur = await db.execute("INSERT INTO asset_tags (name) VALUES ('vip')")
        await db.execute(
            "INSERT INTO staff_tags (staff_id, tag_id, tagged_by) VALUES (:s, :t, :s)",
            {"s": alice["staff_id"], "t": tag_cur.lastrowid},
        )
        await db.execute("INSERT INTO staff_notes (staff_id, note, noter) VALUES (:s, 'old', :s)", {"s": alice["staff_id"]})
        await db.execute("INSERT INTO staff_notes (staff_id, note, noter) VALUES (:s, 'new', :s)", {"s": alice["staff_id"]})

        staff = await database.board.get_board_staff()
        entry = next(s for s in staff if s["id"] == alice["staff_id"])

        assert entry["tags"] == ["vip"]
        assert entry["notes"] == "new"

    async def test_blacklisted_status(self, db: database.Database) -> None:
        """Blacklisted staff should report status 'blacklisted'."""
        await database.staff.resign_staff(discord_id=111)
        await database.staff.blacklist_staff(discord_id=111)

        staff = await database.board.get_board_staff()
        entry = next(s for s in staff if s["discord_id"] == "111")

        assert entry["status"] == "blacklisted"


class TestGetBoardDepartments:
    """Tests for database.board.get_board_departments."""

    async def test_id_and_sort_order_from_staff_level(self, db: database.Database) -> None:
        """id and sort_order should both equal the department's staff_level, and slug should equal key."""
        await db.execute("UPDATE staff_department SET staff_level = 3 WHERE key = 'dev'")

        departments = await database.board.get_board_departments()
        dev = next(d for d in departments if d["slug"] == "dev")

        assert dev["id"] == 3
        assert dev["sort_order"] == 3


class TestGetBoardMemberships:
    """Tests for database.board.get_board_memberships."""

    async def test_excludes_inactive_memberships(self, db: database.Database) -> None:
        """Resigned department memberships should not appear."""
        alice = await db.fetchone("SELECT staff_id FROM staff_staff WHERE name = 'Alice'")
        await database.department.resign_staff_department(staff_id=alice["staff_id"], department_key="dev")

        memberships = await database.board.get_board_memberships()

        assert not any(m["staff_id"] == alice["staff_id"] for m in memberships)


class TestGetBoardHeads:
    """Tests for database.board.get_board_heads."""

    async def test_one_entry_per_department(self, db: database.Database) -> None:
        """Should return exactly one head entry per department."""
        heads = await database.board.get_board_heads()
        dept_count = (await db.fetchone("SELECT COUNT(*) AS c FROM staff_department"))["c"]

        assert len(heads) == dept_count


class TestGetNextStaffId:
    """Tests for database.board.get_next_staff_id."""

    async def test_returns_max_plus_one(self, db: database.Database) -> None:
        """Should return one greater than the highest staff_id."""
        max_id = (await db.fetchone("SELECT MAX(staff_id) AS m FROM staff_staff"))["m"]

        assert await database.board.get_next_staff_id() == max_id + 1