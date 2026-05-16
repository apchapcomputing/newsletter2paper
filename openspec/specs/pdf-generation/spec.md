# PDF Generation Specification

## Purpose

Orchestrating the full pipeline that converts an issue's articles into a downloadable PDF,
using the Go PDF service via Docker exec and uploading the result to Supabase Storage.

---

## Requirements

### Requirement: End-to-End PDF Generation

The system SHALL generate a PDF for an issue by fetching its articles, invoking the Go PDF service,
and uploading the result to Supabase Storage.

#### Scenario: Successful generation returns a download URL

- GIVEN a valid issue with at least one linked publication that has recent articles
- WHEN the client sends `POST /pdf/generate/{issue_id}`
- THEN the system fetches articles, generates a PDF, uploads it, and returns a public `pdf_url`

#### Scenario: No articles found aborts generation

- GIVEN an issue where all linked publications have no articles in the requested time window
- WHEN PDF generation is triggered
- THEN the system returns an error indicating no articles were found

---

### Requirement: Layout Selection

The system SHALL use the issue's stored `format` value to select the PDF template, with an optional override.

#### Scenario: Layout from database used by default

- GIVEN an issue with `format: "essay"` and no `layout_type` query param provided
- WHEN PDF generation is triggered
- THEN the essay template is used

#### Scenario: Query param overrides database format

- GIVEN an issue with `format: "newspaper"` and `layout_type: "essay"` in the query
- WHEN PDF generation is triggered
- THEN the essay template is used regardless of the stored format

---

### Requirement: Date Window Resolution

The system SHALL resolve the article date window using a priority order.

#### Scenario: Explicit query params take highest priority

- GIVEN `start_date` and `end_date` are provided as query params
- WHEN PDF generation is triggered
- THEN those dates are used for article fetching, regardless of the issue's frequency or saved custom dates

#### Scenario: Saved custom dates used when frequency is "custom" and no params given

- GIVEN an issue with `frequency: "custom"` and stored `custom_start_date`/`custom_end_date`
- AND no explicit `start_date`/`end_date` query params are provided
- WHEN PDF generation is triggered
- THEN the stored custom dates are used

#### Scenario: Rolling days_back used as fallback

- GIVEN no explicit date params and frequency is not "custom"
- WHEN PDF generation is triggered
- THEN articles from the last `days_back` days (default: 7) are fetched

#### Scenario: start_date after end_date returns 422

- GIVEN `start_date: "2026-03-10"` and `end_date: "2026-03-01"`
- WHEN PDF generation is triggered
- THEN a 422 error is returned with a message that start_date must be before end_date

---

### Requirement: Per-Publication Image Removal

The system SHALL strip images from articles belonging to publications where `remove_images` is true.

#### Scenario: Images stripped per publication

- GIVEN an issue where publication A has `remove_images: true` and publication B has `remove_images: false`
- WHEN the PDF is generated
- THEN articles from publication A contain no images
- AND articles from publication B retain their images

#### Scenario: Global remove_images override

- GIVEN `remove_images: true` is passed as a query param
- WHEN the PDF is generated
- THEN all articles from all publications have images removed, regardless of per-publication settings

---

### Requirement: Temporary File Cleanup

The system SHALL always clean up temporary files in `/shared/` after PDF generation, whether successful or not.

#### Scenario: Files cleaned up on success

- GIVEN a PDF is generated successfully
- WHEN the upload to Supabase completes
- THEN `/shared/articles_{uuid}.json` and `/shared/output_{uuid}.pdf` are deleted

#### Scenario: Files cleaned up on failure

- GIVEN PDF generation fails (e.g., Go service error)
- WHEN the error is handled
- THEN any temporary files that were created are still deleted

---

### Requirement: HTML Debug Preservation

The system SHALL optionally preserve the intermediate HTML file for debugging.

#### Scenario: keep_html flag preserves HTML

- GIVEN `keep_html: true` is passed as a query param
- WHEN the PDF is generated
- THEN the intermediate HTML file remains in `/shared/` and is not deleted

---

### Requirement: Generation Timeout

The system SHALL time out PDF generation if the Go service does not respond within 120 seconds.

#### Scenario: Timeout returns error

- GIVEN the Go PDF service does not complete within 120 seconds
- WHEN the timeout is reached
- THEN the request fails with an error indicating the timeout was exceeded
- AND temporary files are cleaned up

---

### Requirement: PDF Download Redirect

The system SHALL provide an endpoint that redirects to the most recently generated PDF's storage URL.

#### Scenario: Redirect to latest PDF

- GIVEN a PDF has previously been generated for an issue
- WHEN the client sends `GET /pdf/download/{issue_id}`
- THEN the client is redirected (302) to the Supabase storage URL

#### Scenario: No PDF exists returns 404

- GIVEN no PDF has been generated for the requested issue
- WHEN the client sends `GET /pdf/download/{issue_id}`
- THEN a 404 response is returned

---

### Requirement: Two Layout Templates

The system SHALL support exactly two PDF layout templates.

#### Scenario: Newspaper layout — multi-column

- GIVEN `layout_type: "newspaper"`
- WHEN the PDF is generated
- THEN the output uses a multi-column masonry layout with article headers and a table of contents

#### Scenario: Essay layout — single column

- GIVEN `layout_type: "essay"`
- WHEN the PDF is generated
- THEN the output uses a single-column reading format suitable for long-form content
