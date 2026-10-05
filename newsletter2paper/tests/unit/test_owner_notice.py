"""The email that tells an owner an edition was given up on, and the wording of failure reasons."""
import json
from datetime import datetime, timezone

import httpx
import pytest
import respx

import services.email_service as email_mod
from services.email_service import EmailService, describe_failure

RESEND_EMAILS = "https://api.resend.com/emails"
NEXT = datetime(2026, 10, 9, 13, 0, tzinfo=timezone.utc)   # Friday 09:00 in New York


@pytest.fixture
def service(monkeypatch):
    monkeypatch.setattr(email_mod, "RESEND_API_KEY", "re_test_key")
    monkeypatch.setattr(email_mod, "EMAIL_FROM", "Paper <paper@example.com>")
    monkeypatch.setattr(email_mod.resend, "api_url", "https://api.resend.com")
    return EmailService()


def notice(service, **over):
    args = dict(to="owner@example.com", issue_title="Morning Brief", period="2026-W41",
                error="email: Resend is unavailable (503: down)", next_run_at=NEXT,
                timezone_name="America/New_York", idempotency_key="owner-notice-d1")
    args.update(over)
    return service.send_owner_notice(**args)


@respx.mock
def test_goes_to_the_owner_with_an_idempotency_key_and_says_why_and_when_next(service):
    route = respx.post(RESEND_EMAILS).mock(return_value=httpx.Response(200, json={"id": "n-1"}))

    result = notice(service)

    assert result.ok and result.message_id == "n-1"
    request = route.calls.last.request
    body = json.loads(request.content)
    assert body["to"] == ["owner@example.com"]
    assert request.headers["Idempotency-Key"] == "owner-notice-d1"
    assert "Morning Brief" in body["subject"]
    for part in (body["text"], body["html"]):
        assert "the email could not be sent (Resend is unavailable (503: down))" in part
        assert "Friday, October 9 at 9:00 AM EDT" in part       # the next slot, in the issue's timezone
    assert "still on" in body["text"]


@respx.mock
def test_user_controlled_values_are_escaped_in_html(service):
    route = respx.post(RESEND_EMAILS).mock(return_value=httpx.Response(200, json={"id": "n-1"}))

    notice(service, issue_title='<script>alert(1)</script>', error='email: <img src=x onerror=1>')

    html_body = json.loads(route.calls.last.request.content)["html"]
    assert "<script>" not in html_body and "<img" not in html_body
    assert "&lt;script&gt;" in html_body


@respx.mock
def test_one_shot_slots_are_not_shown_as_a_period(service):
    route = respx.post(RESEND_EMAILS).mock(return_value=httpx.Response(200, json={"id": "n-1"}))
    notice(service, period="once-2026-10-05T09:00:00+00:00", next_run_at=None)
    text = json.loads(route.calls.last.request.content)["text"]
    assert "once-" not in text and "next edition" not in text


@respx.mock
def test_without_a_next_slot_the_notice_does_not_promise_one(service):
    route = respx.post(RESEND_EMAILS).mock(return_value=httpx.Response(200, json={"id": "n-1"}))
    notice(service, next_run_at=None)
    assert "still on" not in json.loads(route.calls.last.request.content)["text"]


@respx.mock
@pytest.mark.parametrize("to", [None, "", "  "])
def test_no_owner_address_is_a_permanent_failure_and_nothing_is_sent(service, to):
    route = respx.post(RESEND_EMAILS)
    result = notice(service, to=to)
    assert not result.ok and result.error_kind == "permanent" and not route.called


@respx.mock
def test_provider_errors_are_classified_like_other_sends(service):
    respx.post(RESEND_EMAILS).mock(return_value=httpx.Response(
        500, json={"statusCode": 500, "name": "application_error", "message": "boom"}))
    result = notice(service)
    assert not result.ok and result.error_kind == "transient"


def test_missing_configuration_is_reported_not_raised(monkeypatch):
    monkeypatch.setattr(email_mod, "RESEND_API_KEY", None)
    result = EmailService().send_owner_notice("owner@example.com", "T", "2026-W41", "email: x")
    assert not result.ok and result.error == "config: RESEND_API_KEY is not set"


@pytest.mark.parametrize("error, expected", [
    ("pdf: renderer timed out", "we could not build the PDF from your newsletters (renderer timed out)."),
    ("email: Resend rejected the message (422: bad)", "the email could not be sent (Resend rejected the message (422: bad))."),
    ("config: no recipient email address is set", "the newspaper is not set up to send (no recipient email address is set)."),
    ("unexpected error: boom", "unexpected error: boom."),
    (None, "an unknown error occurred."),
    ("", "an unknown error occurred."),
])
def test_describe_failure(error, expected):
    assert describe_failure(error) == expected
