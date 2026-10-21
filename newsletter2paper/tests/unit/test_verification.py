"""Recipient verification tokens and the public confirm / unsubscribe pages."""
from datetime import datetime, timedelta, timezone
from uuid import uuid4

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from routers import email_links
from services import verification
from tests.unit.conftest import FakeSupabase

NOW = datetime(2026, 10, 14, 9, tzinfo=timezone.utc)
ISSUE = {"id": "i1", "title": "My Paper", "target_email": "Reader@Example.com"}


def stored(token="tok", **over):
    row = {"issue_id": "i1", "email": "reader@example.com", "token_hash": verification.hash_token(token),
           "expires_at": (NOW + timedelta(hours=1)).isoformat(), "consumed_at": None}
    row.update(over)
    return row


class TestIssueToken:
    def test_stores_a_hash_and_a_24_hour_expiry(self):
        db = FakeSupabase({("email_verifications", "select"): []})
        token = verification.issue_token(db, "i1", " Reader@Example.com ", NOW)
        (_, _, row, _), = db.calls_for("email_verifications", "insert")
        assert row["token_hash"] == verification.hash_token(token) and token not in str(row)
        assert row["email"] == "Reader@Example.com"
        assert row["expires_at"] == (NOW + timedelta(hours=24)).isoformat()

    def test_tokens_are_unguessable_and_distinct(self):
        db = FakeSupabase({("email_verifications", "select"): []})
        a, b = (verification.issue_token(db, "i1", "a@b.co", NOW) for _ in range(2))
        assert a != b and len(a) >= 40

    def test_the_fourth_request_in_an_hour_is_refused(self):
        db = FakeSupabase({("email_verifications", "select"): [{}, {}, {}]})
        with pytest.raises(verification.RateLimited):
            verification.issue_token(db, "i1", "a@b.co", NOW)
        assert db.calls_for("email_verifications", "insert") == []


class TestPeek:
    def peek(self, row, issue=ISSUE):
        db = FakeSupabase({("email_verifications", "select"): [row] if row else [], ("issues", "select"): [issue]})
        return verification.peek(db, "tok", NOW)

    def test_a_valid_token_is_usable(self):
        out = self.peek(stored())
        assert out.ok and out.title == "My Paper"

    @pytest.mark.parametrize("row", [None, stored(consumed_at=NOW.isoformat()),
                                     stored(expires_at=(NOW - timedelta(seconds=1)).isoformat()),
                                     stored(expires_at=NOW.isoformat())])
    def test_unknown_used_or_expired_tokens_are_invalid(self, row):
        out = self.peek(row)
        assert not out.ok and out.reason == verification.INVALID

    def test_a_token_for_a_previous_address_is_refused(self):
        out = self.peek(stored(), {**ISSUE, "target_email": "new@example.com"})
        assert not out.ok and out.reason == verification.CHANGED


class TestConfirm:
    def confirm(self, consumed, issue=ISSUE, updated=({"id": "i1"},)):
        db = FakeSupabase({("email_verifications", "update"): consumed, ("issues", "select"): [issue],
                           ("issues", "update"): list(updated)})
        return db, verification.confirm(db, "tok", NOW)

    def test_marks_the_address_verified_and_consumes_the_token_once(self):
        db, out = self.confirm([stored()])
        assert out.ok
        (_, _, payload, filters), = db.calls_for("email_verifications", "update")
        assert payload == {"consumed_at": NOW.isoformat()}
        assert ("token_hash", verification.hash_token("tok")) in filters
        assert any(c == "consumed_at" for c, _ in filters) and any(c == "expires_at" for c, _ in filters)
        (_, _, verified, vfilters), = db.calls_for("issues", "update")
        assert verified == {"target_email_verified_at": NOW.isoformat()}
        assert ("target_email", "Reader@Example.com") in vfilters  # only if the address is still the same

    def test_a_reused_or_expired_token_changes_nothing(self):
        db, out = self.confirm([])
        assert not out.ok and out.reason == verification.INVALID and db.calls_for("issues", "update") == []

    def test_an_address_changed_since_the_email_was_sent_is_not_verified(self):
        db, out = self.confirm([stored()], {**ISSUE, "target_email": "other@example.com"})
        assert not out.ok and out.reason == verification.CHANGED and db.calls_for("issues", "update") == []

    def test_losing_the_race_with_an_address_change_is_not_verified(self):
        _, out = self.confirm([stored()], updated=())
        assert not out.ok and out.reason == verification.CHANGED


class TestAccountEmail:
    def db(self, email):
        db = FakeSupabase()
        db.client.auth.admin.get_user_by_id.return_value.user.email = email
        return db

    def test_matches_ignoring_case_and_whitespace(self):
        assert verification.is_account_email(self.db("Me@X.co"), "u1", " me@x.CO ")

    def test_other_addresses_and_missing_data_do_not_match(self):
        assert not verification.is_account_email(self.db("me@x.co"), "u1", "you@x.co")
        assert not verification.is_account_email(self.db("me@x.co"), None, "me@x.co")
        assert not verification.is_account_email(self.db("me@x.co"), "u1", None)

    def test_a_lookup_failure_never_verifies(self):
        db = FakeSupabase()
        db.client.auth.admin.get_user_by_id.side_effect = RuntimeError("boom")
        assert not verification.is_account_email(db, "u1", "me@x.co")


FAR = "2999-01-01T00:00:00+00:00"  # the pages use the real clock


def page_client(db):
    app = FastAPI()
    app.include_router(email_links.router)
    app.dependency_overrides[email_links.get_db_service] = lambda: db
    return TestClient(app)


class TestVerifyPages:
    def test_get_shows_a_button_and_confirms_nothing(self):
        db = FakeSupabase({("email_verifications", "select"): [stored(expires_at=FAR)], ("issues", "select"): [ISSUE]})
        resp = page_client(db).get("/email/verify?token=tok")
        assert resp.status_code == 200 and "<form method=\"post\"" in resp.text and "My Paper" in resp.text
        assert db.calls_for("email_verifications", "update") == [] and db.calls_for("issues", "update") == []

    def test_get_with_a_bad_token_is_400(self):
        db = FakeSupabase({("email_verifications", "select"): []})
        assert page_client(db).get("/email/verify?token=nope").status_code == 400

    def test_the_title_is_escaped(self):
        db = FakeSupabase({("email_verifications", "select"): [stored(expires_at=FAR)],
                           ("issues", "select"): [{**ISSUE, "title": "<script>alert(1)</script>"}]})
        assert "<script>" not in page_client(db).get("/email/verify?token=tok").text

    def test_post_confirms(self):
        db = FakeSupabase({("email_verifications", "update"): [stored(expires_at=FAR)], ("issues", "select"): [ISSUE],
                           ("issues", "update"): [{"id": "i1"}]})
        resp = page_client(db).post("/email/verify?token=tok")
        assert resp.status_code == 200 and "confirmed" in resp.text
        assert db.calls_for("issues", "update")

    def test_post_with_a_used_token_is_400(self):
        db = FakeSupabase({("email_verifications", "update"): []})
        assert page_client(db).post("/email/verify?token=tok").status_code == 400


class TestUnsubscribe:
    TOKEN = uuid4()

    def test_get_only_shows_a_button(self):
        db = FakeSupabase({("issues", "select"): [{"id": "i1", "title": "My Paper"}]})
        resp = page_client(db).get(f"/u/{self.TOKEN}")
        assert resp.status_code == 200 and "Unsubscribe" in resp.text and db.calls_for("issues", "update") == []

    def test_post_turns_auto_send_off(self):
        db = FakeSupabase({("issues", "update"): [{"id": "i1"}]})
        # A mail client's RFC 8058 one-click request: POST with the List-Unsubscribe=One-Click body.
        resp = page_client(db).post(f"/u/{self.TOKEN}", content="List-Unsubscribe=One-Click",
                                    headers={"content-type": "application/x-www-form-urlencoded"})
        assert resp.status_code == 200
        (_, _, payload, filters), = db.calls_for("issues", "update")
        assert payload == {"auto_send": False} and filters == (("unsubscribe_token", str(self.TOKEN)),)

    def test_unknown_token_is_404_and_a_malformed_one_never_reaches_the_database(self):
        db = FakeSupabase({("issues", "update"): []})
        assert page_client(db).post(f"/u/{self.TOKEN}").status_code == 404
        assert page_client(db).post("/u/not-a-uuid").status_code == 422
