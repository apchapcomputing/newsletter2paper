from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest

from services import analytics_service as analytics


@pytest.fixture(autouse=True)
def fresh():
    analytics.reset_for_tests()
    yield
    analytics.reset_for_tests()


@pytest.fixture
def client(monkeypatch):
    fake = MagicMock()
    monkeypatch.setattr(analytics, '_client', fake)
    monkeypatch.setattr(analytics, '_initialised', True)
    return fake


def test_off_without_a_key(monkeypatch):
    monkeypatch.delenv('POSTHOG_API_KEY', raising=False)
    assert analytics.enabled() is False
    analytics.capture('delivery_sent', 'u1', {'a': 1})
    analytics.capture_exception(RuntimeError('x'))
    analytics.shutdown()


def test_on_with_a_key(monkeypatch):
    monkeypatch.setenv('POSTHOG_API_KEY', 'phc_test')
    assert analytics.enabled() is True
    assert analytics._client.host.startswith('https://eu.i.posthog.com')


def test_capture_drops_pii_prone_and_empty_props(client):
    analytics.capture('delivery_failed', 'u1', {
        'recipient': 'a@b.co', 'error': 'email: bad a@b.co', 'title': 'T', 'url': 'https://x',
        'error_kind': 'permanent', 'retry_after': None,
    })
    client.capture.assert_called_once_with('delivery_failed', distinct_id='u1', properties={'error_kind': 'permanent'})


def test_capture_exception_passes_the_distinct_id(client):
    exc = RuntimeError('boom')
    analytics.capture_exception(exc, 'anon-1', {'stage': 'render', 'email': 'a@b.co'})
    client.capture_exception.assert_called_once_with(exc, distinct_id='anon-1', properties={'stage': 'render'})


def test_never_raises(client):
    client.capture.side_effect = RuntimeError('posthog down')
    client.capture_exception.side_effect = RuntimeError('posthog down')
    client.shutdown.side_effect = RuntimeError('posthog down')
    analytics.capture('delivery_sent', 'u1')
    analytics.capture_exception(ValueError('x'))
    analytics.shutdown()


def test_request_context_reads_forwarded_posthog_headers():
    request = SimpleNamespace(
        headers={'x-posthog-distinct-id': 'anon-0001', 'x-posthog-session-id': 'session-0001'},
        url=SimpleNamespace(path='/pdf/generate/abc'), method='POST',
    )
    distinct_id, props = analytics.request_context(request, stage='render')
    assert distinct_id == 'anon-0001'
    assert props == {'$session_id': 'session-0001', 'path': '/pdf/generate/abc', 'method': 'POST', 'stage': 'render'}


@pytest.mark.parametrize('value', [None, '', 'short', '$posthog_cookieless', 'a@b.co', 'x' * 65, 'id with spaces'])
def test_forged_or_malformed_forwarded_ids_are_ignored(value):
    request = SimpleNamespace(headers={'x-posthog-distinct-id': value, 'x-posthog-session-id': value},
                              url=SimpleNamespace(path='/x'), method='GET')
    distinct_id, props = analytics.request_context(request)
    assert distinct_id is None and props['$session_id'] is None


def test_client_scrubs_exception_messages_before_sending(monkeypatch):
    monkeypatch.setenv('POSTHOG_API_KEY', 'phc_test')
    assert analytics.enabled()
    hook = analytics._client.before_send
    event = {'properties': {
        '$exception_list': [{'type': 'PDFGenerationError', 'value': 'fetch https://x.substack.com/feed failed',
                             'stacktrace': {'frames': [{'filename': 'routers/pdf.py'}]}}],
        '$exception_message': 'mail to a@b.co bounced',
        'stage': 'render for a@b.co',
        '$current_url': 'https://api.example/pdf',
    }}
    props = hook(event)['properties']
    assert props['$exception_list'][0]['value'] == 'fetch [url] failed'
    assert props['$exception_list'][0]['stacktrace']['frames'] == [{'filename': 'routers/pdf.py'}]
    assert props['$exception_message'] == 'mail to [email] bounced'
    assert props['stage'] == 'render for [email]'
    assert props['$current_url'] == 'https://api.example/pdf'
