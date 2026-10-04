"""RSSService.fetch_recent_articles_for_issue decides which articles get printed.

Scenarios follow openspec/specs/articles: rolling window, explicit range with an
inclusive end date, per-publication cap, remove_images inheritance, and isolation
of one broken feed from the rest.
"""
from datetime import datetime, timedelta, timezone
from unittest.mock import AsyncMock
from uuid import uuid4

import pytest

from models import Article
from services.rss_service import RSSService
from tests.unit.conftest import FakeSupabase

UTC = timezone.utc
NOW = datetime.now(UTC)


def article(title, published):
    return Article(id=uuid4(), title=title, subtitle=None, author="A", content_url=f"https://e.com/{title}",
                   date_published=published)


def link(pub_id, feed="https://e.com/{id}/feed", remove_images=False, title=None):
    return {"remove_images": remove_images,
            "publications": {"id": pub_id, "title": title or f"Pub {pub_id}", "publisher": f"Publisher {pub_id}",
                             "rss_feed_url": feed.format(id=pub_id) if feed else None}}


def make_service(links, feeds):
    """feeds: {feed_url: [Article,...] | Exception}"""
    service = RSSService()
    service.db = FakeSupabase({("issues", "select"): [{"id": "issue-1", "title": "T"}],
                               ("issue_publications", "select"): links})

    async def get_articles(url, skip=0, limit=10):
        result = feeds[url]
        if isinstance(result, Exception):
            raise result
        return result[skip:skip + limit], len(result)

    service.get_articles = AsyncMock(side_effect=get_articles)
    return service


@pytest.mark.asyncio
class TestWindow:
    async def test_rolling_window_excludes_older_articles(self):
        feed = [article("new", NOW - timedelta(days=1)), article("edge-in", NOW - timedelta(days=6, hours=23)),
                article("old", NOW - timedelta(days=8))]
        service = make_service([link("p1")], {"https://e.com/p1/feed": feed})

        result = await service.fetch_recent_articles_for_issue("issue-1", days_back=7)

        assert [a["title"] for a in result["articles_by_publication"]["p1"]] == ["new", "edge-in"]
        assert result["total_articles"] == 2
        assert result["date_range"]["custom"] is False and result["date_range"]["days_back"] == 7

    async def test_explicit_range_overrides_days_back_and_end_date_is_inclusive_for_the_whole_day(self):
        feed = [article("late-on-end-day", datetime(2026, 3, 7, 18, 30, tzinfo=UTC)),
                article("start-day-morning", datetime(2026, 3, 1, 0, 5, tzinfo=UTC)),
                article("after", datetime(2026, 3, 8, 0, 1, tzinfo=UTC)),
                article("before", datetime(2026, 2, 28, 23, 59, tzinfo=UTC))]
        service = make_service([link("p1")], {"https://e.com/p1/feed": feed})

        result = await service.fetch_recent_articles_for_issue(
            "issue-1", days_back=1,
            start_date=datetime(2026, 3, 1, tzinfo=UTC), end_date=datetime(2026, 3, 7, tzinfo=UTC))

        titles = [a["title"] for a in result["articles_by_publication"]["p1"]]
        assert titles == ["late-on-end-day", "start-day-morning"]
        assert result["date_range"]["custom"] is True and result["date_range"]["days_back"] is None

    async def test_start_after_end_is_rejected(self):
        service = make_service([link("p1")], {"https://e.com/p1/feed": []})
        with pytest.raises(ValueError, match="before end_date"):
            await service.fetch_recent_articles_for_issue(
                "issue-1", start_date=datetime(2026, 3, 7, tzinfo=UTC), end_date=datetime(2026, 3, 1, tzinfo=UTC))

    async def test_start_after_end_is_rejected_even_when_the_issue_has_no_publications(self):
        service = make_service([], {})
        with pytest.raises(ValueError, match="before end_date"):
            await service.fetch_recent_articles_for_issue(
                "issue-1", start_date=datetime(2026, 3, 7, tzinfo=UTC), end_date=datetime(2026, 3, 1, tzinfo=UTC))


@pytest.mark.asyncio
class TestPerPublication:
    async def test_cap_keeps_the_first_n_in_feed_order_and_reads_extra_to_survive_filtering(self):
        feed = [article(f"a{i}", NOW - timedelta(hours=i + 1)) for i in range(8)]
        service = make_service([link("p1")], {"https://e.com/p1/feed": feed})

        result = await service.fetch_recent_articles_for_issue("issue-1", max_articles_per_publication=3)

        assert [a["title"] for a in result["articles_by_publication"]["p1"]] == ["a0", "a1", "a2"]
        assert service.get_articles.await_args.kwargs["limit"] == 6  # 2x so old items skipped by the date filter don't starve the cap

    async def test_articles_carry_publication_metadata_and_that_publications_remove_images_flag(self):
        links = [link("p1", remove_images=True), link("p2", remove_images=False)]
        feeds = {"https://e.com/p1/feed": [article("x", NOW)], "https://e.com/p2/feed": [article("y", NOW)]}
        service = make_service(links, feeds)

        result = await service.fetch_recent_articles_for_issue("issue-1")

        (x,), (y,) = result["articles_by_publication"]["p1"], result["articles_by_publication"]["p2"]
        assert x["remove_images"] is True and y["remove_images"] is False
        assert (x["publication_title"], x["publication_publisher"], x["publication_id"]) == ("Pub p1", "Publisher p1", "p1")

    async def test_one_failing_feed_does_not_lose_the_others(self):
        feeds = {"https://e.com/p1/feed": RuntimeError("feed host down"), "https://e.com/p2/feed": [article("ok", NOW)]}
        service = make_service([link("p1"), link("p2")], feeds)

        result = await service.fetch_recent_articles_for_issue("issue-1")

        assert result["articles_by_publication"]["p1"] == []
        assert [a["title"] for a in result["articles_by_publication"]["p2"]] == ["ok"]
        assert result["total_articles"] == 1

    async def test_publication_without_a_feed_url_is_empty_not_an_error(self):
        service = make_service([link("p1", feed=None)], {})

        result = await service.fetch_recent_articles_for_issue("issue-1")

        assert result["articles_by_publication"] == {"p1": []}
        service.get_articles.assert_not_awaited()

    async def test_dangling_junction_rows_are_ignored(self):
        service = make_service([{"remove_images": False, "publications": None}, link("p1")],
                               {"https://e.com/p1/feed": [article("ok", NOW)]})

        result = await service.fetch_recent_articles_for_issue("issue-1")

        assert [p["id"] for p in result["publications"]] == ["p1"]

    async def test_publication_filter_is_applied_to_the_query(self):
        service = make_service([link("p1")], {"https://e.com/p1/feed": []})

        await service.fetch_recent_articles_for_issue("issue-1", publication_id="p1")

        filters = service.db.calls_for("issue_publications", "select")[0][3]
        assert ("issue_id", "issue-1") in filters and ("publication_id", "p1") in filters


@pytest.mark.asyncio
class TestIssueLookup:
    async def test_unknown_issue_raises_value_error(self):
        service = RSSService()
        service.db = FakeSupabase()
        with pytest.raises(ValueError, match="Issue not found"):
            await service.fetch_recent_articles_for_issue("missing")

    async def test_issue_without_publications_returns_an_empty_but_well_formed_result(self):
        result = await make_service([], {}).fetch_recent_articles_for_issue("issue-1")
        assert result["total_articles"] == 0 and result["publications"] == [] and result["articles_by_publication"] == {}
        assert {"from", "to", "days_back", "custom"} <= set(result["date_range"])
