"""HTTP contract of /articles (see openspec/specs/articles)."""
from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from routers import articles


class FakeRss:
    def __init__(self, result=None, error=None):
        self.fetch_recent_articles_for_issue = AsyncMock(return_value=result, side_effect=error)


def make_client(rss=None, db=None):
    app = FastAPI()
    app.include_router(articles.router)
    app.dependency_overrides[articles.get_rss_service] = lambda: rss
    app.dependency_overrides[articles.get_db_service] = lambda: db
    return TestClient(app)


RESULT = {"issue": {"id": "i"}, "publications": [{"id": "p1"}, {"id": "p2"}],
          "articles_by_publication": {}, "total_articles": 4}


class TestFetchArticles:
    def test_defaults_are_seven_days_and_five_per_publication(self):
        rss = FakeRss(RESULT)
        issue_id = uuid4()

        resp = make_client(rss).post(f"/articles/fetch/{issue_id}")

        assert resp.status_code == 200
        kwargs = rss.fetch_recent_articles_for_issue.await_args.kwargs
        assert kwargs["issue_id"] == str(issue_id)
        assert (kwargs["days_back"], kwargs["max_articles_per_publication"]) == (7, 5)
        assert resp.json()["message"] == "Fetched 4 articles from 2 publications"

    def test_body_and_query_params_are_forwarded(self):
        rss = FakeRss(RESULT)

        make_client(rss).post(
            f"/articles/fetch/{uuid4()}?publication_id=pub-9&start_date=2026-03-01&end_date=2026-03-07",
            json={"days_back": 30, "max_articles_per_publication": 2},
        )

        kwargs = rss.fetch_recent_articles_for_issue.await_args.kwargs
        assert (kwargs["days_back"], kwargs["max_articles_per_publication"]) == (30, 2)
        assert kwargs["publication_id"] == "pub-9"
        assert kwargs["start_date"].isoformat() == "2026-03-01T00:00:00+00:00"
        assert kwargs["end_date"].isoformat() == "2026-03-07T00:00:00+00:00"

    def test_start_after_end_is_422_and_never_reaches_the_service(self):
        rss = FakeRss(RESULT)

        resp = make_client(rss).post(f"/articles/fetch/{uuid4()}?start_date=2026-03-07&end_date=2026-03-01")

        assert resp.status_code == 422
        rss.fetch_recent_articles_for_issue.assert_not_awaited()

    def test_unparseable_date_is_422(self):
        resp = make_client(FakeRss(RESULT)).post(f"/articles/fetch/{uuid4()}?start_date=soon")
        assert resp.status_code == 422

    def test_non_uuid_issue_id_is_422(self):
        assert make_client(FakeRss(RESULT)).post("/articles/fetch/not-a-uuid").status_code == 422

    def test_unknown_issue_surfaces_as_404(self):
        rss = FakeRss(error=ValueError("Issue abc not found"))
        resp = make_client(rss).post(f"/articles/fetch/{uuid4()}")
        assert resp.status_code == 404
        assert "not found" in resp.json()["detail"]

    def test_unexpected_failure_is_500(self):
        rss = FakeRss(error=RuntimeError("feed host down"))
        resp = make_client(rss).post(f"/articles/fetch/{uuid4()}")
        assert resp.status_code == 500


def fake_db(issue_rows, publication_rows=()):
    db = MagicMock()

    def table(name):
        rows = {"issues": issue_rows, "issue_publications": list(publication_rows)}[name]
        chain = MagicMock()
        chain.select.return_value = chain
        chain.eq.return_value = chain
        chain.execute.return_value = MagicMock(data=rows)
        return chain

    db.client.table.side_effect = table
    return db


class TestIssueSummary:
    def test_unknown_issue_is_404_not_500(self):
        resp = make_client(db=fake_db([])).get(f"/articles/issue/{uuid4()}/summary")
        assert resp.status_code == 404

    def test_lists_publications_and_skips_dangling_junction_rows(self):
        pubs = [
            {"publications": {"id": "p1", "title": "A", "publisher": "PA", "rss_feed_url": "u1"}},
            {"publications": None},  # junction row whose publication was deleted
        ]
        resp = make_client(db=fake_db([{"id": "i", "title": "T"}], pubs)).get(
            f"/articles/issue/{uuid4()}/summary?days_back=3"
        )

        body = resp.json()
        assert resp.status_code == 200
        assert body["publications_count"] == 1
        assert body["publications"][0]["title"] == "A"
        assert body["date_range"]["days_back"] == 3
