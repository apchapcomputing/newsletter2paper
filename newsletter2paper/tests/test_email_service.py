"""Unit tests for the EmailService (Resend integration)."""

import pytest
from unittest.mock import MagicMock, patch


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

PDF_URL = "https://storage.example.com/newsletters/issue-123.pdf"
ISSUE_ID = "11111111-2222-4333-8444-555555555555"
EMAIL = "reader@example.com"
ISSUE_TITLE = "Morning Digest"


def _make_service():
    """Return an EmailService with a mocked Resend API key."""
    with patch.dict("os.environ", {"RESEND_API_KEY": "re_test_key", "EMAIL_FROM": "test@example.com"}):
        # Re-import settings so the patched env is picked up
        import importlib
        import config.settings as settings_mod
        importlib.reload(settings_mod)

        import services.email_service as email_mod
        importlib.reload(email_mod)

        return email_mod.EmailService()


# ---------------------------------------------------------------------------
# Construction tests
# ---------------------------------------------------------------------------


class TestEmailServiceInit:
    """Tests for EmailService initialisation."""

    def test_missing_api_key_is_a_permanent_config_failure(self):
        """Without RESEND_API_KEY, sends fail permanently with a config: error and no request."""
        with patch.dict("os.environ", {}, clear=True):
            import importlib
            import config.settings as settings_mod
            importlib.reload(settings_mod)
            import services.email_service as email_mod
            importlib.reload(email_mod)

            with patch("resend.Emails.send") as mock_send:
                result = email_mod.EmailService().send(EMAIL, PDF_URL)
            assert not result.ok and result.error_kind == "permanent"
            assert result.error == "config: RESEND_API_KEY is not set"
            mock_send.assert_not_called()

    def test_initialises_successfully_with_api_key(self):
        """EmailService constructs without error when RESEND_API_KEY is present."""
        service = _make_service()
        assert service is not None


# ---------------------------------------------------------------------------
# send_pdf tests
# ---------------------------------------------------------------------------


class TestSendPdf:
    """Tests for EmailService.send_pdf."""

    def test_returns_true_on_success(self):
        """send_pdf returns True when Resend accepts the request."""
        service = _make_service()
        mock_response = {"id": "abc-123"}

        with patch("resend.Emails.send", return_value=mock_response) as mock_send:
            result = service.send_pdf(
                email_address=EMAIL,
                pdf_url=PDF_URL,
                subject="Your PDF is ready",
                issue_title=ISSUE_TITLE,
            )

        assert result is True
        mock_send.assert_called_once()

    def test_send_uses_correct_recipient(self):
        """send_pdf passes the correct 'to' address to Resend."""
        service = _make_service()

        with patch("resend.Emails.send", return_value={"id": "x"}) as mock_send:
            service.send_pdf(email_address=EMAIL, pdf_url=PDF_URL)

        params = mock_send.call_args[0][0]
        assert params["to"] == [EMAIL]

    def test_send_includes_pdf_url_in_html(self):
        """The generated HTML body contains the PDF URL."""
        service = _make_service()

        with patch("resend.Emails.send", return_value={"id": "x"}) as mock_send:
            service.send_pdf(email_address=EMAIL, pdf_url=PDF_URL, issue_title=ISSUE_TITLE)

        params = mock_send.call_args[0][0]
        assert PDF_URL in params["html"]
        assert PDF_URL in params["text"]

    def test_send_includes_issue_title(self):
        """The generated HTML body contains the issue title."""
        service = _make_service()

        with patch("resend.Emails.send", return_value={"id": "x"}) as mock_send:
            service.send_pdf(email_address=EMAIL, pdf_url=PDF_URL, issue_title=ISSUE_TITLE)

        params = mock_send.call_args[0][0]
        assert ISSUE_TITLE in params["html"]
        assert ISSUE_TITLE in params["text"]

    def test_default_subject_when_none_provided(self):
        """send_pdf uses a sensible default subject when none is given."""
        service = _make_service()

        with patch("resend.Emails.send", return_value={"id": "x"}) as mock_send:
            service.send_pdf(email_address=EMAIL, pdf_url=PDF_URL)

        params = mock_send.call_args[0][0]
        assert params["subject"]  # Non-empty string

    def test_returns_false_on_resend_error(self):
        """send_pdf returns False (and does not raise) when Resend throws."""
        service = _make_service()

        with patch("resend.Emails.send", side_effect=Exception("rate limited")):
            result = service.send_pdf(email_address=EMAIL, pdf_url=PDF_URL)

        assert result is False

    def test_returns_false_for_empty_email(self):
        """send_pdf returns False immediately when email_address is empty."""
        service = _make_service()

        with patch("resend.Emails.send") as mock_send:
            result = service.send_pdf(email_address="", pdf_url=PDF_URL)

        assert result is False
        mock_send.assert_not_called()


# ---------------------------------------------------------------------------
# PDF router integration: email wiring
# ---------------------------------------------------------------------------


class TestPdfRouterEmailWiring:
    """Tests that the PDF router calls EmailService when target_email is set."""

    @pytest.fixture()
    def mock_issue_with_email(self):
        return {
            "id": "issue-abc",
            "title": ISSUE_TITLE,
            "format": "newspaper",
            "frequency": "weekly",
            "remove_images": False,
            "target_email": EMAIL,
            "target_email_verified_at": "2026-10-01T00:00:00Z",
            "custom_start_date": None,
            "custom_end_date": None,
        }

    @pytest.fixture()
    def mock_issue_without_email(self, mock_issue_with_email):
        issue = dict(mock_issue_with_email)
        issue["target_email"] = None
        return issue

    def _build_articles_data(self, issue: dict) -> dict:
        return {
            "issue": issue,
            "articles_by_publication": {
                "pub-1": [
                    {
                        "id": "art-1",
                        "title": "Test Article",
                        "content_url": "https://example.com/art-1",
                        "remove_images": False,
                    }
                ]
            },
            "total_articles": 1,
        }

    def _make_mock_db(self, issue_data):
        """Return a mock DatabaseService class whose instances return issue_data."""
        mock_instance = MagicMock()
        (
            mock_instance.client
            .table.return_value
            .select.return_value
            .eq.return_value
            .execute.return_value
            .data
        ) = [issue_data]
        mock_class = MagicMock(return_value=mock_instance)
        return mock_class

    @staticmethod
    def _sign_in_as_owner(app):
        """These tests cover email wiring, not auth (see tests/unit/test_route_auth.py)."""
        from services.auth import IssueAccess, require_issue_access
        app.dependency_overrides[require_issue_access] = lambda: IssueAccess(ISSUE_ID, "user-1")

    def test_email_sent_when_target_email_set(self, mock_issue_with_email):
        """PDF router sends email when issue has a target_email."""
        from fastapi.testclient import TestClient
        from fastapi import FastAPI
        from unittest.mock import AsyncMock, patch as _patch

        app = FastAPI()

        with _patch.dict("os.environ", {"RESEND_API_KEY": "re_test", "EMAIL_FROM": "n@example.com"}):
            import importlib, config.settings as sm, services.email_service as em
            importlib.reload(sm); importlib.reload(em)
            from routers import pdf as pdf_mod
            importlib.reload(pdf_mod)
            app.include_router(pdf_mod.router)
            self._sign_in_as_owner(app)

        mock_pdf_result = {
            "success": True,
            "pdf_url": PDF_URL,
            "issue_info": mock_issue_with_email,
            "articles_count": 1,
            "layout_type": "newspaper",
        }
        articles_data = self._build_articles_data(mock_issue_with_email)

        with (
            _patch("services.rss_service.RSSService.fetch_recent_articles_for_issue", new=AsyncMock(return_value=articles_data)),
            _patch("services.database_service.DatabaseService", new=self._make_mock_db(mock_issue_with_email)),
            _patch("services.go_pdf_service.GoPDFService.generate_pdf_from_issue", new=AsyncMock(return_value=mock_pdf_result)),
            _patch("services.email_service.EmailService.send", return_value=em.SendResult.sent("msg-1")) as mock_email,
        ):
            client = TestClient(app)
            response = client.post(f"/pdf/generate/{ISSUE_ID}")

        assert response.status_code == 200
        data = response.json()
        assert data["email_sent"] is True
        mock_email.assert_called_once()

    def test_email_not_sent_to_an_unconfirmed_address(self, mock_issue_with_email):
        """On-demand generation still returns the PDF, but only a confirmed address is emailed."""
        from fastapi.testclient import TestClient
        from fastapi import FastAPI
        from unittest.mock import AsyncMock, patch as _patch
        import importlib, services.email_service as em
        from routers import pdf as pdf_mod
        importlib.reload(pdf_mod)
        app = FastAPI()
        app.include_router(pdf_mod.router)
        self._sign_in_as_owner(app)
        issue = {**mock_issue_with_email, "target_email_verified_at": None}
        result = {"success": True, "pdf_url": PDF_URL, "issue_info": issue, "articles_count": 1, "layout_type": "newspaper"}
        with (
            _patch("services.rss_service.RSSService.fetch_recent_articles_for_issue", new=AsyncMock(return_value=self._build_articles_data(issue))),
            _patch("services.database_service.DatabaseService", new=self._make_mock_db(issue)),
            _patch("services.go_pdf_service.GoPDFService.generate_pdf_from_issue", new=AsyncMock(return_value=result)),
            _patch("services.email_service.EmailService.send", return_value=em.SendResult.sent("m")) as mock_email,
        ):
            data = TestClient(app).post(f"/pdf/generate/{ISSUE_ID}").json()
        assert data["success"] is True and data["pdf_url"] == PDF_URL
        assert data["email_sent"] is False and "not been confirmed" in data["email_error"]
        mock_email.assert_not_called()

    def test_email_not_sent_when_no_target_email(self, mock_issue_without_email):
        """PDF router skips email when issue has no target_email."""
        from fastapi.testclient import TestClient
        from fastapi import FastAPI
        from unittest.mock import AsyncMock, patch as _patch

        app = FastAPI()

        with _patch.dict("os.environ", {"RESEND_API_KEY": "re_test", "EMAIL_FROM": "n@example.com"}):
            import importlib, config.settings as sm, services.email_service as em
            importlib.reload(sm); importlib.reload(em)
            from routers import pdf as pdf_mod
            importlib.reload(pdf_mod)
            app.include_router(pdf_mod.router)
            self._sign_in_as_owner(app)

        mock_pdf_result = {
            "success": True,
            "pdf_url": PDF_URL,
            "issue_info": mock_issue_without_email,
            "articles_count": 1,
            "layout_type": "newspaper",
        }
        articles_data = self._build_articles_data(mock_issue_without_email)

        with (
            _patch("services.rss_service.RSSService.fetch_recent_articles_for_issue", new=AsyncMock(return_value=articles_data)),
            _patch("services.database_service.DatabaseService", new=self._make_mock_db(mock_issue_without_email)),
            _patch("services.go_pdf_service.GoPDFService.generate_pdf_from_issue", new=AsyncMock(return_value=mock_pdf_result)),
            _patch("services.email_service.EmailService.send", return_value=em.SendResult.sent("msg-1")) as mock_email,
        ):
            client = TestClient(app)
            response = client.post(f"/pdf/generate/{ISSUE_ID}")

        assert response.status_code == 200
        data = response.json()
        assert "email_sent" not in data
        mock_email.assert_not_called()

    def test_email_failure_reports_cause_and_pdf_still_succeeds(self, mock_issue_with_email):
        """A failed send is reported with its cause; the PDF response is still a success."""
        from fastapi.testclient import TestClient
        from fastapi import FastAPI
        from unittest.mock import AsyncMock, patch as _patch

        app = FastAPI()
        import importlib, services.email_service as em
        from routers import pdf as pdf_mod
        importlib.reload(pdf_mod)
        app.include_router(pdf_mod.router)
        self._sign_in_as_owner(app)

        mock_pdf_result = {"success": True, "pdf_url": PDF_URL, "issue_info": mock_issue_with_email,
                           "articles_count": 1, "layout_type": "newspaper"}
        failed = em.SendResult.failed("permanent", "email: Resend rejected the message (422: Invalid `to` field.)")
        with (
            _patch("services.rss_service.RSSService.fetch_recent_articles_for_issue",
                   new=AsyncMock(return_value=self._build_articles_data(mock_issue_with_email))),
            _patch("services.database_service.DatabaseService", new=self._make_mock_db(mock_issue_with_email)),
            _patch("services.go_pdf_service.GoPDFService.generate_pdf_from_issue", new=AsyncMock(return_value=mock_pdf_result)),
            _patch("services.email_service.EmailService.send", return_value=failed),
        ):
            data = TestClient(app).post(f"/pdf/generate/{ISSUE_ID}").json()

        assert data["success"] is True and data["email_sent"] is False
        assert data["email_error"] == failed.error and data["email_error_kind"] == "permanent"
        assert "email_recipient" not in data
