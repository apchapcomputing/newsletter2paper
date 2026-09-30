import os
from datetime import datetime, timezone, timedelta
from unittest.mock import MagicMock

import pytest

os.environ.setdefault('SUPABASE_DATABASE_URL', 'sqlite://')

from services import scheduler as sch
from services.scheduler import SchedulerService, compute_next_run, period_key, retry_delay

UTC = timezone.utc


def dt(*args):
    return datetime(*args, tzinfo=UTC)


class TestComputeNextRun:
    def test_daily_weekly(self):
        now = dt(2026, 10, 1, 9, 30)
        assert compute_next_run('daily', now) == dt(2026, 10, 2, 9, 30)
        assert compute_next_run('weekly', now) == dt(2026, 10, 8, 9, 30)

    def test_monthly_is_calendar_month(self):
        assert compute_next_run('monthly', dt(2026, 1, 15, 8)) == dt(2026, 2, 15, 8)
        assert compute_next_run('monthly', dt(2026, 12, 15, 8)) == dt(2027, 1, 15, 8)

    def test_monthly_clamps_to_month_end(self):
        assert compute_next_run('monthly', dt(2026, 1, 31, 8)) == dt(2026, 2, 28, 8)
        assert compute_next_run('monthly', dt(2028, 1, 31, 8)) == dt(2028, 2, 29, 8)

    def test_non_repeating_returns_none(self):
        assert compute_next_run('once', dt(2026, 1, 1)) is None
        assert compute_next_run('custom', dt(2026, 1, 1)) is None

    def test_timezone_keeps_local_wall_clock_across_dst(self):
        # US DST starts 2026-03-08. 08:00 New York is 13:00 UTC before, 12:00 UTC after.
        now = dt(2026, 3, 7, 13, 0)
        assert compute_next_run('daily', now, 'America/New_York') == dt(2026, 3, 8, 12, 0)

    def test_unknown_timezone_falls_back_to_utc(self):
        assert compute_next_run('daily', dt(2026, 1, 1, 5), 'Not/AZone') == dt(2026, 1, 2, 5)


class TestPeriodKey:
    def test_keys(self):
        now = dt(2026, 10, 1, 9)
        assert period_key('daily', now) == '2026-10-01'
        assert period_key('weekly', now) == '2026-W40'
        assert period_key('monthly', now) == '2026-10'
        assert period_key('custom', now) == 'once'

    def test_uses_local_date(self):
        # 23:30 UTC on Oct 1 is already Oct 2 in Tokyo.
        assert period_key('daily', dt(2026, 10, 1, 23, 30), 'Asia/Tokyo') == '2026-10-02'


def test_retry_delay_backoff_and_cap():
    assert retry_delay(1) == timedelta(hours=1)
    assert retry_delay(2) == timedelta(hours=2)
    assert retry_delay(3) == timedelta(hours=4)
    assert retry_delay(10) == timedelta(hours=24)


@pytest.fixture
def svc(monkeypatch):
    s = SchedulerService.__new__(SchedulerService)
    s.engine = MagicMock()
    s.pdf_service = MagicMock()
    s.batch_size = 5
    s._load = {}
    s.calls = []

    monkeypatch.setattr(s, '_load_issue', lambda issue_id: s._load.get('issue'))
    for name in ('_finalize_success', '_finalize_failure', '_finalize_idle', '_store_pending'):
        monkeypatch.setattr(s, name, lambda *a, _n=name, **k: s.calls.append((_n, a, k)))
    s.generate = MagicMock()
    s.email = MagicMock(return_value=True)

    async def gen(issue):
        return s.generate(issue)
    monkeypatch.setattr(s, '_generate_pdf', gen)
    monkeypatch.setattr(s, '_send_email', lambda issue, to, url: s.email(issue, to, url))
    return s


def issue(**over):
    base = {'id': 'i1', 'frequency': 'weekly', 'schedule_timezone': 'UTC', 'target_email': 'a@b.co',
            'title': 'T', 'run_attempts': 0, 'last_sent_period': None, 'pending_pdf_url': None,
            'pending_period': None}
    base.update(over)
    return base


def names(s):
    return [c[0] for c in s.calls]


class TestProcessIssue:
    async def test_success_generates_emails_and_finalizes(self, svc):
        svc._load['issue'] = issue()
        svc.generate.return_value = {'success': True, 'pdf_url': 'http://pdf'}
        res = await svc._process_issue('i1')
        assert res['success']
        svc.email.assert_called_once()
        assert names(svc) == ['_finalize_success']

    async def test_skips_when_period_already_sent(self, svc):
        period = period_key('weekly', datetime.now(UTC))
        svc._load['issue'] = issue(last_sent_period=period)
        await svc._process_issue('i1')
        svc.generate.assert_not_called()
        svc.email.assert_not_called()
        assert names(svc) == ['_finalize_idle']

    async def test_force_ignores_idempotency(self, svc):
        period = period_key('weekly', datetime.now(UTC))
        svc._load['issue'] = issue(last_sent_period=period)
        svc.generate.return_value = {'success': True, 'pdf_url': 'http://pdf'}
        await svc._process_issue('i1', force=True, previous_status='failed')
        svc.email.assert_called_once()
        name, args, _ = svc.calls[-1]
        assert name == '_finalize_success' and args[-1] == 'failed' and args[-2] is True

    async def test_email_failure_keeps_pdf_and_records_failure(self, svc):
        svc._load['issue'] = issue()
        svc.generate.return_value = {'success': True, 'pdf_url': 'http://pdf'}
        svc.email.return_value = False
        res = await svc._process_issue('i1')
        assert not res['success']
        assert names(svc) == ['_store_pending', '_finalize_failure']
        assert svc.calls[0][1][1] == 'http://pdf'
        assert svc.calls[1][1][1].startswith('email:')

    async def test_retry_resends_email_only_without_regenerating(self, svc):
        period = period_key('weekly', datetime.now(UTC))
        svc._load['issue'] = issue(pending_pdf_url='http://old', pending_period=period, run_attempts=1)
        await svc._process_issue('i1')
        svc.generate.assert_not_called()
        svc.email.assert_called_once()
        assert svc.email.call_args[0][2] == 'http://old'
        assert names(svc) == ['_finalize_success']

    async def test_pending_pdf_from_previous_period_is_regenerated(self, svc):
        svc._load['issue'] = issue(pending_pdf_url='http://old', pending_period='1999-W01')
        svc.generate.return_value = {'success': True, 'pdf_url': 'http://new'}
        await svc._process_issue('i1')
        svc.generate.assert_called_once()
        assert svc.email.call_args[0][2] == 'http://new'

    async def test_pdf_failure_recorded(self, svc):
        svc._load['issue'] = issue()
        svc.generate.return_value = {'success': False, 'error': 'boom'}
        res = await svc._process_issue('i1')
        assert res == {'success': False, 'error': 'boom'}
        svc.email.assert_not_called()
        assert names(svc) == ['_finalize_failure']

    async def test_no_articles_goes_idle(self, svc):
        svc._load['issue'] = issue()
        svc.generate.return_value = None
        await svc._process_issue('i1')
        assert names(svc) == ['_finalize_idle']

    async def test_no_target_email_still_succeeds(self, svc):
        svc._load['issue'] = issue(target_email=None)
        svc.generate.return_value = {'success': True, 'pdf_url': 'http://pdf'}
        await svc._process_issue('i1')
        svc.email.assert_not_called()
        assert names(svc) == ['_finalize_success']

    async def test_missing_issue(self, svc):
        res = await svc._process_issue('nope')
        assert not res['success'] and svc.calls == []


class TestFinalizeFailure:
    """Exercise the real _finalize_failure and inspect the SQL params it writes."""

    def params(self, s):
        conn = s.engine.begin.return_value.__enter__.return_value
        return conn.execute.call_args[0][1]

    def make(self):
        s = SchedulerService.__new__(SchedulerService)
        s.engine = MagicMock()
        return s

    def test_backoff_then_failed(self):
        s = self.make()
        now = dt(2026, 10, 1, 12)
        s._finalize_failure(issue(run_attempts=1), 'email: x', now, False, 'idle')
        p = self.params(s)
        assert p['status'] == 'failed' and p['attempts'] == 2
        assert p['next_at'] == now + timedelta(hours=2) and p['clear'] is False

    def test_gives_up_but_keeps_schedule_alive(self):
        s = self.make()
        now = dt(2026, 10, 1, 12)
        s._finalize_failure(issue(run_attempts=sch.MAX_RUN_ATTEMPTS - 1), 'email: x', now, False, 'idle')
        p = self.params(s)
        assert p['status'] == 'idle' and p['attempts'] == 0 and p['clear'] is True
        assert p['next_at'] == dt(2026, 10, 8, 12)
        assert 'gave up' in p['err']

    def test_force_failure_does_not_touch_schedule(self):
        s = self.make()
        s._finalize_failure(issue(), 'pdf: x', dt(2026, 10, 1), True, 'failed')
        p = self.params(s)
        assert p == {'id': 'i1', 'status': 'failed', 'err': 'pdf: x'}
