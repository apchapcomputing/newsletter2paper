"""DeliveryStore against a real, migrated Postgres (claims, fencing, unique period index, triggers).

Runs only when SCHEDULER_TEST_DATABASE_URL is set; CI points it at the local Supabase started by
.github/workflows/test-db-migrations.yml. Locally:

    npx supabase db start && npx supabase db reset
    SCHEDULER_TEST_DATABASE_URL=postgresql://postgres:postgres@127.0.0.1:54322/postgres \
        pytest tests/integration/test_delivery_store_pg.py
"""
import os
import uuid
from datetime import datetime, timedelta, timezone

import pytest

DB_URL = os.environ.get('SCHEDULER_TEST_DATABASE_URL')
pytestmark = pytest.mark.skipif(not DB_URL, reason='SCHEDULER_TEST_DATABASE_URL not set')

if DB_URL:
    from sqlalchemy import create_engine, text
    from sqlalchemy.exc import IntegrityError

from services.delivery_store import CADENCE_COLUMNS, Claim, ClaimLost, DeliveryStore

LOCK_TIMEOUT = 15


@pytest.fixture
def engine():
    eng = create_engine(DB_URL)
    yield eng
    with eng.begin() as conn:
        conn.execute(text("DELETE FROM public.issues WHERE title LIKE 'delivery-store-test%'"))
        if conn.execute(text("SELECT to_regclass('public.users')")).scalar():
            conn.execute(text("DELETE FROM public.users WHERE email LIKE 'delivery-store-test-%'"))
    eng.dispose()


@pytest.fixture
def store(engine):
    return DeliveryStore(engine)


def make_issue(engine, **over):
    values = {'title': 'delivery-store-test', 'format': 'essay', 'frequency': 'weekly',
              'auto_send': True, 'schedule_status': 'idle',
              'next_run_at': datetime.now(timezone.utc) - timedelta(minutes=1), 'locked_at': None}
    values.update(over)
    cols = ', '.join(values)
    params = ', '.join(f':{c}' for c in values)
    with engine.begin() as conn:
        return str(conn.execute(text(f"INSERT INTO public.issues ({cols}) VALUES ({params}) RETURNING id"), values).scalar())


def row(engine, sql, **params):
    with engine.begin() as conn:
        return conn.execute(text(sql), params).mappings().fetchone()


def loaded_cadence(engine, issue_id):
    """The cadence as a run would have loaded it at its start."""
    return dict(row(engine, f"SELECT {', '.join(CADENCE_COLUMNS)} FROM public.issues WHERE id = :id", id=issue_id))


def slot():
    return datetime(2026, 10, 2, 9, tzinfo=timezone.utc)


class TestClaims:
    def test_skip_locked_passes_over_a_row_another_connection_holds(self, engine, store):
        make_issue(engine)
        with engine.connect() as other:
            tx = other.begin()
            other.execute(text("SELECT id FROM public.issues WHERE title = 'delivery-store-test' FOR UPDATE"))
            assert store.claim_next_due(LOCK_TIMEOUT) is None  # skipped, not blocked
            tx.rollback()
        assert store.claim_next_due(LOCK_TIMEOUT) is not None

    def test_fresh_lock_is_left_alone(self, engine, store):
        make_issue(engine)
        assert store.claim_next_due(LOCK_TIMEOUT) is not None
        assert store.claim_next_due(LOCK_TIMEOUT) is None

    def test_stale_lock_is_taken_over_with_a_new_token(self, engine, store):
        issue_id = make_issue(engine, schedule_status='processing',
                              locked_at=datetime.now(timezone.utc) - timedelta(minutes=LOCK_TIMEOUT + 5))
        claim = store.claim_next_due(LOCK_TIMEOUT)
        assert claim.issue_id == issue_id
        r = row(engine, "SELECT schedule_status, claim_token FROM public.issues WHERE id = :id", id=issue_id)
        assert r['schedule_status'] == 'processing' and str(r['claim_token']) == claim.token


class TestFencing:
    def test_taken_over_worker_writes_nothing(self, engine, store):
        issue_id = make_issue(engine)
        old = store.claim_next_due(LOCK_TIMEOUT)
        delivery = store.open_scheduled_delivery(old, slot(), '2026-W40')
        # The first run stalls past the lock timeout and a second worker takes over.
        with engine.begin() as conn:
            conn.execute(text("UPDATE public.issues SET locked_at = now() - interval '1 hour' WHERE id = :id"),
                         {"id": issue_id})
        new = store.claim_next_due(LOCK_TIMEOUT)
        assert new.issue_id == issue_id and new.token != old.token

        with pytest.raises(ClaimLost):
            store.mark_sending(old, delivery['id'], 'http://pdf', 'a@b.co', 'delivery-key-0')
        with pytest.raises(ClaimLost):
            store.finish(old, {'schedule_status': 'idle', 'last_run_error': 'stale'}, delivery['id'], {'status': 'sent'})

        r = row(engine, "SELECT schedule_status, last_run_error FROM public.issues WHERE id = :id", id=issue_id)
        assert r['schedule_status'] == 'processing' and r['last_run_error'] is None
        d = row(engine, "SELECT status FROM public.issue_deliveries WHERE id = :id", id=delivery['id'])
        assert d['status'] == 'pending'

    def test_current_worker_writes_issue_and_delivery_together(self, engine, store):
        issue_id = make_issue(engine)
        cadence = loaded_cadence(engine, issue_id)
        claim = store.claim_next_due(LOCK_TIMEOUT)
        delivery = store.open_scheduled_delivery(claim, slot(), '2026-W40')
        store.finish(claim, {'schedule_status': 'idle', 'next_run_at': slot() + timedelta(days=7)},
                     delivery['id'], {'status': 'sent', 'sent_at': datetime.now(timezone.utc)}, cadence=cadence)
        r = row(engine, "SELECT schedule_status, next_run_at FROM public.issues WHERE id = :id", id=issue_id)
        assert r['schedule_status'] == 'idle' and r['next_run_at'] == slot() + timedelta(days=7)
        assert row(engine, "SELECT status FROM public.issue_deliveries WHERE id = :id", id=delivery['id'])['status'] == 'sent'


class TestDeliveries:
    def test_one_scheduled_delivery_per_period(self, engine, store):
        issue_id = make_issue(engine)
        claim = store.claim_next_due(LOCK_TIMEOUT)
        first = store.open_scheduled_delivery(claim, slot(), '2026-W40')
        store.finish(claim, {'schedule_status': 'processing'}, first['id'], {'status': 'sent'})

        again = store.open_scheduled_delivery(claim, slot(), '2026-W40')
        assert again['id'] == first['id'] and again['status'] == 'sent'
        with pytest.raises(IntegrityError):
            with engine.begin() as conn:
                conn.execute(text(
                    "INSERT INTO public.issue_deliveries (issue_id, trigger, period_key, scheduled_for) "
                    "VALUES (:id, 'scheduled', '2026-W40', now())"
                ), {"id": issue_id})

    def test_manual_deliveries_do_not_count_against_the_period(self, engine, store):
        make_issue(engine)
        claim = store.claim_next_due(LOCK_TIMEOUT)
        store.create_manual_delivery(claim)
        store.create_manual_delivery(claim)
        scheduled = store.open_scheduled_delivery(claim, slot(), '2026-W40')
        assert scheduled['trigger'] == 'scheduled' and scheduled['status'] == 'pending'

    def test_crash_after_sending_reopens_the_same_delivery(self, engine, store):
        issue_id = make_issue(engine)
        claim = store.claim_next_due(LOCK_TIMEOUT)
        delivery = store.open_scheduled_delivery(claim, slot(), '2026-W40')
        store.mark_sending(claim, delivery['id'], 'http://pdf', 'a@b.co', 'delivery-key-0')
        # Process dies here. The lock goes stale and the next poll reclaims the issue.
        with engine.begin() as conn:
            conn.execute(text("UPDATE public.issues SET locked_at = now() - interval '1 hour' WHERE id = :id"),
                         {"id": issue_id})
        recovered = store.claim_next_due(LOCK_TIMEOUT)
        reopened = store.open_scheduled_delivery(recovered, slot() + timedelta(hours=1), 'ignored')
        assert reopened['id'] == delivery['id']
        assert reopened['status'] == 'sending' and reopened['attempts'] == 0 and reopened['pdf_url'] == 'http://pdf'
        assert reopened['idempotency_key'] == 'delivery-key-0'  # the recovered run resends with the same key


class TestCadenceTrigger:
    def test_cadence_change_resets_schedule_and_abandons_open_edition(self, engine, store):
        issue_id = make_issue(engine)
        claim = store.claim_next_due(LOCK_TIMEOUT)
        pending = store.open_scheduled_delivery(claim, slot(), '2026-W40')
        store.finish(claim, {'schedule_status': 'failed', 'last_run_error': 'email: x'}, pending['id'], {'status': 'failed'})

        with engine.begin() as conn:
            conn.execute(text("UPDATE public.issues SET frequency = 'daily' WHERE id = :id"), {"id": issue_id})

        r = row(engine, "SELECT next_run_at, schedule_status, last_run_error FROM public.issues WHERE id = :id", id=issue_id)
        assert r['next_run_at'] is None and r['schedule_status'] == 'idle' and r['last_run_error'] is None
        d = row(engine, "SELECT status, error FROM public.issue_deliveries WHERE id = :id", id=pending['id'])
        assert d['status'] == 'abandoned' and d['error'] == 'config: schedule changed'

    def test_edition_already_sending_is_not_abandoned(self, engine, store):
        issue_id = make_issue(engine)
        claim = store.claim_next_due(LOCK_TIMEOUT)
        delivery = store.open_scheduled_delivery(claim, slot(), '2026-W40')
        store.mark_sending(claim, delivery['id'], 'http://pdf', 'a@b.co', 'delivery-key-0')
        with engine.begin() as conn:
            conn.execute(text("UPDATE public.issues SET auto_send = false WHERE id = :id"), {"id": issue_id})
        assert row(engine, "SELECT status FROM public.issue_deliveries WHERE id = :id", id=delivery['id'])['status'] == 'sending'

    def test_in_flight_send_finishing_after_a_cadence_change_defers_to_the_new_cadence(self, engine, store):
        issue_id = make_issue(engine)
        cadence = loaded_cadence(engine, issue_id)
        claim = store.claim_next_due(LOCK_TIMEOUT)
        delivery = store.open_scheduled_delivery(claim, slot(), '2026-W40')
        store.mark_sending(claim, delivery['id'], 'http://pdf', 'a@b.co', 'delivery-key-0')
        with engine.begin() as conn:  # owner switches to daily while the email is going out
            conn.execute(text("UPDATE public.issues SET frequency = 'daily' WHERE id = :id"), {"id": issue_id})

        # The run computed next_run_at from the weekly cadence it loaded.
        store.finish(claim, {'schedule_status': 'idle', 'next_run_at': slot() + timedelta(days=7)},
                     delivery['id'], {'status': 'sent'}, cadence=cadence)

        r = row(engine, "SELECT schedule_status, next_run_at FROM public.issues WHERE id = :id", id=issue_id)
        assert r['next_run_at'] is None and r['schedule_status'] == 'idle'  # next poll uses the daily cadence
        assert row(engine, "SELECT status FROM public.issue_deliveries WHERE id = :id", id=delivery['id'])['status'] == 'sent'

    def test_failure_after_a_cadence_change_does_not_strand_the_issue(self, engine, store):
        issue_id = make_issue(engine)
        cadence = loaded_cadence(engine, issue_id)
        claim = store.claim_next_due(LOCK_TIMEOUT)
        delivery = store.open_scheduled_delivery(claim, slot(), '2026-W40')
        with engine.begin() as conn:  # trigger abandons the pending edition
            conn.execute(text("UPDATE public.issues SET schedule_weekday = 2 WHERE id = :id"), {"id": issue_id})

        retry_at = datetime.now(timezone.utc) + timedelta(hours=1)
        store.finish(claim, {'schedule_status': 'failed', 'next_run_at': retry_at, 'last_run_error': 'pdf: x'},
                     delivery['id'], {'status': 'failed', 'attempts': 1, 'next_attempt_at': retry_at}, cadence=cadence)

        # 'failed' with no next_run_at would never be claimed or re-initialised.
        r = row(engine, "SELECT schedule_status, next_run_at FROM public.issues WHERE id = :id", id=issue_id)
        assert r['schedule_status'] == 'idle' and r['next_run_at'] is None
        d = row(engine, "SELECT status, next_attempt_at FROM public.issue_deliveries WHERE id = :id", id=delivery['id'])
        assert d['status'] == 'abandoned' and d['next_attempt_at'] is None

    def test_one_shot_completion_is_kept_when_cadence_unchanged(self, engine, store):
        issue_id = make_issue(engine, frequency='once')
        cadence = loaded_cadence(engine, issue_id)
        claim = store.claim_next_due(LOCK_TIMEOUT)
        delivery = store.open_scheduled_delivery(claim, slot(), 'once-x')
        store.finish(claim, {'schedule_status': 'idle', 'next_run_at': None, 'auto_send': False},
                     delivery['id'], {'status': 'sent'}, cadence=cadence)
        assert row(engine, "SELECT auto_send FROM public.issues WHERE id = :id", id=issue_id)['auto_send'] is False
        assert row(engine, "SELECT status FROM public.issue_deliveries WHERE id = :id", id=delivery['id'])['status'] == 'sent'

    def test_unrelated_update_keeps_the_schedule(self, engine, store):
        due = datetime.now(timezone.utc) + timedelta(days=1)
        issue_id = make_issue(engine, next_run_at=due)
        with engine.begin() as conn:
            conn.execute(text("UPDATE public.issues SET title = 'delivery-store-test renamed' WHERE id = :id"), {"id": issue_id})
        assert row(engine, "SELECT next_run_at FROM public.issues WHERE id = :id", id=issue_id)['next_run_at'] == due


def test_send_now_claim_sets_a_token(engine, store):
    issue_id = make_issue(engine, next_run_at=None)
    claim = store.claim_for_send_now(issue_id, LOCK_TIMEOUT, 10)
    assert isinstance(claim, Claim)
    r = row(engine, "SELECT claim_token FROM public.issues WHERE id = :id", id=issue_id)
    assert str(r['claim_token']) == claim.token


def rollback_sql():
    """The commented-out rollback block from the migration, minus its BEGIN/COMMIT."""
    path = os.path.join(os.path.dirname(__file__), '..', '..', 'supabase', 'migrations',
                        '20261005000000_issue_deliveries.sql')
    lines = open(path).read().split('-- Rollback', 1)[1].splitlines()
    start, end = lines.index('-- BEGIN;'), lines.index('-- COMMIT;')
    return '\n'.join(line[3:] for line in lines[start + 1:end])


def test_rollback_restores_columns_from_delivery_records(engine, store):
    issue_id = make_issue(engine)
    claim = store.claim_next_due(LOCK_TIMEOUT)
    sent = store.open_scheduled_delivery(claim, slot(), '2026-W40')
    store.finish(claim, {'schedule_status': 'processing'}, sent['id'],
                 {'status': 'sent', 'sent_at': datetime.now(timezone.utc)})
    retry = store.open_scheduled_delivery(claim, slot() + timedelta(days=7), '2026-W41')
    store.mark_sending(claim, retry['id'], 'http://pdf', 'a@b.co', 'delivery-key-0')
    store.finish(claim, {'schedule_status': 'failed'}, retry['id'], {'status': 'failed', 'attempts': 2})

    with engine.connect() as conn:
        tx = conn.begin()  # DDL is transactional in Postgres; undone below
        try:
            conn.exec_driver_sql(rollback_sql())
            r = conn.execute(text(
                "SELECT run_attempts, last_sent_period, pending_pdf_url, pending_period FROM public.issues WHERE id = :id"
            ), {"id": issue_id}).mappings().one()
            assert dict(r) == {'run_attempts': 2, 'last_sent_period': '2026-W40',
                               'pending_pdf_url': 'http://pdf', 'pending_period': '2026-W41'}
            assert conn.execute(text("SELECT to_regclass('public.issue_deliveries')")).scalar() is None
        finally:
            tx.rollback()


def make_owner(engine, issue_id):
    user_id = str(uuid.uuid4())
    with engine.begin() as conn:
        # The local baseline still has the legacy users table (and an FK to it); production doesn't.
        if conn.execute(text("SELECT to_regclass('public.users')")).scalar():
            conn.execute(text(
                "INSERT INTO public.users (id, email, username, password, first_name, last_name) "
                "VALUES (:id, :email, :email, 'x', 'T', 'T')"
            ), {'id': user_id, 'email': f'delivery-store-test-{user_id}@example.com'})
        conn.execute(text("INSERT INTO public.user_issues (user_id, issue_id) VALUES (:u, :i)"),
                     {'u': user_id, 'i': issue_id})
    return user_id


def make_sent_delivery(engine, issue_id, sent_ago):
    with engine.begin() as conn:
        return str(conn.execute(text(
            "INSERT INTO public.issue_deliveries (issue_id, trigger, scheduled_for, status, pdf_url, sent_at) "
            "VALUES (:i, 'manual', now(), 'sent', 'https://pdf.example/a.pdf', now() - :ago) RETURNING id"
        ), {'i': issue_id, 'ago': sent_ago}).scalar())


class TestAnalyticsLookups:
    def test_owner_id(self, engine, store):
        issue_id = make_issue(engine)
        assert store.owner_id(issue_id) is None  # guest issue
        user_id = make_owner(engine, issue_id)
        assert store.owner_id(issue_id) == user_id

    def test_first_real_open_sets_opened_at_once(self, engine, store):
        delivery_id = make_sent_delivery(engine, make_issue(engine), timedelta(hours=2))
        first = store.record_open(delivery_id, timedelta(seconds=30))
        assert first['pdf_url'] == 'https://pdf.example/a.pdf'
        assert first['first_open'] is True and first['likely_scanner'] is False
        opened_at = row(engine, "SELECT opened_at FROM public.issue_deliveries WHERE id = :id", id=delivery_id)['opened_at']
        assert opened_at is not None
        again = store.record_open(delivery_id, timedelta(seconds=30))
        assert again['first_open'] is False
        assert row(engine, "SELECT opened_at FROM public.issue_deliveries WHERE id = :id", id=delivery_id)['opened_at'] == opened_at

    def test_scanner_prefetch_does_not_count_as_an_open(self, engine, store):
        delivery_id = make_sent_delivery(engine, make_issue(engine), timedelta(seconds=5))
        info = store.record_open(delivery_id, timedelta(seconds=30))
        assert info['likely_scanner'] is True
        assert row(engine, "SELECT opened_at FROM public.issue_deliveries WHERE id = :id", id=delivery_id)['opened_at'] is None

    def test_unsent_or_unknown_delivery_is_none(self, engine, store):
        issue_id = make_issue(engine)
        with engine.begin() as conn:
            pending = str(conn.execute(text(
                "INSERT INTO public.issue_deliveries (issue_id, trigger, scheduled_for) "
                "VALUES (:i, 'manual', now()) RETURNING id"), {'i': issue_id}).scalar())
        assert store.record_open(pending, timedelta(seconds=30)) is None
        assert store.record_open(str(uuid.uuid4()), timedelta(seconds=30)) is None
