# Article Fetching Specification

## Purpose

Fetching articles from RSS feeds for the publications linked to an issue, with support for
time-window filtering, pagination, and per-publication scoping.

---

## Requirements

### Requirement: RSS Article Fetch with Time Window

The system SHALL fetch articles published within a specified time window from an issue's publications.

#### Scenario: Rolling days_back window

- GIVEN an issue with two publications
- WHEN the client sends `POST /articles/fetch/{issue_id}` with `days_back: 7`
- THEN articles published within the last 7 days are returned, grouped by publication

#### Scenario: Explicit date range overrides days_back

- GIVEN `start_date: "2026-03-01"` and `end_date: "2026-03-07"` are provided as query params
- WHEN the client sends `POST /articles/fetch/{issue_id}`
- THEN only articles published between 2026-03-01 00:00:00 UTC and 2026-03-07 23:59:59 UTC are returned
- AND `days_back` is ignored

#### Scenario: end_date treated as end-of-day UTC

- GIVEN `end_date: "2026-03-07"` is provided
- WHEN the system filters articles
- THEN articles published on 2026-03-07 up to 23:59:59 UTC are included

#### Scenario: Invalid date order returns 422

- GIVEN `start_date: "2026-03-07"` and `end_date: "2026-03-01"` (start after end)
- WHEN the client sends the request
- THEN a 422 error is returned with a message that start_date must be before end_date

---

### Requirement: Max Articles Per Publication

The system SHALL limit the number of articles returned per publication.

#### Scenario: Default limit applied

- GIVEN an issue with a publication that has 20 recent articles
- WHEN the client sends `POST /articles/fetch/{issue_id}` with no `max_articles_per_publication`
- THEN at most 5 articles are returned for that publication (default limit)

#### Scenario: Custom limit respected

- GIVEN `max_articles_per_publication: 10` in the request body
- WHEN the client fetches articles
- THEN at most 10 articles are returned per publication

---

### Requirement: Single Publication Filter

The system SHALL allow scoping article fetching to a single publication within an issue.

#### Scenario: Publication filter applied

- GIVEN an issue with three publications and a valid `publication_id` query param
- WHEN the client sends `POST /articles/fetch/{issue_id}?publication_id=<uuid>`
- THEN only articles from that one publication are returned

---

### Requirement: Graceful Feed Failure Handling

The system SHALL continue processing remaining publications if one feed fails to fetch.

#### Scenario: One feed fails, others succeed

- GIVEN an issue with three publications where one RSS feed is unreachable
- WHEN the client triggers article fetching
- THEN articles from the two reachable publications are returned
- AND an error or warning is logged for the failed feed
- AND the response does not return a 500 error

---

### Requirement: RSS Feed Pagination

The system SHALL support paginated fetching of raw articles directly from an RSS feed URL.

#### Scenario: Paginated article list

- GIVEN `feed_url`, `skip: 5`, and `limit: 5`
- WHEN the client sends `GET /rss/articles`
- THEN articles 6–10 from the feed are returned with `has_more` indicating whether more exist

#### Scenario: Limit capped at 20

- GIVEN `limit: 50` in the request
- WHEN the client sends `GET /rss/articles`
- THEN a 422 validation error is returned (max limit is 20)

---

### Requirement: Article Summary

The system SHALL provide a lightweight article count and preview per publication for a given issue.

#### Scenario: Summary returned

- GIVEN an issue with two publications
- WHEN the client sends `GET /articles/issue/{issue_id}/summary?days_back=7`
- THEN a summary array is returned with each publication's article count and article titles/dates

---

### Requirement: remove_images Propagation

The system SHALL attach the per-publication `remove_images` flag to each fetched article.

#### Scenario: remove_images flag inherited from publication settings

- GIVEN a publication linked to an issue with `remove_images: true`
- WHEN articles are fetched for that issue
- THEN each article from that publication has `remove_images: true` in its data
