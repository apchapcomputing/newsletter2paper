"""Date-window parsing shared by the articles and pdf routers.

These decide *which articles end up in a printed issue*, so the edge cases matter:
naive dates must be read as UTC, and a saved custom range must only apply to
`custom` issues and only when the caller gave no explicit range.
"""
from datetime import datetime, timezone

import pytest
from fastapi import HTTPException

from routers.articles import _parse_date_param as articles_parse
from routers.pdf import _parse_date_param as pdf_parse, _resolve_date_window


@pytest.mark.parametrize("parse", [articles_parse, pdf_parse])
class TestParseDateParam:
    def test_none_stays_none(self, parse):
        assert parse(None, "start_date") is None

    def test_date_only_is_midnight_utc(self, parse):
        assert parse("2026-03-01", "start_date") == datetime(2026, 3, 1, tzinfo=timezone.utc)

    def test_explicit_offset_is_preserved(self, parse):
        parsed = parse("2026-03-01T10:00:00+02:00", "start_date")
        assert parsed.utcoffset().total_seconds() == 7200
        assert parsed == datetime(2026, 3, 1, 8, 0, tzinfo=timezone.utc)

    def test_garbage_is_a_422_that_names_the_parameter(self, parse):
        with pytest.raises(HTTPException) as exc:
            parse("last tuesday", "end_date")
        assert exc.value.status_code == 422
        assert "end_date" in exc.value.detail


class TestResolveDateWindow:
    def test_explicit_params_win_over_saved_custom_dates(self):
        issue = {"frequency": "custom", "custom_start_date": "2026-01-01", "custom_end_date": "2026-01-31"}
        start, end = _resolve_date_window("2026-03-01", "2026-03-07", issue, days_back=7)
        assert (start.date().isoformat(), end.date().isoformat()) == ("2026-03-01", "2026-03-07")

    def test_custom_issue_falls_back_to_its_saved_range(self):
        issue = {"frequency": "custom", "custom_start_date": "2026-01-01", "custom_end_date": "2026-01-31"}
        start, end = _resolve_date_window(None, None, issue, days_back=7)
        assert (start.date().isoformat(), end.date().isoformat()) == ("2026-01-01", "2026-01-31")

    def test_saved_dates_are_ignored_for_recurring_issues(self):
        # A weekly issue may still carry stale custom dates; they must not narrow the window.
        issue = {"frequency": "weekly", "custom_start_date": "2026-01-01", "custom_end_date": "2026-01-31"}
        assert _resolve_date_window(None, None, issue, days_back=7) == (None, None)

    def test_no_dates_means_caller_uses_days_back(self):
        assert _resolve_date_window(None, None, {"frequency": "custom"}, days_back=7) == (None, None)

    def test_start_after_end_is_rejected(self):
        with pytest.raises(HTTPException) as exc:
            _resolve_date_window("2026-03-07", "2026-03-01", {}, days_back=7)
        assert exc.value.status_code == 422

    def test_a_single_bound_is_allowed(self):
        start, end = _resolve_date_window("2026-03-01", None, {}, days_back=7)
        assert start is not None and end is None
