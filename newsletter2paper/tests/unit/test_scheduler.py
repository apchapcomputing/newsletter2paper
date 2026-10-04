import os
from datetime import datetime, timezone, timedelta
from unittest.mock import MagicMock

import pytest

os.environ.setdefault('SUPABASE_DATABASE_URL', 'sqlite://')

from services import scheduler as sch
from services.delivery_store import Claim, ClaimLost, DeliveryStore
from services.email_service import SendResult
from services.scheduler import (
    LOCK_TIMEOUT_MINUTES, SEND_NOW_COOLDOWN_MINUTES, SchedulerService, SendNowCooldown,
    check_lock_timeout, compute_next_run, period_key, retry_delay,
)

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
        assert period_key('custom', now) == 'once-2026-10-01T09:00:00+00:00'

    def test_one_shot_keys_differ_per_slot(self):
        # Re-enabling a one-shot issue gives it a new slot, so the unique period index can't block it.
        assert period_key('once', dt(2026, 10, 1, 9)) != period_key('once', dt(2026, 10, 2, 9))

    def test_key_comes_from_the_slot_not_processing_time(self):
        # A daily slot at 23:00 retried after midnight still belongs to its own day.
        assert period_key('daily', dt(2026, 10, 5, 23)) == '2026-10-05'

    def test_uses_local_date(self):
        # 23:30 UTC on Oct 1 is already Oct 2 in Tokyo.
        assert period_key('daily', dt(2026, 10, 1, 23, 30), 'Asia/Tokyo') == '2026-10-02'


def test_retry_delay_backoff_and_cap():
    assert retry_delay(1) == timedelta(hours=1)
    assert retry_delay(2) == timedelta(hours=2)
    assert retry_delay(3) == timedelta(hours=4)
    assert retry_delay(10) == timedelta(hours=24)


def test_lock_timeout_must_exceed_worst_case_run():
    check_lock_timeout(15, 120)  # 900s > 300 + 120 + 60
    with pytest.raises(RuntimeError, match='SCHEDULER_LOCK_TIMEOUT_MINUTES'):
        check_lock_timeout(8, 120)  # 480s == worst case


CLAIM = Claim('i1', 'tok-1')
TRANSIENT_FAILURE = SendResult.failed('transient', 'email: Resend is unavailable (503: down)')
PERMANENT_FAILURE = SendResult.failed('permanent', 'email: Resend rejected the message (422: Invalid `to` field.)')
SLOT = '2026-10-02T09:00:00+00:00'


def delivery(**over):
    base = {'id': 'd1', 'status': 'pending', 'attempts': 0, 'pdf_url': None, 'trigger': 'scheduled'}
    base.update(over)
    return base


def issue(**over):
    base = {'id': 'i1', 'frequency': 'weekly', 'schedule_timezone': 'UTC', 'target_email': 'a@b.co',
            'title': 'T', 'next_run_at': SLOT}
    base.update(over)
    return base


class FakeStore:
    """In-memory DeliveryStore that records every call in order; `lose_claim_at` names the call
    that raises ClaimLost, as if another worker had taken over."""

    def __init__(self, existing=None, lose_claim_at=None):
        self.existing, self.lose_claim_at = existing, lose_claim_at
        self.log, self.finished = [], []

    def _call(self, name, *args):
        if self.lose_claim_at == name:
            raise ClaimLost('i1')
        self.log.append((name, *args))

    def open_scheduled_delivery(self, claim, scheduled_for, key):
        self._call('open', scheduled_for, key)
        return self.existing or delivery(period_key=key)

    def create_manual_delivery(self, claim):
        self._call('manual')
        return delivery(id='m1', trigger='manual')

    def mark_sending(self, claim, delivery_id, pdf_url, recipient):
        self._call('mark_sending', delivery_id, pdf_url, recipient)

    def finish(self, claim, issue_fields, delivery_id=None, delivery_fields=None, cadence=None):
        self._call('finish')
        self.finished.append((issue_fields, delivery_id, delivery_fields))
        self.cadence = cadence


@pytest.fixture
def svc(monkeypatch):
    s = SchedulerService.__new__(SchedulerService)
    s.store = FakeStore()
    s.batch_size = 5
    s._issue = issue()
    s.generate = MagicMock(return_value={'success': True, 'pdf_url': 'http://pdf'})
    s.email = MagicMock(return_value=SendResult.sent('msg-1'))

    async def gen(_issue):
        return s.generate(_issue)

    def send(_issue, to, url, key):
        s.store.log.append(('email', to, url, key))
        return s.email(_issue, to, url, key)

    monkeypatch.setattr(s, '_load_issue', lambda issue_id: s._issue)
    monkeypatch.setattr(s, '_generate_pdf', gen)
    monkeypatch.setattr(s, '_send_email', send)
    return s


def steps(s):
    return [entry[0] for entry in s.store.log]


class TestScheduledRun:
    async def test_success_commits_sending_before_email_then_records_sent(self, svc):
        res = await svc._process_issue(CLAIM)
        assert res == {'success': True, 'error': None}
        assert steps(svc) == ['open', 'mark_sending', 'email', 'finish']
        assert svc.store.log[2] == ('email', 'a@b.co', 'http://pdf', 'delivery-d1-0')
        issue_fields, delivery_id, d = svc.store.finished[0]
        assert delivery_id == 'd1'
        assert d['status'] == 'sent' and d['resend_message_id'] == 'msg-1' and d['pdf_url'] == 'http://pdf'
        assert issue_fields['schedule_status'] == 'idle' and issue_fields['last_run_error'] is None
        assert issue_fields['next_run_at'] is not None and 'auto_send' not in issue_fields

    async def test_delivery_keyed_on_the_slot_being_served(self, svc):
        svc._issue = issue(frequency='daily', next_run_at='2026-10-05T23:00:00+00:00')
        await svc._process_issue(CLAIM)
        _, scheduled_for, key = svc.store.log[0]
        assert scheduled_for == dt(2026, 10, 5, 23) and key == '2026-10-05'

    @pytest.mark.parametrize('status', ['sent', 'skipped', 'abandoned'])
    async def test_period_already_handled_sends_nothing_and_advances(self, svc, status):
        svc.store.existing = delivery(status=status)
        res = await svc._process_issue(CLAIM)
        assert res['success']
        svc.generate.assert_not_called()
        assert steps(svc) == ['open', 'finish']
        issue_fields, delivery_id, _ = svc.store.finished[0]
        assert delivery_id is None and issue_fields['schedule_status'] == 'idle'

    async def test_crash_after_sending_resends_with_the_same_key(self, svc):
        # The previous run committed 'sending' and died; Resend may already have the email.
        svc.store.existing = delivery(status='sending', pdf_url='http://old', attempts=1)
        await svc._process_issue(CLAIM)
        svc.generate.assert_not_called()
        assert svc.store.log[2] == ('email', 'a@b.co', 'http://old', 'delivery-d1-1')
        assert svc.store.finished[0][2]['status'] == 'sent'

    async def test_email_failure_schedules_retry_and_keeps_pdf(self, svc):
        svc.email.return_value = TRANSIENT_FAILURE
        res = await svc._process_issue(CLAIM)
        assert not res['success']
        assert ('mark_sending', 'd1', 'http://pdf', 'a@b.co') in svc.store.log  # PDF stored for the retry
        issue_fields, _, d = svc.store.finished[0]
        assert d['status'] == 'failed' and d['attempts'] == 1 and d['error'].startswith('email:')
        assert issue_fields['schedule_status'] == 'failed'
        assert issue_fields['next_run_at'] == d['next_attempt_at']

    async def test_retry_reuses_pdf_with_a_new_key(self, svc):
        svc.store.existing = delivery(status='failed', pdf_url='http://old', attempts=1)
        await svc._process_issue(CLAIM)
        svc.generate.assert_not_called()
        assert svc.store.log[2][3] == 'delivery-d1-1'

    async def test_gives_up_after_max_attempts_but_keeps_schedule(self, svc):
        svc.store.existing = delivery(status='failed', pdf_url='http://old', attempts=sch.MAX_RUN_ATTEMPTS - 1)
        svc.email.return_value = TRANSIENT_FAILURE
        await svc._process_issue(CLAIM)
        issue_fields, _, d = svc.store.finished[0]
        assert d['status'] == 'abandoned' and 'gave up' in d['error']
        assert issue_fields['schedule_status'] == 'idle' and issue_fields['next_run_at'] is not None
        assert 'auto_send' not in issue_fields

    async def test_pdf_failure_counts_an_attempt_without_emailing(self, svc):
        svc.generate.return_value = {'success': False, 'error': 'boom'}
        res = await svc._process_issue(CLAIM)
        assert res == {'success': False, 'error': 'boom'}
        assert steps(svc) == ['open', 'finish']
        assert svc.store.finished[0][2]['attempts'] == 1

    async def test_no_articles_marks_skipped(self, svc):
        svc.generate.return_value = None
        await svc._process_issue(CLAIM)
        assert steps(svc) == ['open', 'finish']
        assert svc.store.finished[0][2] == {'status': 'skipped'}

    @pytest.mark.parametrize('email', [None, '', '   '])
    async def test_no_recipient_is_a_permanent_config_failure_before_rendering(self, svc, email):
        svc._issue = issue(target_email=email)
        res = await svc._process_issue(CLAIM)
        assert res == {'success': False, 'error': 'config: no recipient email address is set'}
        svc.generate.assert_not_called()
        assert steps(svc) == ['open', 'finish']
        issue_fields, _, d = svc.store.finished[0]
        assert d['status'] == 'abandoned' and d['error_kind'] == 'permanent'
        assert issue_fields['last_run_error'] == 'config: no recipient email address is set'
        assert issue_fields['schedule_status'] == 'idle' and issue_fields['next_run_at'] is not None

    async def test_permanent_send_failure_abandons_without_retrying(self, svc):
        svc.email.return_value = PERMANENT_FAILURE
        res = await svc._process_issue(CLAIM)
        assert res['error'] == PERMANENT_FAILURE.error
        issue_fields, _, d = svc.store.finished[0]
        assert d == {'status': 'abandoned', 'attempts': 1, 'error': PERMANENT_FAILURE.error,
                     'error_kind': 'permanent', 'next_attempt_at': None}
        assert issue_fields['schedule_status'] == 'idle' and issue_fields['last_run_error'] == PERMANENT_FAILURE.error
        assert 'gave up' not in issue_fields['last_run_error']

    async def test_transient_failure_records_cause_and_kind(self, svc):
        svc.email.return_value = TRANSIENT_FAILURE
        await svc._process_issue(CLAIM)
        issue_fields, _, d = svc.store.finished[0]
        assert d['status'] == 'failed' and d['error_kind'] == 'transient' and d['error'] == TRANSIENT_FAILURE.error
        assert issue_fields['last_run_error'] == TRANSIENT_FAILURE.error

    async def test_retry_waits_at_least_retry_after(self, svc):
        svc.email.return_value = SendResult.failed('transient', 'email: Resend rate limit reached (x)', retry_after=7200)
        before = datetime.now(timezone.utc)
        await svc._process_issue(CLAIM)
        retry_at = svc.store.finished[0][2]['next_attempt_at']
        assert retry_at >= before + timedelta(seconds=7200)  # longer than the 1h first backoff

    async def test_short_retry_after_keeps_the_normal_backoff(self, svc):
        svc.email.return_value = SendResult.failed('transient', 'email: Resend rate limit reached (x)', retry_after=120)
        before = datetime.now(timezone.utc)
        await svc._process_issue(CLAIM)
        assert svc.store.finished[0][2]['next_attempt_at'] >= before + timedelta(hours=1)

    async def test_permanent_failure_on_one_shot_turns_it_off(self, svc):
        svc._issue = issue(frequency='once')
        svc.email.return_value = PERMANENT_FAILURE
        await svc._process_issue(CLAIM)
        issue_fields = svc.store.finished[0][0]
        assert issue_fields['auto_send'] is False and issue_fields['next_run_at'] is None

    async def test_success_clears_error_kind(self, svc):
        await svc._process_issue(CLAIM)
        d = svc.store.finished[0][2]
        assert d['error_kind'] is None and d['resend_message_id'] == 'msg-1'

    async def test_unexpected_error_after_sending_keeps_the_key(self, svc):
        svc.email.side_effect = RuntimeError('socket closed')
        res = await svc._process_issue(CLAIM)
        assert not res['success']
        _, _, d = svc.store.finished[0]
        assert d['status'] == 'failed' and d['attempts'] == 0  # next run reuses delivery-d1-0

    async def test_one_shot_success_turns_auto_send_off(self, svc):
        svc._issue = issue(frequency='once')
        await svc._process_issue(CLAIM)
        issue_fields = svc.store.finished[0][0]
        assert issue_fields['auto_send'] is False and issue_fields['next_run_at'] is None

    async def test_final_write_carries_the_cadence_it_was_computed_from(self, svc):
        svc._issue = issue(auto_send=True, schedule_weekday=4)
        await svc._process_issue(CLAIM)
        assert svc.store.cadence == {'auto_send': True, 'frequency': 'weekly', 'schedule_timezone': 'UTC',
                                     'schedule_weekday': 4}

    async def test_missing_issue(self, svc):
        svc._issue = None
        res = await svc._process_issue(CLAIM)
        assert not res['success'] and svc.store.log == []


class TestFencing:
    async def test_taken_over_before_sending_sends_no_email(self, svc):
        svc.store.lose_claim_at = 'mark_sending'
        res = await svc._process_issue(CLAIM)
        assert res == {'success': False, 'error': 'claim lost'}
        svc.email.assert_not_called()
        assert svc.store.finished == []

    async def test_taken_over_before_finishing_writes_nothing(self, svc):
        svc.store.lose_claim_at = 'finish'
        res = await svc._process_issue(CLAIM)
        assert res['error'] == 'claim lost' and svc.store.finished == []

    async def test_taken_over_before_opening_does_nothing(self, svc):
        svc.store.lose_claim_at = 'open'
        res = await svc._process_issue(CLAIM)
        assert res['error'] == 'claim lost'
        svc.generate.assert_not_called()


class TestManualSend:
    async def test_uses_a_manual_delivery_and_leaves_cadence_alone(self, svc):
        claim = Claim('i1', 'tok', previous_status='failed')
        await svc.send_now(claim)
        assert steps(svc) == ['manual', 'mark_sending', 'email', 'finish']
        assert svc.store.log[2][3] == 'delivery-m1-0'
        issue_fields, delivery_id, d = svc.store.finished[0]
        assert delivery_id == 'm1' and d['status'] == 'sent'
        assert issue_fields['schedule_status'] == 'failed' and 'next_run_at' not in issue_fields

    async def test_failure_is_not_retried(self, svc):
        svc.email.return_value = TRANSIENT_FAILURE
        await svc.send_now(Claim('i1', 'tok', previous_status='idle'))
        issue_fields, _, d = svc.store.finished[0]
        assert d['status'] == 'failed' and 'next_attempt_at' not in d
        assert issue_fields == {'schedule_status': 'idle', 'last_run_error': TRANSIENT_FAILURE.error}
        assert d['error_kind'] == 'transient'


class TestPolling:
    def test_claims_one_issue_at_a_time_until_none_are_due(self, monkeypatch):
        s = SchedulerService.__new__(SchedulerService)
        s.batch_size = 5
        s.store = MagicMock()
        s.store.initialize_unscheduled.return_value = []
        s.store.claim_next_due.side_effect = [Claim('a', 't1'), Claim('b', 't2'), None]
        processed = []

        async def process(claim, force=False):
            processed.append(claim.issue_id)
        monkeypatch.setattr(s, '_process_issue', process)

        s._job_check_and_process()
        assert processed == ['a', 'b'] and s.store.claim_next_due.call_count == 3

    def test_unexpected_error_releases_the_claim(self, monkeypatch):
        s = SchedulerService.__new__(SchedulerService)
        s.batch_size = 1
        s.store = MagicMock()
        s.store.initialize_unscheduled.return_value = []
        s.store.claim_next_due.return_value = Claim('a', 't1')

        async def process(claim, force=False):
            raise RuntimeError('db down')
        monkeypatch.setattr(s, '_process_issue', process)

        s._job_check_and_process()
        claim, fields = s.store.finish.call_args[0]
        assert claim.token == 't1' and fields['schedule_status'] == 'failed' and 'db down' in fields['last_run_error']


def store_with(row=None, rowcount=1):
    engine = MagicMock()
    conn = engine.begin.return_value.__enter__.return_value
    conn.execute.return_value.fetchone.return_value = row
    conn.execute.return_value.rowcount = rowcount
    return DeliveryStore(engine), conn


class TestClaimForSendNow:
    NOW = datetime(2026, 3, 4, 12, 0, tzinfo=timezone.utc)

    def claim(self, prev, locked_minutes_ago=None):
        locked_at = None if locked_minutes_ago is None else self.NOW - timedelta(minutes=locked_minutes_ago)
        store, conn = store_with(None if prev is None else (prev, locked_at, self.NOW))
        return store, conn

    def call(self, store):
        return store.claim_for_send_now('i1', LOCK_TIMEOUT_MINUTES, SEND_NOW_COOLDOWN_MINUTES)

    @pytest.mark.parametrize('prev', ['idle', 'failed'])
    def test_returns_previous_status_and_a_fresh_token(self, prev):
        store, conn = self.claim(prev)
        claim = self.call(store)
        assert claim.previous_status == prev and claim.token
        assert conn.execute.call_args[0][1]['token'] == claim.token

    def test_reclaimed_stale_lock_restores_idle(self):
        # Restoring 'processing' would leave the row stuck after the manual send.
        store, _ = self.claim('processing', locked_minutes_ago=LOCK_TIMEOUT_MINUTES + 1)
        assert self.call(store).previous_status == 'idle'

    def test_already_processing_returns_none(self):
        store, conn = self.claim('processing', locked_minutes_ago=1)
        assert self.call(store) is None
        assert conn.execute.call_count == 1  # no UPDATE

    def test_missing_issue_returns_none(self):
        assert self.call(self.claim(None)[0]) is None

    def test_recent_claim_raises_cooldown(self):
        store, conn = self.claim('idle', locked_minutes_ago=SEND_NOW_COOLDOWN_MINUTES - 2)
        with pytest.raises(SendNowCooldown) as exc:
            self.call(store)
        assert 0 < exc.value.retry_after <= 2 * 60 + 1
        assert conn.execute.call_count == 1  # no UPDATE

    def test_claim_after_cooldown_succeeds(self):
        store, _ = self.claim('idle', locked_minutes_ago=SEND_NOW_COOLDOWN_MINUTES + 1)
        assert self.call(store).previous_status == 'idle'


class TestStoreFinish:
    def test_writes_issue_then_delivery_fenced_on_the_token(self):
        store, conn = store_with()
        store.finish(CLAIM, {'schedule_status': 'idle'}, 'd1', {'status': 'sent'})
        (issue_sql, issue_params), (delivery_sql, delivery_params) = [c[0] for c in conn.execute.call_args_list]
        assert 'claim_token' in str(issue_sql) and issue_params['_token'] == 'tok-1'
        assert 'issue_deliveries' in str(delivery_sql) and delivery_params == {'status': 'sent', '_id': 'd1'}

    def test_lost_claim_raises_and_skips_the_delivery(self):
        store, conn = store_with(rowcount=0)
        with pytest.raises(ClaimLost):
            store.finish(CLAIM, {'schedule_status': 'idle'}, 'd1', {'status': 'sent'})
        assert conn.execute.call_count == 1

    def test_cadence_guard_wraps_schedule_fields(self):
        store, conn = store_with()
        store.finish(CLAIM, {'schedule_status': 'failed', 'next_run_at': None, 'last_run_error': 'x'},
                     cadence={'frequency': 'weekly', 'schedule_weekday': 4})
        sql, params = conn.execute.call_args[0]
        sql = str(sql)
        assert "next_run_at = CASE WHEN frequency::text IS NOT DISTINCT FROM" in sql
        assert "schedule_status = CASE WHEN" in sql and "ELSE 'idle' END" in sql
        assert "last_run_error = :last_run_error" in sql  # unguarded fields stay plain
        assert params['_c_frequency'] == 'weekly' and params['_c_schedule_weekday'] == 4

    def test_without_cadence_fields_are_plain(self):
        store, conn = store_with()
        store.finish(CLAIM, {'schedule_status': 'idle'})
        assert 'CASE' not in str(conn.execute.call_args[0][0])

    def test_failed_outcome_does_not_reopen_an_abandoned_edition(self):
        store, conn = store_with()
        store.finish(CLAIM, {'schedule_status': 'failed'}, 'd1', {'status': 'failed'})
        assert "WHEN status = 'abandoned' AND CAST(:status AS text) = 'failed' THEN status" in str(conn.execute.call_args[0][0])

    def test_rejects_unknown_columns(self):
        store, _ = store_with()
        with pytest.raises(ValueError):
            store.finish(CLAIM, {'claim_token': None})
