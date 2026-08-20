"""Testing Leaderboard View and its outputs."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest
import pytest_mock

from features.development import Development


@pytest.fixture
def dev_cog(mocker: pytest_mock.MockerFixture) -> Development:
    """Set up a mock of the Development Cog as required by the tests."""
    mock_bot = mocker.MagicMock()
    cog = Development(mock_bot)
    return cog


containment_dates: list[tuple[datetime, int]] = [
    (datetime(2026, 8, 1, 0, 0, tzinfo=timezone.utc), 0),
    (datetime(2026, 8, 1, 0, 0, tzinfo=timezone(timedelta(hours=-4))), 0),
    (datetime(2026, 8, 1, 12, 30, tzinfo=timezone.utc), 3),
    (datetime(2026, 8, 1, 23, 59, 59, tzinfo=timezone.utc), 6),
    (datetime(2026, 1, 1, 0, 0, tzinfo=timezone.utc), 0),  # year rollover
    (datetime(2025, 12, 31, 23, 59, 59, tzinfo=timezone.utc), 0),
    (datetime(2028, 2, 29, 12, 0, tzinfo=timezone.utc), 0),  # leap day
    *[(datetime(2026, 8, 1, 12, 0, tzinfo=timezone.utc), sow) for sow in range(7)],
]


@pytest.mark.parametrize("date, start_of_week", containment_dates)
def test_bugreport_leaderboard_containment(dev_cog: Development, date: datetime, start_of_week: int) -> None:
    """Test if a given date falls between the correct start/end dates."""
    dev_cog.start_of_week = start_of_week
    start, end = dev_cog.week_bounds(date, start_of_week)
    assert start.astimezone(timezone.utc) <= date.astimezone(timezone.utc)
    assert date.astimezone(timezone.utc) <= end.astimezone(timezone.utc)


boundary_cases: list[tuple[datetime, int, datetime, datetime]] = [
    # Sat Aug 1 2026, week starts Sunday -> week is Jul 26 - Aug 1
    (
        datetime(2026, 8, 1, 12, 0, tzinfo=timezone.utc),
        0,
        datetime(2026, 7, 26, 0, 0, tzinfo=timezone.utc),
        datetime(2026, 8, 1, 23, 59, 59, tzinfo=timezone.utc),
    ),
    # Sat Aug 1 2026, week starts Monday -> week is Jul 27 - Aug 2
    (
        datetime(2026, 8, 1, 12, 0, tzinfo=timezone.utc),
        1,
        datetime(2026, 7, 27, 0, 0, tzinfo=timezone.utc),
        datetime(2026, 8, 2, 23, 59, 59, tzinfo=timezone.utc),
    ),
    # date IS start_of_week day (Sunday, sow=0) -> start == date's midnight
    (
        datetime(2026, 8, 2, 15, 0, tzinfo=timezone.utc),
        0,
        datetime(2026, 8, 2, 0, 0, tzinfo=timezone.utc),
        datetime(2026, 8, 8, 23, 59, 59, tzinfo=timezone.utc),
    ),
    # date IS last day of week (Saturday, sow=0) -> end == date's day
    (
        datetime(2026, 8, 1, 0, 0, 1, tzinfo=timezone.utc),
        0,
        datetime(2026, 7, 26, 0, 0, tzinfo=timezone.utc),
        datetime(2026, 8, 1, 23, 59, 59, tzinfo=timezone.utc),
    ),
    # month rollover: Sat Aug 1 with sow=6 (week starts Saturday)
    (
        datetime(2026, 8, 1, 6, 0, tzinfo=timezone.utc),
        6,
        datetime(2026, 8, 1, 0, 0, tzinfo=timezone.utc),
        datetime(2026, 8, 7, 23, 59, 59, tzinfo=timezone.utc),
    ),
    # non-UTC offset should not shift the calendar day
    (
        datetime(2026, 8, 1, 0, 0, tzinfo=timezone(timedelta(hours=-4))),
        0,
        datetime(2026, 7, 26, 0, 0, tzinfo=timezone(timedelta(hours=-4))),
        datetime(2026, 8, 1, 23, 59, 59, tzinfo=timezone(timedelta(hours=-4))),
    ),
    # year rollover: Jan 1 2026 (Thursday), sow=0
    (
        datetime(2026, 1, 1, 0, 0, tzinfo=timezone.utc),
        0,
        datetime(2025, 12, 28, 0, 0, tzinfo=timezone.utc),
        datetime(2026, 1, 3, 23, 59, 59, tzinfo=timezone.utc),
    ),
    # leap day: Feb 29 2028 (Tuesday), sow=0
    (
        datetime(2028, 2, 29, 12, 0, tzinfo=timezone.utc),
        0,
        datetime(2028, 2, 27, 0, 0, tzinfo=timezone.utc),
        datetime(2028, 3, 4, 23, 59, 59, tzinfo=timezone.utc),
    ),
    # testing a bug
    (
        datetime(2026, 8, 7, 20, 6, tzinfo=timezone.utc),
        0,
        datetime(2026, 8, 2, 0, 0, tzinfo=timezone.utc),
        datetime(2026, 8, 8, 23, 59, 59, tzinfo=timezone.utc),
    ),
]


@pytest.mark.parametrize("date, start_of_week, expected_start, expected_end", boundary_cases)
def test_bugreport_leaderboard_exact_bounds(
    dev_cog: Development,
    date: datetime,
    start_of_week: int,
    expected_start: datetime,
    expected_end: datetime,
) -> None:
    """Test the expected start/end dates of a week."""
    dev_cog.start_of_week = start_of_week
    start, end = dev_cog.week_bounds(date, start_of_week)
    assert start == expected_start
    assert end == expected_end
