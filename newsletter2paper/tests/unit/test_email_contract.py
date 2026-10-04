"""Contract tests for EmailService against the Resend HTTP API (mocked with respx).

Each case checks the classification (`error_kind`), the user-readable error that ends up on the
delivery and in issues.last_run_error, and the Retry-After hint the scheduler uses.
Snapshots of the rendered bodies live in tests/unit/snapshots; regenerate them with
UPDATE_SNAPSHOTS=1 after an intentional template change.
"""
import json
import os
from pathlib import Path

import httpx
import pytest
import respx

import services.email_service as email_mod
from services.email_service import EmailService

RESEND_EMAILS = "https://api.resend.com/emails"
SNAPSHOTS = Path(__file__).parent / "snapshots"


@pytest.fixture
def service(monkeypatch):
    monkeypatch.setattr(email_mod, "RESEND_API_KEY", "re_test_key")
    monkeypatch.setattr(email_mod, "EMAIL_FROM", "Paper <paper@example.com>")
    monkeypatch.setattr(email_mod.resend, "api_url", "https://api.resend.com")
    return EmailService()


def resend_error(status, name, message, headers=None):
    return httpx.Response(status, json={"statusCode": status, "name": name, "message": message},
                          headers=headers or {})


def send(service, **kw):
    return service.send("reader@example.com", "https://cdn.example.com/a.pdf", issue_title="Morning", **kw)


@respx.mock
def test_accepted_returns_message_id_and_sends_idempotency_key(service):
    route = respx.post(RESEND_EMAILS).mock(return_value=httpx.Response(200, json={"id": "msg-123"}))
    result = send(service, idempotency_key="delivery-d1-0")
    assert result.ok and result.message_id == "msg-123" and result.error is None
    request = route.calls.last.request
    assert request.headers["Idempotency-Key"] == "delivery-d1-0"
    assert request.headers["Authorization"] == "Bearer re_test_key"
    assert json.loads(request.content)["to"] == ["reader@example.com"]


@pytest.mark.parametrize("response, kind, error, retry_after", [
    (resend_error(422, "validation_error", "Invalid `to` field."),
     "permanent", "email: Resend rejected the message (422: Invalid `to` field.)", None),
    (resend_error(403, "validation_error", "The example.com domain is not verified."),
     "permanent", "email: Resend rejected the message (403: The example.com domain is not verified.)", None),
    (resend_error(401, "missing_api_key", "Missing API key in the authorization header"),
     "permanent", "config: Resend rejected the API key (Missing API key in the authorization header.)", None),
    (resend_error(429, "rate_limit_exceeded", "Too many requests.", {"Retry-After": "120"}),
     "transient", "email: Resend rate limit reached (Too many requests.)", 120),
    (resend_error(429, "daily_quota_exceeded", "You have reached your daily email sending quota.",
                  {"retry-after": "3600"}),
     "transient", "email: Resend rate limit reached (You have reached your daily email sending quota.)", 3600),
    (resend_error(500, "application_error", "Something went wrong."),
     "transient", "email: Resend is unavailable (500: Something went wrong.)", None),
    (resend_error(503, "service_unavailable", "Down for maintenance."),
     "transient", "email: Resend is unavailable (503: Down for maintenance.)", None),
    (resend_error(409, "concurrent_idempotent_requests", "Same idempotency key in flight."),
     "transient", "email: Resend is still processing an identical request", None),
    (resend_error(409, "invalid_idempotent_request", "Key reused with a different payload."),
     "permanent", "email: Resend rejected the message (409: Key reused with a different payload.)", None),
])
@respx.mock
def test_error_classification(service, response, kind, error, retry_after):
    respx.post(RESEND_EMAILS).mock(return_value=response)
    result = send(service)
    assert (result.ok, result.error_kind, result.error, result.retry_after) == (False, kind, error, retry_after)


@respx.mock
def test_403_invalid_api_key_is_a_config_error(service):
    respx.post(RESEND_EMAILS).mock(return_value=resend_error(403, "invalid_api_key", "API key is invalid"))
    result = send(service)
    assert result.error_kind == "permanent" and result.error.startswith("config: Resend rejected the API key")


@respx.mock
def test_timeout_is_transient_with_unknown_outcome(service):
    respx.post(RESEND_EMAILS).mock(side_effect=httpx.ReadTimeout("timed out"))
    result = send(service)
    assert result.error_kind == "transient" and result.error.startswith("email: could not reach Resend")
    assert "ReadTimeout" in result.error
    assert result.outcome_unknown  # Resend may have accepted it; the retry must reuse the key


@respx.mock
def test_error_responses_have_a_known_outcome(service):
    respx.post(RESEND_EMAILS).mock(return_value=resend_error(500, "application_error", "boom"))
    assert not send(service).outcome_unknown


@respx.mock
def test_connection_error_is_transient(service):
    respx.post(RESEND_EMAILS).mock(side_effect=httpx.ConnectError("connection refused"))
    assert send(service).error_kind == "transient"


@pytest.mark.parametrize("patch, recipient, error", [
    ({"RESEND_API_KEY": None}, "reader@example.com", "config: RESEND_API_KEY is not set"),
    ({"EMAIL_FROM": ""}, "reader@example.com", "config: EMAIL_FROM is not set"),
    ({}, None, "config: no recipient email address is set"),
    ({}, "", "config: no recipient email address is set"),
])
@respx.mock
def test_configuration_problems_fail_permanently_without_a_request(service, monkeypatch, patch, recipient, error):
    route = respx.post(RESEND_EMAILS)
    for name, value in patch.items():
        monkeypatch.setattr(email_mod, name, value)
    result = service.send(recipient, "https://cdn.example.com/a.pdf")
    assert (result.ok, result.error_kind, result.error) == (False, "permanent", error)
    assert not route.called


# ---------------------------------------------------------------------------
# Rendered bodies
# ---------------------------------------------------------------------------

HOSTILE_TITLE = '<img src=x onerror=alert(1)> & "Friends"'
PDF_URL = 'https://cdn.example.com/a.pdf?token=abc&sig="x"'


def check_snapshot(name, actual):
    path = SNAPSHOTS / name
    if os.environ.get("UPDATE_SNAPSHOTS"):
        path.write_text(actual)
    assert actual == path.read_text(), f"{name} changed; rerun with UPDATE_SNAPSHOTS=1 if intended"


def test_html_body_escapes_user_content(service):
    body = service._build_html(PDF_URL, HOSTILE_TITLE)
    assert "<img" not in body and "&lt;img src=x onerror=alert(1)&gt; &amp; &quot;Friends&quot;" in body
    assert 'href="https://cdn.example.com/a.pdf?token=abc&amp;sig=&quot;x&quot;"' in body
    check_snapshot("email_body.html", body)


def test_text_body_keeps_values_literal(service):
    body = service._build_text(PDF_URL, HOSTILE_TITLE)
    assert HOSTILE_TITLE in body and PDF_URL in body
    check_snapshot("email_body.txt", body)
