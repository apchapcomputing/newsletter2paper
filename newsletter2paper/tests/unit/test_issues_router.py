"""HTTP contract of /issues, including request validation and send-now."""
from uuid import uuid4

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from routers import issues
from services.delivery_store import Claim
from services.scheduler import SendNowCooldown
from tests.unit.conftest import FakeSupabase

ISSUE_ID = uuid4()


def client_for(db):
    app = FastAPI()
    app.include_router(issues.router)
    app.dependency_overrides[issues.get_db_service] = lambda: db
    return TestClient(app)


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
        db = FakeSupabase({("issues", "insert"): [{"id": str(ISSUE_ID)}]})

        resp = client_for(db).post("/issues/", json={"format": "newspaper"})

        assert resp.status_code == 200
        (_, _, payload, _), = db.calls_for("issues", "insert")
        assert payload["title"] == "Your Newspaper"
        assert (payload["frequency"], payload["auto_send"], payload["article_window_days"]) == ("weekly", False, 7)


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

    def db(self, email="a@b.co", owned=True):
        return FakeSupabase({
            ("issues", "select"): [{"id": str(ISSUE_ID), "target_email": email}],
            ("user_issues", "select"): [{"issue_id": str(ISSUE_ID)}] if owned else [],
        })

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
