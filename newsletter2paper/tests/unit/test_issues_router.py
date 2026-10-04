"""HTTP contract of /issues, including request validation and send-now."""
from uuid import uuid4

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from routers import issues
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
