"""GET /d/{delivery_id}: the tracked link in delivery emails."""
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace
from uuid import uuid4

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from routers import deliveries

NOW = datetime(2026, 10, 5, 12, tzinfo=timezone.utc)
DELIVERY_ID = uuid4()


class Store:
    def __init__(self, info):
        self.info, self.calls = info, []

    def record_open(self, delivery_id, scanner_window):
        self.calls.append((delivery_id, scanner_window))
        return self.info

    def owner_id(self, issue_id):
        return 'user-1'


def opened(**over):
    info = {'issue_id': 'i1', 'trigger': 'scheduled', 'pdf_url': 'https://cdn.example.com/a.pdf?token=t',
            'sent_at': NOW - timedelta(hours=3), 'opened_at': None, 'db_now': NOW,
            'first_open': True, 'likely_scanner': False}
    info.update(over)
    return info


def client(store):
    app = FastAPI()
    app.include_router(deliveries.router)
    app.state.scheduler = SimpleNamespace(store=store) if store else None
    return TestClient(app)


@pytest.fixture
def events(monkeypatch):
    sent = []
    monkeypatch.setattr(deliveries.analytics, 'enabled', lambda: True)
    monkeypatch.setattr(deliveries.analytics, 'capture', lambda e, d, p: sent.append((e, d, p)))
    return sent


def test_redirects_to_the_pdf_and_records_the_open(events):
    store = Store(opened())
    res = client(store).get(f'/d/{DELIVERY_ID}', follow_redirects=False)
    assert res.status_code == 302
    assert res.headers['location'] == 'https://cdn.example.com/a.pdf?token=t'
    assert store.calls == [(DELIVERY_ID, deliveries.SCANNER_WINDOW)]
    assert events == [('edition_opened', 'user-1', {
        'issue_id': 'i1', 'delivery_id': str(DELIVERY_ID), 'trigger': 'scheduled',
        'first_open': True, 'likely_scanner': False, 'hours_since_sent': 3.0})]


def test_still_redirects_without_analytics():
    res = client(Store(opened())).get(f'/d/{DELIVERY_ID}', follow_redirects=False)
    assert res.status_code == 302


def test_unknown_delivery_is_404(events):
    res = client(Store(None)).get(f'/d/{DELIVERY_ID}', follow_redirects=False)
    assert res.status_code == 404 and events == []


def test_malformed_id_is_rejected_before_the_database():
    store = Store(opened())
    assert client(store).get('/d/not-a-uuid').status_code == 422
    assert store.calls == []


def test_scheduler_not_running_is_503():
    assert client(None).get(f'/d/{DELIVERY_ID}').status_code == 503
