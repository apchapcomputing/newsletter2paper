"""PostHog for the backend: product events and error tracking.

Every function is a no-op without POSTHOG_API_KEY (local runs, tests) and never raises, so an
analytics outage can't break a request or a scheduled run. Event names are object_action
snake_case, matching ui/lib/analytics.js, and the same PII-prone properties are dropped: never
send email addresses, article text, feed URLs or issue titles.
"""
import logging
import os
import re
from typing import Optional, Tuple

logger = logging.getLogger(__name__)

BLOCKED_PROPS = frozenset({'email', 'target_email', 'recipient', 'url', 'feed_url', 'title', 'query', 'html', 'error'})
DEFAULT_HOST = 'https://eu.i.posthog.com'

_EMAIL = re.compile(r'[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}')
_URL = re.compile(r'\b(?:https?|ftp)://[^\s"\'<>)\]]+', re.IGNORECASE)
# Same shape check as ui/lib/analyticsPrivacy.js: forwarded ids are client-controlled.
_DISTINCT_ID = re.compile(r'^[A-Za-z0-9-]{8,64}$')


def scrub_text(value):
    """Replace emails and URLs; exception messages can quote a feed URL or a recipient."""
    return _URL.sub('[url]', _EMAIL.sub('[email]', value)) if isinstance(value, str) else value


def _scrub_event(event):
    """before_send hook: scrub exception messages and custom string properties. Stack frames are
    kept for grouping; code variables are off (capture_exception_code_variables defaults to False)."""
    props = (event or {}).get('properties')
    if not props:
        return event
    for exc in props.get('$exception_list') or []:
        if isinstance(exc, dict):
            exc['value'] = scrub_text(exc.get('value'))
    if '$exception_message' in props:
        props['$exception_message'] = scrub_text(props['$exception_message'])
    for key, value in list(props.items()):
        if not key.startswith('$') and isinstance(value, str):
            props[key] = scrub_text(value)
    return event


def trusted_distinct_id(value) -> Optional[str]:
    """A forwarded browser id, if it looks like one; used only to attribute errors."""
    return value if isinstance(value, str) and _DISTINCT_ID.match(value) else None

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
                    before_send=_scrub_event,
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
    return trusted_distinct_id(request.headers.get('x-posthog-distinct-id')), {
        '$session_id': trusted_distinct_id(request.headers.get('x-posthog-session-id')),
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
