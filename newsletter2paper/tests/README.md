# Backend tests

Run from `newsletter2paper/`:

```bash
pip install -r requirements.txt pytest pytest-asyncio
pytest                      # everything; no network or Supabase needed
pytest tests/unit/test_go_pdf_service.py::TestExecuteGoCli   # one class
```

`tests/conftest.py` points `SUPABASE_URL` at an unroutable address, so a test that forgets to
inject a fake fails fast instead of touching a real project.

## Layout

| Path | What it covers |
|---|---|
| `unit/test_date_params.py` | ISO date parsing and window resolution shared by the articles/pdf routers |
| `unit/test_articles_router.py`, `unit/test_issues_router.py` | HTTP contract: validation, status codes (404 stays 404), what gets written to Supabase |
| `unit/test_fetch_recent_articles.py` | Which articles make it into an issue: window, inclusive end date, per-publication cap, `remove_images` inheritance, failure isolation |
| `unit/test_go_pdf_service.py` | The FastAPI → Go seam: JSON contract, CLI flags, timeouts, temp-file cleanup |
| `test_feed_extraction.py`, `test_rss_service_content.py`, `test_rss_service_enhanced.py` | Feed parsing, discovery, date utilities (fixture: `fixtures/substack_feed.xml`) |
| `test_email_service.py` | Resend wrapper and its wiring into `/pdf/generate` |

## Writing tests here

- Test behaviour a user or another service relies on, not that a constructor stores its arguments.
- `unit/conftest.py` has `FakeSupabase`, which records `(table, op, payload, filters)` so you can
  assert on what would be written. Prefer it over chained `MagicMock` return values.
- `RSSService._rss_cache` is class-level; clear it in `setUp` when a test fetches a feed URL.
- Async tests: use `pytest.mark.asyncio` (pytest style) or `unittest.IsolatedAsyncioTestCase`.
  A plain `unittest.TestCase` with `async def` tests is **silently never awaited**.
