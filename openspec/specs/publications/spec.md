# Publications Specification

## Purpose

Management of Substack (and other RSS-based) publication records that users can add to their issues.
A publication is a shared, global resource — any user can reference any publication.

---

## Requirements

### Requirement: Publication Discovery via URL

The system SHALL automatically discover the RSS feed URL from a given publication homepage URL.

#### Scenario: Substack feed discovery

- GIVEN a user provides a Substack homepage URL (e.g. `https://kyla.substack.com`)
- WHEN the system calls `GET /rss/url?webpage_url=<url>`
- THEN the system returns the RSS feed URL (e.g. `https://kyla.substack.com/feed`)

#### Scenario: No RSS feed found

- GIVEN a URL that has no discoverable RSS feed
- WHEN the system calls `GET /rss/url?webpage_url=<url>`
- THEN a 404 response is returned with a descriptive error message

---

### Requirement: Publication Registration

The system SHALL allow registering a new publication by providing its title, URL, RSS feed URL, and publisher.

#### Scenario: Successful registration

- GIVEN a valid publication payload with title, url, rss_feed_url, and publisher
- WHEN the client sends `POST /publications/`
- THEN the publication is stored and returned with a generated ID

#### Scenario: Duplicate URL rejected

- GIVEN a publication URL that already exists in the database
- WHEN the client sends `POST /publications/` with that URL
- THEN a 400 error is returned indicating the URL already exists

---

### Requirement: Publication Search

The system SHALL allow searching publications by title or publisher name using a case-insensitive partial match.

#### Scenario: Matching results returned

- GIVEN publications exist with titles containing "Kyla"
- WHEN the client sends `GET /publications/?search=kyla`
- THEN only publications whose title or publisher contains "kyla" are returned

#### Scenario: No search term — all publications returned

- GIVEN multiple publications exist
- WHEN the client sends `GET /publications/` with no search param
- THEN all publications are returned

---

### Requirement: Publication Retrieval by ID

The system SHALL return a single publication record by its ID.

#### Scenario: Publication found

- GIVEN a publication with a known ID exists
- WHEN the client sends `GET /publications/{id}`
- THEN the full publication record is returned

#### Scenario: Publication not found

- GIVEN no publication exists with the requested ID
- WHEN the client sends `GET /publications/{id}`
- THEN a 404 response is returned

---

### Requirement: Deduplication

The system SHALL prevent the same publication URL from being registered more than once.

#### Scenario: Exact URL match rejected

- GIVEN a publication with URL `https://example.substack.com` already exists
- WHEN the client attempts to register a new publication with the same URL
- THEN the system returns a 400 error and does not create a duplicate record
