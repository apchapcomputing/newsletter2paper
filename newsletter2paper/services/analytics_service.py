"""PostHog for the backend: product events and error tracking.

Every function is a no-op without POSTHOG_API_KEY (local runs, tests) and never raises, so an
analytics outage can't break a request or a scheduled run. Event names are object_action
snake_case, matching ui/lib/analytics.js, and the same PII-prone properties are dropped: never
send email addresses, article text, feed URLs or issue titles.
"""
import logging
import os
from typing import Optional, Tuple

logger = logging.getLogger(__name__)

BLOCKED_PROPS = frozenset({'email', 'target_email', 'recipient', 'url', 'feed_url', 'title', 'query', 'html', 'error'})
DEFAULT_HOST = 'https://eu.i.posthog.com'

_client = None
_initialised = False


def _get_client():
    global _client, _initialised
    if not _initialised:
        _initialised = True
        key = os.environ.get('POSTHOG_API_KEY')
        if key:
            try:
                from posthog import Posthog
                _client = Posthog(
                    key,
                    host=os.environ.get('POSTHOG_HOST', DEFAULT_HOST),
                    # Uncaught exceptions (including in scheduler threads) go to Error tracking too.
                    enable_exception_autocapture=True,
                )
            except Exception:
                logger.exception("PostHog client could not be created; analytics is off")
    return _client


def enabled() -> bool:
    return _get_client() is not None


def _clean(properties: Optional[dict]) -> dict:
    return {k: v for k, v in (properties or {}).items() if k not in BLOCKED_PROPS and v is not None}


def capture(event: str, distinct_id: str, properties: Optional[dict] = None) -> None:
    client = _get_client()
    if client is None:
        return
    try:
        client.capture(event, distinct_id=str(distinct_id), properties=_clean(properties))
    except Exception:
        logger.exception(f"Could not send analytics event {event}")


def capture_exception(exc: BaseException, distinct_id: Optional[str] = None, properties: Optional[dict] = None) -> None:
    """Send a caught exception to Error tracking. distinct_id is the browser's
    (X-POSTHOG-DISTINCT-ID) or the issue owner's, when known."""
    client = _get_client()
    if client is None:
        return
    try:
        client.capture_exception(exc, distinct_id=distinct_id or None, properties=_clean(properties))
    except Exception:
        logger.exception("Could not send exception to PostHog")


def request_context(request, **properties) -> Tuple[Optional[str], dict]:
    """(distinct_id, properties) for a request: the browser's PostHog ids, which the Next.js API
    routes forward (tracing_headers in ui/lib/analytics.js), plus the route."""
    return request.headers.get('x-posthog-distinct-id'), {
        '$session_id': request.headers.get('x-posthog-session-id'),
        'path': request.url.path,
        'method': request.method,
        **properties,
    }


def shutdown() -> None:
    """Flush queued events; called when the app stops."""
    if _client is not None:
        try:
            _client.shutdown()
        except Exception:
            logger.exception("Could not flush PostHog events")


def reset_for_tests() -> None:
    global _client, _initialised
    _client, _initialised = None, False
