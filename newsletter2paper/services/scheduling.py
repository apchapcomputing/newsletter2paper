"""Delivery-slot arithmetic for scheduled issues. Pure functions, no I/O.

A *slot* is one planned delivery time: `schedule_time_local` (default 09:00) on the issue's
cadence (every day / `schedule_weekday` / `schedule_day_of_month`) in `schedule_timezone`.

Rules this module enforces for the scheduler:
  * the next slot is anchored to the slot just served, never to processing time, so a retry that
    succeeds hours late does not move later deliveries;
  * the period key comes from the slot, so a late retry still belongs to its own period;
  * missed slots are not replayed;
  * a retry may not be scheduled at or after the next slot (`retry_deadline`).
"""
import logging
from datetime import date, datetime, time, timedelta, timezone
from typing import Optional
from zoneinfo import ZoneInfo

logger = logging.getLogger(__name__)

# Frequencies that send once and then turn auto_send off; they have no recurring period.
ONE_SHOT_FREQUENCIES = {'once', 'custom'}
RECURRING_FREQUENCIES = {'daily', 'weekly', 'monthly'}
DEFAULT_TIME_LOCAL = time(9, 0)
# Longest a period can last; used to bound catch-up after downtime.
_PERIOD = {'daily': timedelta(days=1), 'weekly': timedelta(days=7), 'monthly': timedelta(days=31)}
MAX_BACKOFF = timedelta(hours=24)


def resolve_tz(tz_name: Optional[str]) -> ZoneInfo:
    try:
        return ZoneInfo(tz_name or 'UTC')
    except Exception:
        logger.warning(f"Unknown schedule_timezone {tz_name!r}; falling back to UTC")
        return ZoneInfo('UTC')


def parse_time_local(value) -> time:
    """'HH:MM' (or 'HH:MM:SS') to a time; anything unusable falls back to 09:00."""
    if isinstance(value, time):
        return value.replace(tzinfo=None)
    try:
        parts = [int(p) for p in str(value).split(':')]
        return time(parts[0], parts[1])
    except (ValueError, IndexError, TypeError):
        return DEFAULT_TIME_LOCAL


def retry_delay(attempts: int) -> timedelta:
    """Exponential backoff: 1h, 2h, 4h, ... capped at 24h."""
    return min(timedelta(hours=2 ** max(attempts - 1, 0)), MAX_BACKOFF)


def period_key(frequency: str, scheduled_for: datetime, tz_name: Optional[str] = None) -> str:
    """Identifier of the delivery period the slot `scheduled_for` belongs to.

    Computed from the slot, never processing time, so a late retry stays in its period.
    One-shot frequencies key on the slot itself: each enablement is its own edition.
    """
    if frequency in RECURRING_FREQUENCIES:
        local = scheduled_for.astimezone(resolve_tz(tz_name))
        if frequency == 'daily':
            return local.strftime('%Y-%m-%d')
        if frequency == 'weekly':
            iso = local.isocalendar()
            return f"{iso[0]}-W{iso[1]:02d}"
        return local.strftime('%Y-%m')
    return f"once-{scheduled_for.astimezone(timezone.utc).isoformat()}"


def _at(day: date, at: time, tz: ZoneInfo) -> datetime:
    """The UTC instant of `day` at wall-clock `at` in `tz`.

    A time that does not exist (spring-forward gap) lands on the first valid minute after it; an
    ambiguous one (fall-back overlap) uses the first occurrence."""
    return datetime.combine(day, at, tzinfo=tz).astimezone(timezone.utc)


def _clamped(year: int, month: int, day: int) -> date:
    first_next = date(year + (month == 12), month % 12 + 1, 1)
    return date(year, month, min(day, (first_next - timedelta(days=1)).day))


def slot_after(issue: dict, t: datetime, anchor: Optional[datetime] = None) -> Optional[datetime]:
    """The first slot strictly after `t` (UTC-aware), or None for one-shot / unknown frequencies.

    `schedule_weekday` / `schedule_day_of_month` default to those of `anchor` (default `t`) when
    unset, which keeps an issue on the weekday / day it started on.
    """
    frequency = issue.get('frequency', 'weekly')
    if frequency not in RECURRING_FREQUENCIES:
        return None
    tz = resolve_tz(issue.get('schedule_timezone'))
    at = parse_time_local(issue.get('schedule_time_local'))
    local_t = t.astimezone(tz)
    local_anchor = (anchor or t).astimezone(tz)

    if frequency == 'daily':
        day = local_t.date()
        step = lambda d: d + timedelta(days=1)  # noqa: E731
    elif frequency == 'weekly':
        weekday = issue.get('schedule_weekday')
        weekday = local_anchor.weekday() if weekday is None else int(weekday)
        day = local_t.date() + timedelta(days=(weekday - local_t.weekday()) % 7)
        step = lambda d: d + timedelta(days=7)  # noqa: E731
    else:
        dom = issue.get('schedule_day_of_month')
        dom = local_anchor.day if dom is None else int(dom)
        day = _clamped(local_t.year, local_t.month, dom)
        step = lambda d: _clamped(d.year + (d.month == 12), d.month % 12 + 1, dom)  # noqa: E731

    # The candidate for today may already be past; walk forward until strictly after t.
    slot = _at(day, at, tz)
    while slot <= t:
        day = step(day)
        slot = _at(day, at, tz)
    return slot


def first_slot(issue: dict, now: datetime) -> Optional[datetime]:
    """First delivery after enabling (or changing) the schedule."""
    return slot_after(issue, now, anchor=now)


def next_slot_after_delivery(issue: dict, scheduled_for: datetime, now: datetime) -> Optional[datetime]:
    """The slot to release the issue to once the edition for `scheduled_for` is finished, whatever
    the outcome. Anchored to `scheduled_for`, in the future, and never replaying missed slots."""
    frequency = issue.get('frequency', 'weekly')
    if frequency not in RECURRING_FREQUENCIES:
        return None
    base = max(scheduled_for, now - _PERIOD[frequency])
    slot = slot_after(issue, base, anchor=scheduled_for)
    while slot is not None and slot <= now:
        slot = slot_after(issue, slot, anchor=scheduled_for)
    return slot


def retry_deadline(issue: dict, scheduled_for: datetime) -> Optional[datetime]:
    """When the edition for `scheduled_for` stops being worth retrying: the next slot. None for
    one-shot issues, which have no next edition."""
    return slot_after(issue, scheduled_for, anchor=scheduled_for)
