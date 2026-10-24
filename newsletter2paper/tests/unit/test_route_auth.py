"""Every route that reads or changes an issue needs the owner's token or the guest token.

Uses the real auth dependencies against a fake Supabase; a request without credentials is
401, and credentials that don't match the issue are 404 (so IDs can't be probed).
"""
from unittest.mock import AsyncMock, MagicMock
from uuid import UUID, uuid4

import pytest
from fastapi import Depends, FastAPI
from fastapi.testclient import TestClient

from routers import articles, issues, pdf
from services import auth
from tests.unit.conftest import FakeSupabase

ISSUE_ID = str(uuid4())
USER_ID = str(uuid4())
OWNER = {"Authorization": "Bearer good"}
GUEST_TOKEN = "guest_" + "a" * 36
GUEST = {"x-guest-token": GUEST_TOKEN}

# (method, path, json body) for every owner-or-guest route
PROTECTED = [
    ("GET", f"/issues/{ISSUE_ID}", None),
    ("PUT", f"/issues/{ISSUE_ID}", {"title": "x"}),
    ("DELETE", f"/issues/{ISSUE_ID}", None),
    ("POST", f"/issues/{ISSUE_ID}/publications", {"publication_ids": []}),
    ("GET", f"/issues/{ISSUE_ID}/publications", None),
    ("POST", f"/articles/fetch/{ISSUE_ID}", None),
    ("GET", f"/articles/issue/{ISSUE_ID}/summary", None),
    ("POST", f"/pdf/generate/{ISSUE_ID}", None),
    ("GET", f"/pdf/download/{ISSUE_ID}", None),
    ("GET", f"/pdf/status/{ISSUE_ID}", None),
]


def make_db(owned=False, guest_row=None, issue_row=None):
    responses = {
        ("user_issues", "select"): [{"issue_id": ISSUE_ID}] if owned else [],
        ("issues", "select"): [guest_row] if guest_row else ([issue_row] if issue_row else []),
        ("issues", "update"): [{"id": ISSUE_ID}],
        ("issue_publications", "select"): [],
    }
    db = FakeSupabase(responses)
    db.client.auth.get_user.return_value.user.id = USER_ID
    return db


def make_client(db):
    app = FastAPI()
    for r in (issues.router, articles.router, pdf.router):
        app.include_router(r)
    app.dependency_overrides[issues.get_db_service] = lambda: db
    return TestClient(app, raise_server_exceptions=False)


def call(client, method, path, body, headers=None):
    return client.request(method, path, json=body, headers=headers or {})


@pytest.mark.parametrize("method,path,body", PROTECTED)
class TestProtectedRoutes:
    def test_no_credentials_is_401(self, method, path, body):
        assert call(make_client(make_db(owned=True)), method, path, body).status_code == 401

    def test_invalid_bearer_token_is_401(self, method, path, body):
        db = make_db(owned=True)
        db.client.auth.get_user.side_effect = Exception("bad jwt")
        assert call(make_client(db), method, path, body, OWNER).status_code == 401

    def test_other_users_issue_is_404(self, method, path, body):
        assert call(make_client(make_db(owned=False)), method, path, body, OWNER).status_code == 404

    def test_wrong_guest_token_is_404(self, method, path, body):
        row = {"status": "guest", "guest_token": "other"}
        assert call(make_client(make_db(guest_row=row)), method, path, body, GUEST).status_code == 404

    def test_guest_token_on_a_claimed_issue_is_404(self, method, path, body):
        row = {"status": "draft", "guest_token": GUEST_TOKEN}
        assert call(make_client(make_db(guest_row=row)), method, path, body, GUEST).status_code == 404

    def test_issue_without_a_guest_token_never_matches(self, method, path, body):
        row = {"status": "guest", "guest_token": None}
        assert call(make_client(make_db(guest_row=row)), method, path, body, GUEST).status_code == 404


class TestAccessDependency:
    def probe(self, db):
        app = FastAPI()
        app.dependency_overrides[auth.get_db_service] = lambda: db

        @app.get("/probe/{issue_id}")
        def probe(issue_id: UUID, access: auth.IssueAccess = Depends(auth.require_issue_access)):
            return {"owner": access.is_owner, "user_id": access.user_id}

        @app.get("/owner-only/{issue_id}")
        def owner_only(issue_id: UUID, access: auth.IssueAccess = Depends(auth.require_issue_owner)):
            return {"user_id": access.user_id}

        return TestClient(app)

    def test_owner_is_let_in(self):
        resp = self.probe(make_db(owned=True)).get(f"/probe/{ISSUE_ID}", headers=OWNER)
        assert resp.json() == {"owner": True, "user_id": USER_ID}

    def test_guest_token_holder_is_let_in_but_is_not_an_owner(self):
        row = {"status": "guest", "guest_token": GUEST_TOKEN}
        resp = self.probe(make_db(guest_row=row)).get(f"/probe/{ISSUE_ID}", headers=GUEST)
        assert resp.json() == {"owner": False, "user_id": None}

    def test_owner_wins_when_both_credentials_are_sent(self):
        resp = self.probe(make_db(owned=True)).get(f"/probe/{ISSUE_ID}", headers={**OWNER, **GUEST})
        assert resp.json()["owner"] is True

    def test_guest_token_works_alongside_a_stale_bearer_for_another_user(self):
        row = {"status": "guest", "guest_token": GUEST_TOKEN}
        resp = self.probe(make_db(owned=False, guest_row=row)).get(f"/probe/{ISSUE_ID}", headers={**OWNER, **GUEST})
        assert resp.json()["owner"] is False

    def test_guest_token_works_alongside_an_expired_bearer(self):
        row = {"status": "guest", "guest_token": GUEST_TOKEN}
        db = make_db(guest_row=row)
        db.client.auth.get_user.side_effect = Exception("expired")
        resp = self.probe(db).get(f"/probe/{ISSUE_ID}", headers={**OWNER, **GUEST})
        assert resp.status_code == 200
        assert resp.json()["owner"] is False

    def test_expired_bearer_alone_is_still_401(self):
        db = make_db(owned=True)
        db.client.auth.get_user.side_effect = Exception("expired")
        assert self.probe(db).get(f"/probe/{ISSUE_ID}", headers=OWNER).status_code == 401

    def test_owner_only_rejects_guests(self):
        row = {"status": "guest", "guest_token": GUEST_TOKEN}
        c = self.probe(make_db(guest_row=row))
        assert c.get(f"/owner-only/{ISSUE_ID}", headers=GUEST).status_code == 401
        assert c.get(f"/owner-only/{ISSUE_ID}", headers=OWNER).status_code == 404


class TestGuestAccess:
    ROW = {"id": ISSUE_ID, "status": "guest", "guest_token": GUEST_TOKEN, "title": "T"}

    def test_guest_token_reads_the_issue_without_leaking_it(self):
        resp = call(make_client(make_db(guest_row=self.ROW)), "GET", f"/issues/{ISSUE_ID}", None, GUEST)
        assert resp.status_code == 200
        assert "guest_token" not in resp.json()["issue"]

    @pytest.mark.parametrize("body", [{"target_email": "victim@example.com"}, {"auto_send": True}])
    def test_guest_cannot_set_a_recipient_or_auto_send_on_update(self, body):
        db = make_db(guest_row=self.ROW)
        resp = call(make_client(db), "PUT", f"/issues/{ISSUE_ID}", body, GUEST)
        assert resp.status_code == 403
        assert db.calls_for("issues", "update") == []

    def test_guest_can_still_edit_other_fields_and_clear_the_email(self):
        resp = call(make_client(make_db(guest_row=self.ROW)), "PUT", f"/issues/{ISSUE_ID}",
                    {"title": "New", "target_email": ""}, GUEST)
        assert resp.status_code == 200

    def test_owner_can_set_a_recipient(self):
        db = make_db(owned=True, issue_row={"id": ISSUE_ID})
        resp = call(make_client(db), "PUT", f"/issues/{ISSUE_ID}", {"target_email": "me@example.com"}, OWNER)
        assert resp.status_code == 200


class TestCreate:
    def test_no_credentials_is_401(self):
        assert call(make_client(make_db()), "POST", "/issues/", {"format": "essay"}).status_code == 401

    @pytest.mark.parametrize("extra", [{"target_email": "victim@example.com"},
                                       {"target_email": "a@b.co", "auto_send": True}])
    def test_guest_cannot_create_an_issue_with_a_recipient(self, extra):
        db = make_db()
        resp = call(make_client(db), "POST", "/issues/", {"format": "essay", **extra}, GUEST)
        assert resp.status_code == 403
        assert db.calls_for("issues", "insert") == []

    def test_short_guest_token_is_rejected(self):
        db = make_db()
        resp = call(make_client(db), "POST", "/issues/", {"format": "essay"}, {"x-guest-token": "s3cret"})
        assert resp.status_code == 422
        assert db.calls_for("issues", "insert") == []

    def test_guest_issue_is_stored_as_guest_with_its_token(self):
        db = make_db()
        db.responses[("issues", "insert")] = [{"id": ISSUE_ID, "guest_token": GUEST_TOKEN}]
        resp = call(make_client(db), "POST", "/issues/", {"format": "essay"}, GUEST)
        assert resp.status_code == 200
        (_, _, payload, _), = db.calls_for("issues", "insert")
        assert (payload["status"], payload["guest_token"], payload["target_email"]) == ("guest", GUEST_TOKEN, None)
        assert db.calls_for("user_issues", "insert") == []
        assert "guest_token" not in resp.json()["issue"]


class TestPdfEmail:
    """/pdf/generate emails the link only to the signed-in owner."""

    @pytest.fixture
    def stubs(self, monkeypatch):
        import services.database_service as dbs
        import services.email_service as email
        import services.rss_service as rss

        issue = {"id": ISSUE_ID, "title": "T", "format": "essay", "target_email": "victim@example.com", "target_email_verified_at": "2026-10-01T00:00:00Z",
                 "status": "guest", "guest_token": GUEST_TOKEN}
        db = make_db(guest_row=issue, owned=False)
        monkeypatch.setattr(dbs, "DatabaseService", lambda: db)
        fake_rss = MagicMock()
        fake_rss.fetch_recent_articles_for_issue = AsyncMock(return_value={
            "total_articles": 1, "issue": issue, "articles_by_publication": {"p": [{"title": "a"}]}})
        monkeypatch.setattr(rss, "RSSService", lambda: fake_rss)
        monkeypatch.setattr(pdf.pdf_service, "generate_pdf_from_issue", AsyncMock(return_value={
            "success": True, "pdf_url": "https://x/y.pdf", "issue_info": issue, "articles_count": 1}))
        sender = MagicMock()
        sender.send.return_value = MagicMock(ok=True)
        monkeypatch.setattr(email, "EmailService", lambda: sender)
        return db, sender

    def test_guest_generation_sends_no_email(self, stubs):
        db, sender = stubs
        resp = call(make_client(db), "POST", f"/pdf/generate/{ISSUE_ID}", None, GUEST)
        assert resp.status_code == 200
        sender.send.assert_not_called()
        assert "email_sent" not in resp.json()
        assert "guest_token" not in resp.json()["issue_info"]

    def test_owner_generation_emails_the_target(self, stubs):
        db, sender = stubs
        db.responses[("user_issues", "select")] = [{"issue_id": ISSUE_ID}]
        resp = call(make_client(db), "POST", f"/pdf/generate/{ISSUE_ID}", None, OWNER)
        assert resp.status_code == 200
        sender.send.assert_called_once()
        assert sender.send.call_args.kwargs["email_address"] == "victim@example.com"


class TestAdminRoutes:
    ROUTES = [("GET", "/pdf/test-storage"), ("DELETE", "/pdf/cleanup"), ("GET", "/pdf/memory/stats")]

    @pytest.mark.parametrize("method,path", ROUTES)
    def test_disabled_without_a_configured_token(self, method, path, monkeypatch):
        monkeypatch.delenv("ADMIN_API_TOKEN", raising=False)
        assert call(make_client(make_db()), method, path, None, {"x-admin-token": "anything"}).status_code == 404

    @pytest.mark.parametrize("method,path", ROUTES)
    def test_wrong_or_missing_token_is_401(self, method, path, monkeypatch):
        monkeypatch.setenv("ADMIN_API_TOKEN", "admin-secret")
        c = make_client(make_db())
        assert call(c, method, path, None).status_code == 401
        assert call(c, method, path, None, {"x-admin-token": "nope"}).status_code == 401

    def test_correct_token_is_let_in(self, monkeypatch):
        monkeypatch.setenv("ADMIN_API_TOKEN", "admin-secret")
        monkeypatch.setattr(pdf.pdf_service, "test_connection", lambda: {"success": True})
        resp = call(make_client(make_db()), "GET", "/pdf/memory/stats", None, {"x-admin-token": "admin-secret"})
        assert resp.status_code == 200

    @pytest.mark.parametrize("path", ["/pdf/memory/cleanup", "/pdf/memory/cache"])
    def test_noop_memory_routes_are_gone(self, path):
        c = make_client(make_db())
        assert c.post(path).status_code in (404, 405) and c.delete(path).status_code in (404, 405)
