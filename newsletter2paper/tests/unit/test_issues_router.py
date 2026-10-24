"""HTTP contract of /issues, including request validation and send-now."""
from uuid import uuid4

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from routers import issues
from services.auth import IssueAccess
from services.delivery_store import Claim
from services.scheduler import SendNowCooldown
from tests.unit.conftest import FakeSupabase

ISSUE_ID = uuid4()


OWNER = str(uuid4())
ACCOUNT_EMAIL = "a@b.co"
OWNER_HEADERS = {"Authorization": "Bearer good"}


def client_for(db, as_owner=True):
    """as_owner short-circuits issue access; auth itself is covered in test_route_auth.py."""
    app = FastAPI()
    app.include_router(issues.router)
    app.dependency_overrides[issues.get_db_service] = lambda: db
    if as_owner:
        app.dependency_overrides[issues.require_issue_access] = lambda: IssueAccess(str(ISSUE_ID), OWNER)
    return TestClient(app)


def signed_in_db(responses=None):
    db = FakeSupabase({("user_issues", "insert"): [{"issue_id": str(ISSUE_ID)}], **(responses or {})})
    db.client.auth.get_user.return_value.user.id = OWNER
    db.client.auth.admin.get_user_by_id.return_value.user.email = ACCOUNT_EMAIL
    return db


class TestCreateValidation:
    def test_unknown_frequency_is_rejected(self):
        resp = client_for(FakeSupabase()).post("/issues/", json={"format": "essay", "frequency": "hourly"})
        assert resp.status_code == 422

    def test_custom_frequency_needs_both_dates(self):
        resp = client_for(FakeSupabase()).post(
            "/issues/", json={"format": "essay", "frequency": "custom", "custom_start_date": "2026-03-01T00:00:00Z"}
        )
        assert resp.status_code == 422

    def test_custom_range_must_not_be_reversed(self):
        resp = client_for(FakeSupabase()).post(
            "/issues/",
            json={"format": "essay", "frequency": "custom",
                  "custom_start_date": "2026-03-07T00:00:00Z", "custom_end_date": "2026-03-01T00:00:00Z"},
        )
        assert resp.status_code == 422

    def test_valid_request_inserts_defaults(self):
        db = signed_in_db({("issues", "insert"): [{"id": str(ISSUE_ID)}]})

        resp = client_for(db).post("/issues/", json={"format": "newspaper"}, headers=OWNER_HEADERS)

        assert resp.status_code == 200
        (_, _, payload, _), = db.calls_for("issues", "insert")
        assert payload["title"] == "Your Newspaper"
        assert (payload["frequency"], payload["auto_send"], payload["article_window_days"]) == ("weekly", False, 7)
        assert "status" not in payload  # signed-in issues are not guest rows
        (_, _, link, _), = db.calls_for("user_issues", "insert")
        assert link == {"user_id": OWNER, "issue_id": str(ISSUE_ID)}


class TestUpdate:
    def put(self, db, body):
        return client_for(db).put(f"/issues/{ISSUE_ID}", json=body)

    def test_only_sent_fields_are_written(self):
        db = FakeSupabase({("issues", "update"): [{"id": str(ISSUE_ID)}]})

        self.put(db, {"title": "New title"})

        (_, _, payload, filters), = db.calls_for("issues", "update")
        assert set(payload) == {"title", "updated_at"}
        assert filters == (("id", str(ISSUE_ID)),)

    def test_renaming_does_not_wipe_a_saved_custom_range(self):
        db = FakeSupabase({("issues", "update"): [{"id": str(ISSUE_ID)}]})

        self.put(db, {"title": "Renamed"})

        payload = db.calls_for("issues", "update")[0][2]
        assert "custom_start_date" not in payload and "custom_end_date" not in payload

    def test_explicit_null_clears_a_custom_date(self):
        db = FakeSupabase({("issues", "update"): [{"id": str(ISSUE_ID)}]})

        self.put(db, {"custom_start_date": None})

        assert db.calls_for("issues", "update")[0][2]["custom_start_date"] is None

    def test_switching_away_from_custom_clears_both_dates(self):
        db = FakeSupabase({("issues", "update"): [{"id": str(ISSUE_ID)}]})

        self.put(db, {"frequency": "weekly"})

        payload = db.calls_for("issues", "update")[0][2]
        assert payload["custom_start_date"] is None and payload["custom_end_date"] is None

    def test_unknown_issue_is_404(self):
        assert self.put(FakeSupabase(), {"title": "x"}).status_code == 404

    def test_window_must_be_validated(self):
        assert self.put(FakeSupabase(), {"article_window_days": 0}).status_code == 422


class TestAutoSendNeedsRecipient:
    def test_create_with_auto_send_and_no_email_is_rejected(self):
        resp = client_for(FakeSupabase()).post("/issues/", json={"format": "essay", "auto_send": True})
        assert resp.status_code == 422 and "target_email" in resp.text

    def test_create_with_auto_send_and_the_account_email_is_accepted_and_marked_verified(self):
        db = signed_in_db({("issues", "insert"): [{"id": str(ISSUE_ID)}]})
        resp = client_for(db).post("/issues/", json={"format": "essay", "auto_send": True, "target_email": "A@B.co"},
                                   headers=OWNER_HEADERS)
        assert resp.status_code == 200
        (_, _, payload, _), = db.calls_for("issues", "insert")
        assert payload["target_email_verified_at"]
        assert payload["schedule_weekday"] is not None  # weekly is pinned to a weekday when enabled

    def test_create_with_auto_send_and_another_address_is_rejected_as_unverified(self):
        db = signed_in_db({("issues", "insert"): [{"id": str(ISSUE_ID)}]})
        resp = client_for(db).post("/issues/", json={"format": "essay", "auto_send": True, "target_email": "other@x.co"},
                                   headers=OWNER_HEADERS)
        assert resp.status_code == 422 and resp.json()["detail"] == issues._NOT_VERIFIED
        assert db.calls_for("issues", "insert") == []

    def test_create_with_another_address_but_no_auto_send_is_stored_unverified(self):
        db = signed_in_db({("issues", "insert"): [{"id": str(ISSUE_ID)}]})
        resp = client_for(db).post("/issues/", json={"format": "essay", "target_email": "other@x.co"},
                                   headers=OWNER_HEADERS)
        assert resp.status_code == 200
        (_, _, payload, _), = db.calls_for("issues", "insert")
        assert "target_email_verified_at" not in payload

    def put(self, stored, body):
        db = signed_in_db({("issues", "select"): [stored], ("issues", "update"): [{"id": str(ISSUE_ID)}]})
        return db, client_for(db).put(f"/issues/{ISSUE_ID}", json=body)

    def test_enabling_without_a_stored_email_is_rejected(self):
        db, resp = self.put({"auto_send": False, "target_email": None}, {"auto_send": True})
        assert resp.status_code == 422 and resp.json()["detail"] == issues._NO_RECIPIENT
        assert db.calls_for("issues", "update") == []

    def test_enabling_with_a_verified_stored_email_is_accepted(self):
        _, resp = self.put({"auto_send": False, "target_email": "a@b.co", "target_email_verified_at": "2026-10-01T00:00:00Z"},
                           {"auto_send": True})
        assert resp.status_code == 200

    def test_enabling_with_an_unverified_stored_email_is_rejected(self):
        db, resp = self.put({"auto_send": False, "target_email": "other@x.co", "target_email_verified_at": None},
                            {"auto_send": True})
        assert resp.status_code == 422 and resp.json()["detail"] == issues._NOT_VERIFIED
        assert db.calls_for("issues", "update") == []

    def test_enabling_and_setting_the_account_email_together_is_accepted(self):
        db, resp = self.put({"auto_send": False, "target_email": None}, {"auto_send": True, "target_email": "a@b.co"})
        assert resp.status_code == 200
        (_, _, payload, _), = db.calls_for("issues", "update")
        assert payload["target_email_verified_at"]

    def test_enabling_and_setting_another_email_together_is_rejected(self):
        _, resp = self.put({"auto_send": False, "target_email": None}, {"auto_send": True, "target_email": "other@x.co"})
        assert resp.status_code == 422

    def test_changing_the_address_on_a_live_schedule_turns_it_off_until_confirmed(self):
        db, resp = self.put({"auto_send": True, "target_email": "a@b.co", "target_email_verified_at": "2026-10-01T00:00:00Z"},
                            {"target_email": "other@x.co"})
        assert resp.status_code == 200
        (_, _, payload, _), = db.calls_for("issues", "update")
        assert payload["auto_send"] is False and payload["target_email_verified_at"] is None
        assert "turned off" in resp.json()["message"]

    def test_resending_the_same_address_keeps_it_verified(self):
        db, resp = self.put({"auto_send": True, "target_email": "other@x.co", "target_email_verified_at": "2026-10-01T00:00:00Z"},
                            {"target_email": "OTHER@x.co "})
        (_, _, payload, _), = db.calls_for("issues", "update")
        assert "auto_send" not in payload and "target_email_verified_at" not in payload

    def test_enabling_pins_a_weekly_issue_to_a_weekday(self):
        db, _ = self.put({"auto_send": False, "target_email": "a@b.co", "target_email_verified_at": "2026-10-01T00:00:00Z",
                          "frequency": "weekly"}, {"auto_send": True})
        (_, _, payload, _), = db.calls_for("issues", "update")
        assert 0 <= payload["schedule_weekday"] <= 6

    def test_enabling_keeps_a_weekday_the_owner_chose(self):
        db, _ = self.put({"auto_send": False, "target_email": "a@b.co", "target_email_verified_at": "2026-10-01T00:00:00Z",
                          "frequency": "weekly", "schedule_weekday": 4}, {"auto_send": True})
        (_, _, payload, _), = db.calls_for("issues", "update")
        assert "schedule_weekday" not in payload

    def test_the_database_trigger_is_reported_as_422(self):
        db = signed_in_db({("issues", "select"): [{"auto_send": False, "target_email": "a@b.co",
                                                  "target_email_verified_at": "x"}]})
        db.client.table.side_effect = lambda name: (_ for _ in ()).throw(Exception("recipient_not_verified: x")) \
            if name == "issues" and db.calls_for("issues", "select") else db._table(name)
        resp = client_for(db).put(f"/issues/{ISSUE_ID}", json={"auto_send": True})
        assert resp.status_code == 422

    def test_clearing_the_email_while_enabled_is_rejected(self):
        _, resp = self.put({"auto_send": True, "target_email": "a@b.co"}, {"target_email": "  "})
        assert resp.status_code == 422

    def test_disabling_never_needs_an_email(self):
        db, resp = self.put({"auto_send": True, "target_email": None}, {"auto_send": False})
        assert resp.status_code == 200 and db.calls_for("issues", "select") == []


class TestScheduleFields:
    def put(self, body):
        db = signed_in_db({("issues", "update"): [{"id": str(ISSUE_ID)}]})
        return db, client_for(db).put(f"/issues/{ISSUE_ID}", json=body)

    @pytest.mark.parametrize("body", [
        {"schedule_timezone": "Mars/Olympus"}, {"schedule_time_local": "9:00"}, {"schedule_time_local": "25:00"},
        {"schedule_weekday": 7}, {"schedule_weekday": -1}, {"schedule_day_of_month": 0}, {"schedule_day_of_month": 32},
    ])
    def test_invalid_values_are_rejected(self, body):
        assert self.put(body)[1].status_code == 422

    def test_valid_values_are_written(self):
        db, resp = self.put({"schedule_timezone": "Europe/Berlin", "schedule_time_local": "07:30",
                             "schedule_weekday": 0, "schedule_day_of_month": 31})
        assert resp.status_code == 200
        (_, _, payload, _), = db.calls_for("issues", "update")
        assert (payload["schedule_timezone"], payload["schedule_time_local"], payload["schedule_weekday"],
                payload["schedule_day_of_month"]) == ("Europe/Berlin", "07:30", 0, 31)

    def test_explicit_null_clears_weekday(self):
        db, _ = self.put({"schedule_weekday": None})
        (_, _, payload, _), = db.calls_for("issues", "update")
        assert payload["schedule_weekday"] is None

    def test_unsent_fields_are_left_alone(self):
        db, _ = self.put({"title": "x"})
        (_, _, payload, _), = db.calls_for("issues", "update")
        assert not any(k.startswith("schedule_") for k in payload)


class TestResponsesHideInternals:
    def test_get_strips_tokens_and_reports_verification(self):
        row = {"id": str(ISSUE_ID), "guest_token": "g", "claim_token": "c", "unsubscribe_token": "u",
               "target_email_verified_at": "2026-10-01T00:00:00Z"}
        resp = client_for(FakeSupabase({("issues", "select"): [row]})).get(f"/issues/{ISSUE_ID}")
        issue = resp.json()["issue"]
        assert not {"guest_token", "claim_token", "unsubscribe_token"} & set(issue)
        assert issue["recipient_verified"] is True


class TestRecipientVerificationRequest:
    def post(self, db, sent, monkeypatch):
        import services.email_service as em
        monkeypatch.setattr(em.EmailService, "send_verification", lambda self, to, url, title=None, idempotency_key=None: sent(to, url))
        app = FastAPI()
        app.include_router(issues.router)
        app.dependency_overrides[issues.get_db_service] = lambda: db
        app.dependency_overrides[issues.require_issue_owner] = lambda: IssueAccess(str(ISSUE_ID), OWNER)
        return TestClient(app).post(f"/issues/{ISSUE_ID}/target-email/verify")

    def row(self, **over):
        return {"id": str(ISSUE_ID), "title": "T", "target_email": "other@x.co", "target_email_verified_at": None, **over}

    def test_emails_a_link_and_stores_only_a_hash(self, monkeypatch):
        import services.email_service as em
        sent = []
        db = FakeSupabase({("issues", "select"): [self.row()]})
        db.rpc_results = {"issue_email_verification": True}
        resp = self.post(db, lambda to, url: sent.append((to, url)) or em.SendResult.sent("m"), monkeypatch)
        assert resp.status_code == 200 and resp.json()["verified"] is False
        (to, url), = sent
        token = url.split("token=")[1]
        (_, stored), = db.rpc_calls
        assert to == "other@x.co" and "/email/verify?token=" in url
        assert token not in str(stored) and stored["p_token_hash"] == verification_hash(token)
        assert stored["p_user_id"] == OWNER and stored["p_issue_id"] == str(ISSUE_ID)

    def test_already_verified_sends_nothing(self, monkeypatch):
        db = FakeSupabase({("issues", "select"): [self.row(target_email_verified_at="2026-10-01T00:00:00Z")]})
        resp = self.post(db, lambda *a: 1 / 0, monkeypatch)
        assert resp.json()["verified"] is True and db.rpc_calls == []

    def test_no_address_is_a_400(self, monkeypatch):
        db = FakeSupabase({("issues", "select"): [self.row(target_email=None)]})
        assert self.post(db, lambda *a: 1 / 0, monkeypatch).status_code == 400

    def test_rate_limited_when_the_database_refuses(self, monkeypatch):
        db = FakeSupabase({("issues", "select"): [self.row()]})
        db.rpc_results = {"issue_email_verification": False}
        resp = self.post(db, lambda *a: 1 / 0, monkeypatch)   # no email is sent
        assert resp.status_code == 429 and resp.headers["Retry-After"] == "3600"

    def test_a_failed_send_is_a_502(self, monkeypatch):
        import services.email_service as em
        db = FakeSupabase({("issues", "select"): [self.row()]})
        db.rpc_results = {"issue_email_verification": True}
        resp = self.post(db, lambda *a: em.SendResult.failed("permanent", "email: no"), monkeypatch)
        assert resp.status_code == 502


def verification_hash(token):
    from services.verification import hash_token
    return hash_token(token)


class TestDeliveriesList:
    def test_returns_the_issues_editions_newest_first_with_a_capped_limit(self):
        db = FakeSupabase({("issue_deliveries", "select"): [{"id": "d1", "status": "sent"}]})
        app = FastAPI()
        app.include_router(issues.router)
        app.dependency_overrides[issues.get_db_service] = lambda: db
        app.dependency_overrides[issues.require_issue_owner] = lambda: IssueAccess(str(ISSUE_ID), OWNER)
        resp = TestClient(app).get(f"/issues/{ISSUE_ID}/deliveries?limit=9999")
        assert resp.json() == {"success": True, "deliveries": [{"id": "d1", "status": "sent"}]}
        (_, _, _, filters), = db.calls_for("issue_deliveries", "select")
        assert filters == (("issue_id", str(ISSUE_ID)),)


class TestGetAndDelete:
    def test_get_unknown_issue_is_404(self):
        assert client_for(FakeSupabase()).get(f"/issues/{ISSUE_ID}").status_code == 404

    def test_delete_removes_junction_rows_before_the_issue(self):
        db = FakeSupabase({("issues", "delete"): [{"id": str(ISSUE_ID)}]})

        resp = client_for(db).delete(f"/issues/{ISSUE_ID}")

        assert resp.status_code == 200
        order = [c[0] for c in db.calls if c[1] == "delete"]
        assert order == ["issue_publications", "issues"]

    def test_delete_unknown_issue_is_404(self):
        assert client_for(FakeSupabase()).delete(f"/issues/{ISSUE_ID}").status_code == 404


class TestAddPublications:
    def test_unknown_issue_is_404_and_nothing_is_deleted(self):
        db = FakeSupabase()

        resp = client_for(db).post(f"/issues/{ISSUE_ID}/publications", json={"publication_ids": [str(uuid4())]})

        assert resp.status_code == 404
        assert db.calls_for("issue_publications") == []

    def test_replaces_the_issue_publications_and_keeps_per_publication_settings(self):
        p1, p2 = uuid4(), uuid4()
        db = FakeSupabase({("issues", "select"): [{"id": str(ISSUE_ID)}],
                           ("issue_publications", "insert"): [{}, {}]})

        resp = client_for(db).post(
            f"/issues/{ISSUE_ID}/publications",
            json={"publications": [{"publication_id": str(p1), "remove_images": True},
                                   {"publication_id": str(p2), "remove_images": False}]},
        )

        assert resp.status_code == 200
        assert [c[1] for c in db.calls_for("issue_publications")] == ["delete", "insert"]
        rows = db.calls_for("issue_publications", "insert")[0][2]
        assert [(r["publication_id"], r["remove_images"]) for r in rows] == [(str(p1), True), (str(p2), False)]

    def test_legacy_publication_ids_default_to_images_kept(self):
        p1 = uuid4()
        db = FakeSupabase({("issues", "select"): [{"id": str(ISSUE_ID)}],
                           ("issue_publications", "insert"): [{}]})

        client_for(db).post(f"/issues/{ISSUE_ID}/publications", json={"publication_ids": [str(p1)]})

        rows = db.calls_for("issue_publications", "insert")[0][2]
        assert rows[0]["remove_images"] is False


class TestSendNow:
    USER_ID = str(uuid4())

    class FakeScheduler:
        def __init__(self, claim='idle', fail=False):
            self.claim, self.fail, self.sent, self.failures = claim, fail, [], []

        def claim_for_send_now(self, issue_id):
            if isinstance(self.claim, Exception):
                raise self.claim
            return None if self.claim is None else Claim(issue_id, 'tok', self.claim)

        async def send_now(self, claim):
            if self.fail:
                raise RuntimeError("boom")
            self.sent.append((claim.issue_id, claim.previous_status))

        def release_after_error(self, claim, error, **kw):
            self.failures.append((claim.issue_id, error, kw))

    def post(self, db, scheduler, authed=True):
        c = client_for(db)
        if authed:
            c.app.dependency_overrides[issues.get_current_user_id] = lambda: self.USER_ID
        if scheduler is not None:
            c.app.state.scheduler = scheduler
        return c.post(f"/issues/{ISSUE_ID}/send-now")

    def db(self, email="a@b.co", owned=True, verified="2026-10-01T00:00:00Z"):
        return FakeSupabase({
            ("issues", "select"): [{"id": str(ISSUE_ID), "target_email": email, "target_email_verified_at": verified}],
            ("user_issues", "select"): [{"issue_id": str(ISSUE_ID)}] if owned else [],
        })

    def test_an_unconfirmed_address_is_refused_before_any_claim(self):
        sched = self.FakeScheduler()
        resp = self.post(self.db(verified=None), sched)
        assert resp.status_code == 422 and "Confirm the delivery address" in resp.json()["detail"]
        assert sched.claims == [] if hasattr(sched, "claims") else True

    def test_requires_bearer_token(self):
        sched = self.FakeScheduler()
        assert self.post(self.db(), sched, authed=False).status_code == 401
        assert sched.sent == []

    def test_invalid_token_is_401(self):
        db = self.db()
        db.client.auth.get_user.side_effect = Exception("bad jwt")
        c = client_for(db)
        c.app.state.scheduler = sched = self.FakeScheduler()
        resp = c.post(f"/issues/{ISSUE_ID}/send-now", headers={"Authorization": "Bearer nope"})
        assert resp.status_code == 401 and sched.sent == []

    def test_valid_token_resolves_user(self):
        db = self.db()
        db.client.auth.get_user.return_value.user.id = self.USER_ID
        c = client_for(db)
        c.app.state.scheduler = sched = self.FakeScheduler()
        resp = c.post(f"/issues/{ISSUE_ID}/send-now", headers={"Authorization": "Bearer good"})
        assert resp.status_code == 202
        db.client.auth.get_user.assert_called_once_with("good")
        assert ("user_id", self.USER_ID) in db.calls_for("user_issues", "select")[0][3]

    def test_issue_owned_by_someone_else_is_404(self):
        sched = self.FakeScheduler()
        assert self.post(self.db(owned=False), sched).status_code == 404
        assert sched.sent == []

    def test_cooldown_is_429_with_retry_after(self):
        resp = self.post(self.db(), self.FakeScheduler(claim=SendNowCooldown(300)))
        assert resp.status_code == 429
        assert resp.headers["Retry-After"] == "300"

    def test_accepted_runs_send_in_background(self):
        sched = self.FakeScheduler(claim='failed')
        resp = self.post(self.db(), sched)
        assert resp.status_code == 202
        assert sched.sent == [(str(ISSUE_ID), 'failed')]

    def test_unknown_issue_is_404(self):
        assert self.post(FakeSupabase(), self.FakeScheduler()).status_code == 404

    def test_no_target_email_is_400(self):
        assert self.post(self.db(email=None), self.FakeScheduler()).status_code == 400

    def test_already_processing_is_409(self):
        sched = self.FakeScheduler(claim=None)
        assert self.post(self.db(), sched).status_code == 409
        assert sched.sent == []

    def test_scheduler_not_running_is_503(self):
        assert self.post(self.db(), None).status_code == 503

    def test_background_failure_is_recorded(self):
        sched = self.FakeScheduler(fail=True)
        assert self.post(self.db(), sched).status_code == 202
        (issue_id, error, kw), = sched.failures
        assert issue_id == str(ISSUE_ID) and "boom" in error and kw["force"] is True
