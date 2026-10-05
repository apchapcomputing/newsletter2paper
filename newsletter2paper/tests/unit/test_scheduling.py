"""Slot arithmetic: where the next delivery lands, and which period a slot belongs to."""
from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo

import pytest
from hypothesis import given, settings, strategies as st

from services.scheduling import (
    first_slot, next_slot_after_delivery, parse_time_local, period_key, retry_delay, retry_deadline, slot_after,
)

UTC = timezone.utc
NY, LONDON = ZoneInfo('America/New_York'), ZoneInfo('Europe/London')


def utc(*a):
    return datetime(*a, tzinfo=UTC)


def issue(**over):
    base = {'frequency': 'daily', 'schedule_timezone': 'UTC', 'schedule_time_local': '09:00',
            'schedule_weekday': None, 'schedule_day_of_month': None}
    base.update(over)
    return base


class TestSlotAfter:
    def test_daily_is_the_next_local_09_00(self):
        assert slot_after(issue(), utc(2026, 10, 5, 8, 0)) == utc(2026, 10, 5, 9, 0)
        assert slot_after(issue(), utc(2026, 10, 5, 9, 0)) == utc(2026, 10, 6, 9, 0)   # strictly after
        assert slot_after(issue(), utc(2026, 10, 5, 23, 59)) == utc(2026, 10, 6, 9, 0)

    def test_custom_local_time_and_timezone(self):
        i = issue(schedule_time_local='07:30', schedule_timezone='America/New_York')
        assert slot_after(i, utc(2026, 10, 5, 0, 0)) == datetime(2026, 10, 5, 7, 30, tzinfo=NY).astimezone(UTC)

    def test_weekly_lands_on_the_configured_weekday(self):
        i = issue(frequency='weekly', schedule_weekday=4)   # Friday
        assert slot_after(i, utc(2026, 10, 5, 12)) == utc(2026, 10, 9, 9)     # Mon -> that Friday
        assert slot_after(i, utc(2026, 10, 9, 9)) == utc(2026, 10, 16, 9)     # on the slot -> next week

    def test_weekly_without_a_weekday_keeps_the_anchors_weekday(self):
        i = issue(frequency='weekly')
        anchor = utc(2026, 10, 7, 20)   # a Wednesday
        assert slot_after(i, anchor, anchor=anchor).weekday() == 2

    def test_monthly_lands_on_the_day_of_month_and_clamps_short_months(self):
        i = issue(frequency='monthly', schedule_day_of_month=31)
        assert slot_after(i, utc(2026, 1, 15)) == utc(2026, 1, 31, 9)
        assert slot_after(i, utc(2026, 1, 31, 9)) == utc(2026, 2, 28, 9)
        assert slot_after(i, utc(2028, 1, 31, 9)) == utc(2028, 2, 29, 9)      # leap year
        assert slot_after(i, utc(2026, 12, 31, 9)) == utc(2027, 1, 31, 9)     # year rollover

    def test_one_shot_and_unknown_frequencies_have_no_slot(self):
        for freq in ('once', 'custom', 'hourly'):
            assert slot_after(issue(frequency=freq), utc(2026, 1, 1)) is None

    def test_unknown_timezone_and_bad_time_fall_back_to_utc_09_00(self):
        i = issue(schedule_timezone='Not/AZone', schedule_time_local='soon')
        assert slot_after(i, utc(2026, 1, 1)) == utc(2026, 1, 1, 9)

    def test_local_time_is_kept_across_dst(self):
        i = issue(schedule_timezone='America/New_York')
        saturday = slot_after(i, utc(2026, 3, 7, 12))    # 09:00 EST = 14:00Z
        sunday = slot_after(i, saturday)                 # clocks spring forward on Mar 8: 09:00 EDT = 13:00Z
        assert saturday == utc(2026, 3, 7, 14)
        assert sunday == utc(2026, 3, 8, 13)

    @pytest.mark.parametrize('tz', ['America/New_York', 'Europe/London', 'Australia/Lord_Howe'])
    def test_every_slot_around_a_dst_change_is_at_the_local_time(self, tz):
        i = issue(schedule_timezone=tz, schedule_time_local='09:00')
        t = utc(2026, 3, 1)
        for _ in range(60):
            t = slot_after(i, t)
            local = t.astimezone(ZoneInfo(tz))
            assert (local.hour, local.minute) == (9, 0), (tz, t)

    def test_a_time_that_does_not_exist_moves_forward(self):
        # 02:30 does not exist on 2026-03-08 in New York (clocks jump 02:00 -> 03:00).
        i = issue(schedule_timezone='America/New_York', schedule_time_local='02:30')
        slot = slot_after(i, utc(2026, 3, 8, 6, 0)).astimezone(NY)
        assert (slot.month, slot.day) == (3, 8) and slot.hour == 3

    def test_an_ambiguous_time_uses_the_first_occurrence(self):
        # 01:30 happens twice on 2026-11-01 in New York; the first is EDT (UTC-4).
        i = issue(schedule_timezone='America/New_York', schedule_time_local='01:30')
        assert slot_after(i, utc(2026, 11, 1, 0, 0)) == utc(2026, 11, 1, 5, 30)


class TestNextSlotAfterDelivery:
    def test_late_success_does_not_move_the_slot(self):
        # Weekly Friday 09:00 New York; the edition succeeded on a late retry at 16:00 local.
        i = issue(frequency='weekly', schedule_weekday=4, schedule_timezone='America/New_York')
        slot = datetime(2026, 10, 9, 9, 0, tzinfo=NY).astimezone(UTC)
        late = datetime(2026, 10, 9, 16, 0, tzinfo=NY).astimezone(UTC)

        nxt = next_slot_after_delivery(i, slot, late)

        assert nxt == datetime(2026, 10, 16, 9, 0, tzinfo=NY).astimezone(UTC)

    def test_never_returns_a_time_in_the_past(self):
        i = issue(frequency='daily')
        nxt = next_slot_after_delivery(i, utc(2026, 10, 1, 9), utc(2026, 10, 5, 12))
        assert nxt == utc(2026, 10, 6, 9)

    def test_after_downtime_missed_slots_are_not_replayed(self):
        i = issue(frequency='daily')
        # Served the Oct 1 slot on Oct 5 (service was down): next is tomorrow, not Oct 2..4.
        assert next_slot_after_delivery(i, utc(2026, 10, 1, 9), utc(2026, 10, 5, 9, 5)) == utc(2026, 10, 6, 9)

    def test_one_shot_has_no_next_slot(self):
        assert next_slot_after_delivery(issue(frequency='once'), utc(2026, 1, 1), utc(2026, 1, 2)) is None

    def test_monthly_keeps_its_day(self):
        i = issue(frequency='monthly', schedule_day_of_month=15)
        assert next_slot_after_delivery(i, utc(2026, 10, 15, 9), utc(2026, 10, 15, 20)) == utc(2026, 11, 15, 9)


class TestRetryDeadline:
    def test_is_the_next_slot(self):
        assert retry_deadline(issue(), utc(2026, 10, 5, 9)) == utc(2026, 10, 6, 9)

    def test_none_for_one_shot(self):
        assert retry_deadline(issue(frequency='custom'), utc(2026, 10, 5, 9)) is None


class TestFirstSlot:
    def test_enabling_waits_for_the_next_slot(self):
        assert first_slot(issue(), utc(2026, 10, 5, 10)) == utc(2026, 10, 6, 9)


class TestPeriodKey:
    def test_keys_by_frequency(self):
        t = utc(2026, 10, 1, 9)
        assert period_key('daily', t) == '2026-10-01'
        assert period_key('weekly', t) == '2026-W40'
        assert period_key('monthly', t) == '2026-10'

    def test_uses_the_local_date_of_the_slot(self):
        assert period_key('daily', utc(2026, 10, 1, 23, 30), 'Asia/Tokyo') == '2026-10-02'

    def test_one_shot_keys_on_the_slot_itself(self):
        a, b = period_key('once', utc(2026, 1, 1)), period_key('once', utc(2026, 1, 2))
        assert a != b and a.startswith('once-')


def test_retry_delay_backoff_and_cap():
    assert [retry_delay(n) for n in (1, 2, 3, 4)] == [timedelta(hours=h) for h in (1, 2, 4, 8)]
    assert retry_delay(10) == timedelta(hours=24)


def test_parse_time_local():
    assert (parse_time_local('07:45').hour, parse_time_local('07:45').minute) == (7, 45)
    assert parse_time_local('07:45:00').hour == 7
    assert parse_time_local(None).hour == 9 and parse_time_local('25:99').hour == 9


instants = st.datetimes(min_value=datetime(2024, 1, 1), max_value=datetime(2030, 12, 31), timezones=st.just(UTC))
zones = st.sampled_from(['UTC', 'America/New_York', 'Europe/London', 'Australia/Lord_Howe', 'Asia/Kolkata'])
# Explicit weekday / day-of-month: with them unset the slot depends on the anchor, which callers pin.
issues = st.builds(
    lambda f, tz, h, m, wd, dom: issue(frequency=f, schedule_timezone=tz, schedule_time_local=f"{h:02d}:{m:02d}",
                                       schedule_weekday=wd, schedule_day_of_month=dom),
    st.sampled_from(['daily', 'weekly', 'monthly']), zones, st.integers(0, 23), st.sampled_from([0, 15, 30, 45]),
    st.integers(0, 6), st.integers(1, 31),
)


class TestProperties:
    @settings(max_examples=300, deadline=None)
    @given(issues, instants)
    def test_slot_is_strictly_after_t_and_is_the_very_first_one(self, i, t):
        slot = slot_after(i, t)
        assert slot > t
        assert slot - t <= timedelta(days=32)
        # Nothing earlier qualifies: asking from just before the slot returns the same slot.
        assert slot_after(i, slot - timedelta(seconds=1)) == slot

    @settings(max_examples=300, deadline=None)
    @given(issues, instants)
    def test_walking_slots_is_strictly_increasing(self, i, t):
        first = slot_after(i, t)
        assert slot_after(i, first) > first

    @settings(max_examples=300, deadline=None)
    @given(issues, instants)
    def test_slots_fall_on_the_configured_local_time_unless_it_does_not_exist(self, i, t):
        slot = slot_after(i, t).astimezone(ZoneInfo(i['schedule_timezone']))
        hh, mm = (int(x) for x in i['schedule_time_local'].split(':'))
        # A wall-clock time inside a DST gap is shifted forward; otherwise it is exact.
        assert (slot.hour, slot.minute) == (hh, mm) or slot.hour == hh + 1

    @settings(max_examples=200, deadline=None)
    @given(issues, instants, st.integers(0, 40))
    def test_next_slot_after_delivery_is_future_and_ignores_how_late_the_run_was(self, i, scheduled_for, late_hours):
        now = scheduled_for + timedelta(hours=late_hours)
        nxt = next_slot_after_delivery(i, scheduled_for, now)
        assert nxt > now
        deadline = retry_deadline(i, scheduled_for)
        if now < deadline:
            # Finishing the same edition any time before the next slot yields that next slot.
            assert nxt == deadline
