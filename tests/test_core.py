"""The counting rules themselves, with no disk and no operating system involved."""

from __future__ import annotations

from datetime import datetime

import pytest

from deskhours.core import DayState, hours_from_slots, should_notify, slot_at

TODAY = "2026-08-18"


def test_a_slot_covers_the_minutes_it_spans():
    assert slot_at(datetime(2026, 8, 18, 15, 0), 30) == (15, 0)
    assert slot_at(datetime(2026, 8, 18, 15, 29), 30) == (15, 0)
    assert slot_at(datetime(2026, 8, 18, 15, 30), 30) == (15, 1)


@pytest.mark.parametrize("bad", [0, -30, 7, 45])
def test_a_slot_size_that_does_not_divide_the_hour_is_refused(bad):
    """Slots are addressed as (hour, index), which only holds for a divisor of 60."""
    with pytest.raises(ValueError):
        slot_at(datetime(2026, 8, 18, 15, 0), bad)


def test_repeated_slots_are_counted_once():
    assert hours_from_slots([(9, 0), (9, 0), (9, 1)], 30) == 1.0


def test_no_reminder_below_the_threshold():
    assert should_notify(7.5, notified_hour=0, threshold=8.0) is None


def test_the_first_reminder_arrives_at_the_threshold():
    assert should_notify(8.0, notified_hour=0, threshold=8.0) == 8


def test_the_same_hour_is_never_announced_twice():
    """The watermark is the whole point: polling every 5 minutes must not mean nagging."""
    assert should_notify(8.5, notified_hour=8, threshold=8.0) is None


def test_the_next_whole_hour_is_announced_again():
    assert should_notify(9.0, notified_hour=8, threshold=8.0) == 9


def test_state_from_yesterday_starts_the_day_over():
    """Hours must not leak across midnight; the stored day is what decides."""
    stored = {"date": "2026-08-17", "slots": [[9, 0], [9, 1]], "notified_hour": 8}
    state = DayState.from_dict(stored, today=TODAY)
    assert state.slots == set()
    assert state.notified_hour == 0
    assert state.day == TODAY


def test_state_from_today_is_restored():
    stored = {"date": TODAY, "slots": [[9, 0], [9, 1]], "notified_hour": 8}
    state = DayState.from_dict(stored, today=TODAY)
    assert state.slots == {(9, 0), (9, 1)}
    assert state.notified_hour == 8
    assert state.hours(30) == 1.0


def test_a_damaged_slot_entry_is_skipped_instead_of_crashing():
    """A hand-edited or half-written state file must not take the reminder down with it."""
    stored = {"date": TODAY, "slots": [[9, 0], "nonsense", [9], [10, 1, 2]], "notified_hour": 0}
    assert DayState.from_dict(stored, today=TODAY).slots == {(9, 0)}


def test_a_day_survives_being_written_and_read_back():
    state = DayState(day=TODAY, slots={(9, 0), (14, 1)}, notified_hour=8)
    assert DayState.from_dict(state.to_dict(), today=TODAY) == state


def test_the_clock_hours_are_what_a_person_reads():
    state = DayState(day=TODAY, slots={(14, 1), (9, 0), (9, 1)})
    assert state.active_clock_hours() == [9, 14]
