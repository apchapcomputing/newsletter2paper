import os
from datetime import datetime, timezone, timedelta
from unittest.mock import MagicMock
from zoneinfo import ZoneInfo

import pytest
import time_machine

os.environ.setdefault('SUPABASE_DATABASE_URL', 'sqlite://')

from services import scheduler as sch
from services.delivery_store import Claim, ClaimLost, DeliveryStore
from services.email_service import SendResult
from services.scheduling import first_slot, retry_delay  # noqa: F401
from services.scheduler import (
    LOCK_TIMEOUT_MINUTES, SEND_NOW_COOLDOWN_MINUTES, SchedulerService, SendNowCooldown,
    check_lock_timeout,
)

UTC = timezone.utc


def dt(*args):
    return datetime(*args, tzinfo=UTC)


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

    def mark_sending(self, claim, delivery_id, pdf_url, recipient, idempotency_key):
        self._call('mark_sending', delivery_id, pdf_url, recipient, idempotency_key)

    def finish(self, claim, issue_fields, delivery_id=None, delivery_fields=None, cadence=None):
        self._call('finish')
        self.finished.append((issue_fields, delivery_id, delivery_fields))
        self.cadence = cadence

    # Owner notification
    notice = {'id': 'd1', 'owner_email': 'owner@x.co', 'title': 'T', 'period_key': '2026-10-05',
              'error': 'email: boom', 'next_run_at': '2026-10-06T09:00:00+00:00', 'schedule_timezone': 'UTC'}
    pending = ()

    def claim_owner_notice(self, delivery_id):
        self._call('claim_notice', delivery_id)
        return self.notice

    def release_owner_notice(self, delivery_id):
        self._call('release_notice', delivery_id)

    def unnotified_abandoned(self, limit=5):
        self._call('sweep')
        return list(self.pending)


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

    s.owner_notice = MagicMock(return_value=SendResult.sent('notice-1'))

    def send_notice(notice):
        s.store.log.append(('notice_email', notice['owner_email'], notice['id']))
        return s.owner_notice(notice)

    monkeypatch.setattr(s, '_send_owner_notice', send_notice)
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
        # The previous run committed 'sending' with its key and died; Resend may already have the email.
        svc.store.existing = delivery(status='sending', pdf_url='http://old', attempts=1,
                                      idempotency_key='delivery-d1-1')
        await svc._process_issue(CLAIM)
        svc.generate.assert_not_called()
        assert svc.store.log[2] == ('email', 'a@b.co', 'http://old', 'delivery-d1-1')
        assert svc.store.finished[0][2]['status'] == 'sent'

    async def test_email_failure_schedules_retry_and_keeps_pdf(self, svc):
        svc.email.return_value = TRANSIENT_FAILURE
        res = await svc._process_issue(CLAIM)
        assert not res['success']
        assert ('mark_sending', 'd1', 'http://pdf', 'a@b.co', 'delivery-d1-0') in svc.store.log  # PDF stored for the retry
        issue_fields, _, d = svc.store.finished[0]
        assert d['status'] == 'failed' and d['attempts'] == 1 and d['error'].startswith('email:')
        assert d['idempotency_key'] is None  # Resend answered with an error: the next attempt gets a new key
        assert issue_fields['schedule_status'] == 'failed'
        assert issue_fields['next_run_at'] == d['next_attempt_at']

    async def test_timeout_keeps_the_key_for_the_retry(self, svc):
        # No response: Resend may have accepted the email, so the retry must reuse the key.
        svc.email.return_value = SendResult.failed('transient', 'email: could not reach Resend (timeout)',
                                                   outcome_unknown=True)
        await svc._process_issue(CLAIM)
        d = svc.store.finished[0][2]
        assert d['status'] == 'failed' and d['attempts'] == 1 and 'idempotency_key' not in d

    async def test_timeout_then_retry_sends_the_same_key_twice(self, svc):
        # Run 1: Resend accepts the email but the response times out.
        svc.email.return_value = SendResult.failed('transient', 'email: could not reach Resend (ReadTimeout)',
                                                   outcome_unknown=True)
        await svc._process_issue(CLAIM)
        _, _, _, _, stored_key = next(e for e in svc.store.log if e[0] == 'mark_sending')
        _, _, failed = svc.store.finished[0]
        assert failed['attempts'] == 1 and 'idempotency_key' not in failed  # stored key left in place

        # Run 2: the retry resumes the delivery as the database now has it.
        svc.store = FakeStore(existing=delivery(status='failed', pdf_url='http://pdf',
                                                attempts=failed['attempts'], idempotency_key=stored_key))
        svc.email.return_value = SendResult.sent('msg-1')
        await svc._process_issue(CLAIM)
        sent_keys = [e[4] for e in svc.store.log if e[0] == 'mark_sending']
        assert stored_key == 'delivery-d1-0' and sent_keys == ['delivery-d1-0']  # not delivery-d1-1
        assert svc.store.finished[0][2]['status'] == 'sent'

    async def test_retry_after_unknown_outcome_reuses_the_stored_key(self, svc):
        svc.store.existing = delivery(status='failed', pdf_url='http://old', attempts=1,
                                      idempotency_key='delivery-d1-0')
        await svc._process_issue(CLAIM)
        assert svc.store.log[2][3] == 'delivery-d1-0'

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
        assert steps(svc) == ['open', 'finish', 'claim_notice', 'notice_email']   # the owner is told why nothing was sent
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
        # The attempt counts (retries stay bounded) but the stored delivery-d1-0 key is kept.
        assert d['status'] == 'failed' and d['attempts'] == 1 and 'idempotency_key' not in d

    async def test_unexpected_error_before_sending_clears_the_key(self, svc):
        svc.generate.side_effect = RuntimeError('render crashed')
        await svc._process_issue(CLAIM)
        assert svc.store.finished[0][2]['idempotency_key'] is None

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


# ---------------------------------------------------------------------------
# Retry window, slot anchoring and owner notification (issue #23)
# ---------------------------------------------------------------------------

def daily_issue(**over):
    base = {'frequency': 'daily', 'schedule_time_local': '09:00', 'next_run_at': '2026-10-05T09:00:00+00:00'}
    base.update(over)
    return issue(**base)


def open_delivery(attempts, slot=dt(2026, 10, 5, 9)):
    return delivery(status='failed' if attempts else 'pending', attempts=attempts, pdf_url='http://pdf',
                    scheduled_for=slot, period_key='2026-10-05')


async def attempt(svc, at, attempts, result=TRANSIENT_FAILURE):
    """Run one attempt at `at`, as the poll would, and return (issue_fields, delivery_fields)."""
    svc.store = FakeStore(existing=open_delivery(attempts))
    svc.email.return_value = result
    with time_machine.travel(at, tick=False):
        await svc._process_issue(CLAIM)
    issue_fields, _, d = svc.store.finished[-1]
    return issue_fields, d


class TestRetryWindow:
    async def test_full_ladder_then_gives_up_at_the_next_slot(self, svc):
        svc._issue = daily_issue()
        at, expected_delay = dt(2026, 10, 5, 9), [1, 2, 4, 8]
        for n, hours in enumerate(expected_delay):
            fields, d = await attempt(svc, at, n)
            assert d['status'] == 'failed' and d['attempts'] == n + 1
            assert fields['schedule_status'] == 'failed' and fields['next_run_at'] == at + timedelta(hours=hours)
            at = fields['next_run_at']
        assert at == dt(2026, 10, 6, 0)   # 15h after the slot, still before the next 09:00

        fields, d = await attempt(svc, at, 4)   # fifth failure

        assert d['status'] == 'abandoned' and 'gave up after 5 attempts' in d['error']
        assert fields['schedule_status'] == 'idle'
        assert fields['next_run_at'] == dt(2026, 10, 6, 9)       # the next slot, not 'now + 1 day'
        assert fields['last_run_error'] == d['error']
        assert 'auto_send' not in fields                          # the schedule stays on

    async def test_retry_that_would_pass_the_next_slot_is_abandoned_instead(self, svc):
        svc._issue = daily_issue()
        # Fourth failure at 06:00 the next morning: +8h would be 14:00, after the 09:00 slot.
        fields, d = await attempt(svc, dt(2026, 10, 6, 6), 3)

        assert d['status'] == 'abandoned' and 'next edition is due first' in d['error']
        assert fields['next_run_at'] == dt(2026, 10, 6, 9) and fields['schedule_status'] == 'idle'

    async def test_retry_landing_exactly_on_the_next_slot_is_abandoned_one_minute_earlier_is_not(self, svc):
        svc._issue = daily_issue()
        # attempts=1 -> the next backoff is 2h; the next slot is Oct 6 09:00.
        _, just_in_time = await attempt(svc, dt(2026, 10, 6, 6, 59), 1)    # retry at 08:59
        _, on_the_slot = await attempt(svc, dt(2026, 10, 6, 7, 0), 1)      # retry at 09:00
        assert just_in_time['status'] == 'failed'
        assert on_the_slot['status'] == 'abandoned'

    async def test_retry_after_from_the_provider_can_also_close_the_window(self, svc):
        svc._issue = daily_issue()
        limited = SendResult.failed('transient', 'email: rate limited', retry_after=24 * 3600)
        fields, d = await attempt(svc, dt(2026, 10, 5, 9), 0, limited)
        assert d['status'] == 'abandoned'

    async def test_one_shot_issues_have_no_deadline_so_they_keep_retrying(self, svc):
        svc._issue = issue(frequency='once', next_run_at='2026-10-05T09:00:00+00:00')
        fields, d = await attempt(svc, dt(2026, 10, 5, 9), 3)
        assert d['status'] == 'failed' and fields['next_run_at'] == dt(2026, 10, 5, 17)

    async def test_the_period_key_stays_with_the_slot_when_a_retry_runs_in_the_next_period(self, svc):
        # A retry claimed at 02:00 on Oct 6 still serves Oct 5's slot, so it is Oct 5's delivery.
        svc._issue = daily_issue(next_run_at='2026-10-06T02:00:00+00:00')
        svc.store = FakeStore(existing=open_delivery(2))
        with time_machine.travel(dt(2026, 10, 6, 2), tick=False):
            await svc._process_issue(CLAIM)
        issue_fields, _, d = svc.store.finished[-1]
        assert d['status'] == 'sent'
        assert issue_fields['next_run_at'] == dt(2026, 10, 6, 9)


class TestSlotAnchoring:
    async def test_late_success_keeps_next_weeks_slot(self, svc):
        # Weekly Friday 09:00 New York; succeeds on the third attempt at 16:00 local.
        ny = ZoneInfo('America/New_York')
        slot = datetime(2026, 10, 9, 9, 0, tzinfo=ny).astimezone(UTC)
        late = datetime(2026, 10, 9, 16, 0, tzinfo=ny).astimezone(UTC)
        svc._issue = issue(frequency='weekly', schedule_weekday=4, schedule_timezone='America/New_York',
                           schedule_time_local='09:00', next_run_at=late.isoformat())
        svc.store = FakeStore(existing=delivery(status='failed', attempts=2, pdf_url='http://pdf', scheduled_for=slot,
                                                period_key='2026-W41'))
        svc.email.return_value = SendResult.sent('msg-1')

        with time_machine.travel(late, tick=False):
            await svc._process_issue(CLAIM)

        fields, _, d = svc.store.finished[-1]
        assert d['status'] == 'sent'
        assert fields['next_run_at'] == datetime(2026, 10, 16, 9, 0, tzinfo=ny).astimezone(UTC)

    @pytest.mark.parametrize('freq, slot, finished, expected', [
        # No weekday / day-of-month configured: the slot's own weekday / day is kept even when the
        # retry that finally succeeds runs on a later day.
        ('weekly', dt(2026, 10, 9, 9), dt(2026, 10, 10, 2), dt(2026, 10, 16, 9)),     # Friday slot, done Saturday 02:00
        ('monthly', dt(2026, 10, 15, 9), dt(2026, 10, 17, 3), dt(2026, 11, 15, 9)),   # 15th slot, done on the 17th
        ('daily', dt(2026, 10, 5, 9), dt(2026, 10, 5, 23), dt(2026, 10, 6, 9)),
    ])
    async def test_late_success_stays_on_the_slots_weekday_or_day_when_none_is_configured(
            self, svc, freq, slot, finished, expected):
        svc._issue = issue(frequency=freq, schedule_time_local='09:00', schedule_weekday=None,
                           schedule_day_of_month=None, next_run_at=finished.isoformat())
        svc.store = FakeStore(existing=delivery(status='failed', attempts=2, pdf_url='http://pdf', scheduled_for=slot))
        svc.email.return_value = SendResult.sent('msg-1')

        with time_machine.travel(finished, tick=False):
            await svc._process_issue(CLAIM)

        assert svc.store.finished[-1][0]['next_run_at'] == expected

    async def test_a_period_already_handled_advances_from_its_slot(self, svc):
        svc._issue = daily_issue()
        svc.store = FakeStore(existing=delivery(status='sent', scheduled_for=dt(2026, 10, 5, 9)))
        with time_machine.travel(dt(2026, 10, 5, 9, 30), tick=False):
            await svc._process_issue(CLAIM)
        assert svc.store.finished[-1][0]['next_run_at'] == dt(2026, 10, 6, 9)

    def test_enabling_waits_for_the_next_configured_slot(self):
        s = SchedulerService.__new__(SchedulerService)
        s.store = MagicMock()
        seen = {}

        def init(first_run):
            seen['at'] = first_run({'frequency': 'weekly', 'schedule_timezone': 'UTC', 'schedule_time_local': '09:00',
                                    'schedule_weekday': 4, 'schedule_day_of_month': None})
            return [('i1', seen['at'])]

        s.store.initialize_unscheduled.side_effect = init
        with time_machine.travel(dt(2026, 10, 7, 15), tick=False):   # a Wednesday
            s._initialize_unscheduled()
        assert seen['at'] == dt(2026, 10, 9, 9)

    def test_one_shot_issues_are_due_right_away(self):
        s = SchedulerService.__new__(SchedulerService)
        s.store = MagicMock()
        seen = {}
        s.store.initialize_unscheduled.side_effect = lambda cb: seen.setdefault('at', cb({'frequency': 'once'})) and []
        with time_machine.travel(dt(2026, 10, 7, 15), tick=False):
            s._initialize_unscheduled()
        assert seen['at'] == dt(2026, 10, 7, 15)


class TestOwnerNotice:
    async def abandon(self, svc, error_result=None):
        svc._issue = daily_issue()
        fields, d = await attempt(svc, dt(2026, 10, 5, 21), 4, error_result or TRANSIENT_FAILURE)
        assert d['status'] == 'abandoned'

    async def test_abandoning_an_edition_emails_the_owner_once(self, svc):
        await self.abandon(svc)
        assert [e[0] for e in svc.store.log if e[0] in ('claim_notice', 'notice_email', 'release_notice')] == [
            'claim_notice', 'notice_email']
        assert ('notice_email', 'owner@x.co', 'd1') in svc.store.log

    async def test_a_permanent_failure_also_notifies(self, svc):
        await self.abandon(svc, SendResult.failed('permanent', 'email: Resend rejected the message (422: bad address)'))
        assert 'notice_email' in steps(svc)

    async def test_the_schedule_stays_on_when_the_owner_is_told(self, svc):
        await self.abandon(svc)
        fields = svc.store.finished[-1][0]
        assert 'auto_send' not in fields and fields['next_run_at'] is not None

    async def test_no_notice_when_it_was_already_sent(self, svc):
        svc.store = FakeStore(existing=open_delivery(4))
        svc.store.notice = None          # claim_owner_notice found owner_notified_at already set
        svc._issue = daily_issue()
        svc.email.return_value = TRANSIENT_FAILURE
        with time_machine.travel(dt(2026, 10, 5, 21), tick=False):
            await svc._process_issue(CLAIM)
        assert 'notice_email' not in steps(svc)

    async def test_failed_send_releases_the_flag_so_a_later_tick_retries(self, svc):
        svc.owner_notice.return_value = SendResult.failed('transient', 'email: Resend is unavailable')
        await self.abandon(svc)
        assert steps(svc)[-2:] == ['notice_email', 'release_notice']

    async def test_an_exception_while_sending_releases_the_flag_and_does_not_break_the_run(self, svc):
        svc.owner_notice.side_effect = RuntimeError('boom')
        await self.abandon(svc)    # the run itself still completes and is recorded as abandoned
        assert steps(svc)[-1] == 'release_notice'

    async def test_a_failing_claim_does_not_break_the_run_and_releases_nothing(self, svc):
        svc.store.claim_owner_notice = MagicMock(side_effect=RuntimeError('db down'))
        svc._issue = daily_issue()
        await attempt(svc, dt(2026, 10, 5, 21), 4)   # replaces the store; re-patch below
        store = svc.store
        store.claim_owner_notice = MagicMock(side_effect=RuntimeError('db down'))
        svc._notify_owner('d1')
        assert 'release_notice' not in steps(svc)

    async def test_manual_sends_never_notify(self, svc):
        svc.email.return_value = TRANSIENT_FAILURE
        await svc.send_now(Claim('i1', 'tok', previous_status='idle'))
        assert 'claim_notice' not in steps(svc)

    def test_sweep_notifies_abandoned_editions_whose_notice_was_lost(self, svc):
        svc.store.pending = ['d7', 'd8']
        svc._notify_pending_owners()
        assert [e for e in svc.store.log if e[0] == 'claim_notice'] == [('claim_notice', 'd7'), ('claim_notice', 'd8')]

    def test_every_poll_ends_with_the_sweep(self, monkeypatch):
        s = SchedulerService.__new__(SchedulerService)
        s.batch_size = 5
        s.store = MagicMock()
        s.store.initialize_unscheduled.return_value = []
        s.store.claim_next_due.return_value = None
        s.store.unnotified_abandoned.return_value = []
        s._job_check_and_process()
        s.store.unnotified_abandoned.assert_called_once()
