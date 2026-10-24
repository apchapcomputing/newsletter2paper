"""Opt-in staging check against the real Resend API, using Resend's test addresses.

delivered@resend.dev always accepts; bounced@resend.dev is accepted by the API and bounces afterwards.
Nothing reaches a real inbox. Skipped unless RESEND_STAGING_API_KEY and EMAIL_FROM are set:

    RESEND_STAGING_API_KEY=re_... EMAIL_FROM='Paper <paper@example.com>' pytest tests/e2e/test_resend_staging.py -v

See openspec/changes/scheduled-delivery-production/runbook.md.
"""
import os
import uuid

import pytest

KEY = os.environ.get("RESEND_STAGING_API_KEY")
FROM = os.environ.get("EMAIL_FROM")
pytestmark = pytest.mark.skipif(not (KEY and FROM), reason="RESEND_STAGING_API_KEY / EMAIL_FROM not set")


@pytest.fixture
def service(monkeypatch):
    import services.email_service as email_mod
    monkeypatch.setattr(email_mod, "RESEND_API_KEY", KEY)
    monkeypatch.setattr(email_mod, "EMAIL_FROM", FROM)
    return email_mod.EmailService()


def test_delivery_email_with_unsubscribe_headers_is_accepted(service):
    result = service.send("delivered@resend.dev", "https://example.com/edition.pdf", subject="E2E: edition",
                          issue_title="E2E", idempotency_key=f"e2e-{uuid.uuid4()}",
                          unsubscribe_url="https://example.com/u/00000000-0000-0000-0000-000000000000")
    assert result.ok, result.error
    assert result.message_id


def test_same_idempotency_key_is_accepted_twice_and_is_one_email(service):
    key = f"e2e-{uuid.uuid4()}"
    first = service.send("delivered@resend.dev", "https://example.com/edition.pdf", idempotency_key=key)
    second = service.send("delivered@resend.dev", "https://example.com/edition.pdf", idempotency_key=key)
    assert first.ok and second.ok
    assert first.message_id == second.message_id  # Resend returned the original email


def test_confirmation_email_is_accepted(service):
    result = service.send_verification("delivered@resend.dev", "https://example.com/email/verify?token=e2e", "E2E")
    assert result.ok, result.error


def test_a_bounce_address_is_accepted_by_the_api(service):
    # The bounce arrives later, as a webhook; the send itself succeeds.
    assert service.send("bounced@resend.dev", "https://example.com/edition.pdf").ok


def test_an_invalid_address_is_a_permanent_failure(service):
    result = service.send("not-an-address", "https://example.com/edition.pdf")
    assert not result.ok and result.error_kind == "permanent"
