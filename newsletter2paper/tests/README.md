# Enhanced RSS Service Tests

This directory contains comprehensive unit tests for all the RSS service enhancements made to the newsletter2paper backend.

## Test Files Overview

### 1. `test_rss_service_enhanced.py`
Tests for core RSS service enhancements including:

**TestEnhancedFeedDiscovery**

- Enhanced feed URL discovery with HEAD requests
- Content-type detection for RSS/Atom feeds
- Common feed path testing (`/feed`, `/rss.xml`, etc.)
- HTML parsing for `<link rel="alternate">` tags
- Error handling and fallback mechanisms

**TestRSSParsingUtilities**

- RSS/Atom content validation
- Feed metadata extraction (title, description, item count)
- Enhanced date parsing (RFC 2822, ISO formats)
- Malformed content handling

**TestDateFilteringUtilities**

- Article filtering by date ranges
- Period parsing (`last-week`, `last-month`, custom ranges)
- Date range calculation and validation
- Invalid period handling

### 2. `test_rss_service_content.py`
Tests for enhanced content extraction and utility methods:

**TestEnhancedContentExtraction**

- CDATA content handling in RSS feeds
- Multiple content source fallbacks (description → summary → content:encoded)
- Atom feed parsing and content extraction
- Enhanced author extraction from multiple fields
- Timezone-aware date processing
- Article pagination functionality

**TestUtilityMethods**

- RSS feed content fetching with validation
- Multi-feed article aggregation
- Error handling in feed processing
- Date filtering integration

**TestIssueArticleFetching**

- Enhanced `fetch_recent_articles_for_issue` method
- Custom parameter handling (days_back, max_articles_per_publication)
- Database integration with publications
- Error handling for missing issues/publications

### 3. `test_articles_router.py`
Tests for the new articles API router:

**TestArticlesRouter**

- POST `/articles/fetch/{issue_id}` endpoint
- Query parameter validation (days_back, max_articles_per_publication)
- Error responses (404 for missing issues, 500 for server errors)
- UUID validation for issue IDs
- Empty result handling

**TestArticlesRouterIntegration**

- Complete integration flow testing
- Multi-publication article fetching
- Response format validation
- Database service integration

## Test Coverage

The tests cover all new functionality added to the RSS service:

### ✅ Feed Discovery Enhancements

- HEAD request optimization
- Content-type checking
- Common path fallbacks
- HTML link tag parsing

### ✅ RSS Parsing Improvements

- CDATA content extraction
- Multiple content source handling
- Enhanced date parsing
- Better error handling

### ✅ Date Filtering Utilities

- Flexible date range support
- Period-based filtering
- Custom date range parsing

### ✅ Content Extraction Enhancements

- Namespace-aware XML parsing
- Fallback content sources
- Author field extraction
- Timezone handling

### ✅ New Utility Methods

- Multi-feed processing
- Content validation
- Integration with database service

### ✅ API Router Integration

- RESTful endpoint testing
- Parameter validation
- Error response handling
- Integration testing

## Running the Tests

### Run All Enhanced Tests

```bash
cd /path/to/newsletter2paper/newsletter2paper
python tests/run_enhanced_tests.py
```

### Run Specific Test Class

```bash
python tests/run_enhanced_tests.py TestEnhancedFeedDiscovery
python tests/run_enhanced_tests.py TestArticlesRouter
```

### Run Individual Test Files

```bash
python -m pytest tests/test_rss_service_enhanced.py -v
python -m pytest tests/test_rss_service_content.py -v  
python -m pytest tests/test_articles_router.py -v
```

### Run with Coverage

```bash
python -m pytest tests/test_rss_service_enhanced.py --cov=services.rss_service --cov-report=html
```

## Mock Objects and Test Data

The tests use comprehensive mocking to avoid external dependencies:

- **MockResponse**: Simulates HTTP responses for RSS feeds
- **Mock Database**: Mocks Supabase database operations
- **Sample RSS/Atom**: Realistic feed content for testing
- **Async Mocking**: Proper async method mocking for database operations

## Test Scenarios Covered

### Happy Path Testing

- Successful feed discovery and parsing
- Multi-publication article fetching
- Date filtering and pagination
- API endpoint success responses

### Error Handling

- Network errors and timeouts
- Malformed RSS/XML content
- Missing database records
- Invalid parameters and UUIDs

### Edge Cases

- Empty feeds and missing content
- CDATA and namespace handling
- Timezone edge cases
- Large dataset processing

### Integration Testing

- End-to-end API flows
- Database service integration
- Multi-component interaction testing

## Test Quality Features

- **Comprehensive Coverage**: Tests all new methods and enhancements
- **Realistic Data**: Uses actual RSS/Atom feed structures
- **Async Support**: Proper async testing with AsyncMock
- **Error Scenarios**: Extensive error condition testing
- **Integration Tests**: End-to-end workflow validation
- **Performance Testing**: Large dataset handling
- **Parameterized Tests**: Multiple input validation

## Dependencies

The tests require:

- `unittest` (Python standard library)
- `unittest.mock` for mocking
- `fastapi.testclient` for API testing
- `requests` for HTTP mocking
- Project modules (`services.rss_service`, `routers.articles`, etc.)

## Notes

- Tests are designed to run without external network calls
- All database operations are mocked
- RSS feed content is simulated with realistic XML
- Async methods are properly tested with AsyncMock
- Error conditions are thoroughly validated
