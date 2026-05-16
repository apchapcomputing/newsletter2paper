# Issues Specification

## Purpose

An issue is a user-configured newsletter compilation — it groups publications together with
layout and scheduling preferences, and is the primary unit used to generate PDFs.

---

## Requirements

### Requirement: Issue Creation

The system SHALL allow creating an issue with a title, format, and frequency.

#### Scenario: Successful creation with preset frequency

- GIVEN a valid request with `format: "newspaper"` and `frequency: "weekly"`
- WHEN the client sends `POST /issues/`
- THEN an issue is created and returned with a generated ID and default title "Your Newspaper"

#### Scenario: Custom frequency requires date range

- GIVEN a request with `frequency: "custom"` but missing `custom_start_date` or `custom_end_date`
- WHEN the client sends `POST /issues/`
- THEN a 422 validation error is returned

#### Scenario: Invalid date order rejected

- GIVEN a request with `custom_start_date` after `custom_end_date`
- WHEN the client sends `POST /issues/`
- THEN a 422 error is returned indicating start must be before end

---

### Requirement: Issue Update

The system SHALL allow partially updating an issue's title, format, frequency, and date range.

#### Scenario: Switching from custom to preset frequency clears saved dates

- GIVEN an issue with `frequency: "custom"` and stored custom dates
- WHEN the client sends `PUT /issues/{id}` with `frequency: "weekly"`
- THEN `custom_start_date` and `custom_end_date` are cleared from the database

#### Scenario: Updating title only

- GIVEN an existing issue
- WHEN the client sends `PUT /issues/{id}` with only a new title
- THEN only the title is updated; all other fields remain unchanged

---

### Requirement: Issue Retrieval

The system SHALL return a full issue record including its associated publications.

#### Scenario: Issue with publications returned

- GIVEN an issue with three linked publications exists
- WHEN the client sends `GET /issues/{id}`
- THEN the response includes the issue data and an array of its publications with per-publication settings

#### Scenario: Issue not found

- GIVEN no issue exists with the requested ID
- WHEN the client sends `GET /issues/{id}`
- THEN a 404 response is returned

---

### Requirement: Publication Association

The system SHALL allow adding publications to an issue with optional per-publication settings.

#### Scenario: Adding publications with remove_images settings

- GIVEN an issue and two publications
- WHEN the client sends `POST /issues/{id}/publications` with a `publications` array including `remove_images` flags
- THEN each publication is linked to the issue with the specified settings stored in `issue_publications`

#### Scenario: Legacy publication_ids format accepted

- GIVEN a client using the deprecated `publication_ids` array format
- WHEN the client sends `POST /issues/{id}/publications`
- THEN the publications are added with default `remove_images: false`

---

### Requirement: Publication Removal

The system SHALL allow removing a publication from an issue.

#### Scenario: Publication removed

- GIVEN a publication linked to an issue
- WHEN the client sends `DELETE /issues/{id}/publications/{publication_id}`
- THEN the `issue_publications` record is deleted and the publication is no longer listed for that issue

---

### Requirement: Per-Publication Settings Update

The system SHALL allow updating per-publication settings (e.g., `remove_images`) within an issue.

#### Scenario: Image removal toggled for one publication

- GIVEN a publication linked to an issue with `remove_images: false`
- WHEN the client sends `PATCH /issues/{id}/publications/{publication_id}` with `remove_images: true`
- THEN only that publication's `remove_images` flag is updated; other publications are unaffected

---

### Requirement: Frequency Modes

The system SHALL support five frequency values: `daily`, `weekly`, `monthly`, `once`, and `custom`.

#### Scenario: Invalid frequency rejected

- GIVEN a request with `frequency: "biweekly"`
- WHEN the client sends `POST /issues/` or `PUT /issues/{id}`
- THEN a 422 validation error is returned listing the valid options

---

### Requirement: Format Values

The system SHALL support exactly two format values: `newspaper` and `essay`.

#### Scenario: Invalid format rejected

- GIVEN a request with `format: "magazine"`
- WHEN the client sends `POST /issues/`
- THEN a 422 validation error is returned
