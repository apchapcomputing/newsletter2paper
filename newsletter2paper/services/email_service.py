import html
import logging
from dataclasses import dataclass
from typing import Dict, List, Mapping, Optional, Tuple, Union

import httpx
import resend
from resend.http_client import HTTPClient

from config.settings import RESEND_API_KEY, EMAIL_FROM

logger = logging.getLogger(__name__)

# Seconds before a Resend request counts as a (transient) timeout.
RESEND_TIMEOUT_SECONDS = 30
TRANSIENT, PERMANENT = 'transient', 'permanent'


@dataclass(frozen=True)
class SendResult:
    """Outcome of one send attempt.

    `error` is user-readable and prefixed `email:` (the provider refused or failed) or `config:`
    (our setup is wrong). `retry_after` is Resend's Retry-After in seconds, when it sent one.
    `outcome_unknown` means no response arrived (timeout, network error), so Resend may have
    accepted the email: a retry must reuse the same idempotency key.
    """
    ok: bool
    message_id: Optional[str] = None
    error_kind: Optional[str] = None
    error: Optional[str] = None
    retry_after: Optional[int] = None
    outcome_unknown: bool = False

    @classmethod
    def sent(cls, message_id: Optional[str]) -> "SendResult":
        return cls(ok=True, message_id=message_id)

    @classmethod
    def failed(cls, error_kind: str, error: str, retry_after: Optional[int] = None,
               outcome_unknown: bool = False) -> "SendResult":
        return cls(ok=False, error_kind=error_kind, error=error, retry_after=retry_after,
                   outcome_unknown=outcome_unknown)


def classify_resend_error(exc: Exception) -> SendResult:
    """Map a Resend SDK error to a SendResult.

    transient: 429, 5xx, network errors and timeouts (the SDK reports those as 500), and 409
    concurrent_idempotent_requests (the same key is still being processed). permanent: any other
    4xx, e.g. an invalid address or an unverified sending domain.
    """
    if not isinstance(exc, resend.exceptions.ResendError):
        return SendResult.failed(TRANSIENT, f"email: unexpected error sending via Resend ({exc})",
                                 outcome_unknown=True)
    try:
        code = int(exc.code)
    except (TypeError, ValueError):
        code = 500
    message = exc.message or exc.error_type or 'no details'
    if code == 429:
        return SendResult.failed(TRANSIENT, f"email: Resend rate limit reached ({message})",
                                 retry_after=_retry_after(exc.headers))
    if code >= 500:
        if exc.error_type == 'HttpClientError':
            return SendResult.failed(TRANSIENT, f"email: could not reach Resend ({message})", outcome_unknown=True)
        return SendResult.failed(TRANSIENT, f"email: Resend is unavailable ({code}: {message})")
    if code == 409 and exc.error_type == 'concurrent_idempotent_requests':
        return SendResult.failed(TRANSIENT, "email: Resend is still processing an identical request")
    # 403 also covers an unverified sending domain; only a key problem is our configuration.
    if code == 401 or exc.error_type == 'invalid_api_key':
        return SendResult.failed(PERMANENT, f"config: Resend rejected the API key ({message})")
    return SendResult.failed(PERMANENT, f"email: Resend rejected the message ({code}: {message})")


def _retry_after(headers: Optional[Mapping[str, str]]) -> Optional[int]:
    value = {k.lower(): v for k, v in (headers or {}).items()}.get('retry-after')
    try:
        return max(0, int(float(value))) if value is not None else None
    except ValueError:
        return None  # HTTP-date form; fall back to our own backoff


class _HttpxClient(HTTPClient):
    """Synchronous Resend transport on httpx, with an explicit timeout.

    The SDK's default transport uses requests; httpx lets tests mock the real Resend API with
    respx. Request errors (including timeouts) surface as ResendError code 500 'HttpClientError'.
    """

    def __init__(self, timeout: float = RESEND_TIMEOUT_SECONDS):
        self._timeout = timeout

    def request(
        self,
        method: str,
        url: str,
        headers: Mapping[str, str],
        json: Optional[Union[Dict[str, object], List[object]]] = None,
    ) -> Tuple[bytes, int, Mapping[str, str]]:
        try:
            resp = httpx.request(method, url, headers=headers, json=json, timeout=self._timeout)
        except httpx.RequestError as e:
            raise RuntimeError(f"Request failed: {type(e).__name__}: {e}") from e
        return resp.content, resp.status_code, dict(resp.headers)


class EmailService:
    """Service for sending emails via the Resend API."""

    def __init__(self) -> None:
        # Configuration problems are reported per send as permanent `config:` failures, so
        # callers get a result instead of an exception.
        if RESEND_API_KEY:
            resend.api_key = RESEND_API_KEY
        resend.default_http_client = _HttpxClient()

    def send(
        self,
        email_address: Optional[str],
        pdf_url: str,
        subject: Optional[str] = None,
        issue_title: Optional[str] = None,
        idempotency_key: Optional[str] = None,
    ) -> SendResult:
        """
        Send an email containing a link to a generated PDF.

        Parameters:
        -----------
        email_address : str
            Recipient email address.
        pdf_url : str
            Signed URL pointing to the generated PDF in Supabase storage.
        subject : str, optional
            Email subject line. Defaults to a sensible newsletter title.
        issue_title : str, optional
            Human-readable issue title shown in the email body.
        idempotency_key : str, optional
            Resend treats repeated requests with the same key (within 24h) as one email,
            so a retry after a crash cannot deliver twice.

        Returns:
        --------
        SendResult
            `ok` with the Resend message id, or the classified failure. Never raises.
        """
        email_address = (email_address or '').strip()
        if not email_address:
            return SendResult.failed(PERMANENT, "config: no recipient email address is set")
        if not RESEND_API_KEY:
            return SendResult.failed(PERMANENT, "config: RESEND_API_KEY is not set")
        if not EMAIL_FROM:
            return SendResult.failed(PERMANENT, "config: EMAIL_FROM is not set")

        display_title = issue_title or "Your newsletter"
        params: resend.Emails.SendParams = {
            "from": EMAIL_FROM,
            "to": [email_address],
            "subject": subject or "Your newsletter PDF is ready",
            "html": self._build_html(pdf_url=pdf_url, issue_title=display_title),
            "text": self._build_text(pdf_url=pdf_url, issue_title=display_title),
        }
        options: resend.Emails.SendOptions = {}
        if idempotency_key:
            options["idempotency_key"] = idempotency_key

        try:
            response = resend.Emails.send(params, options)
        except Exception as exc:  # noqa: BLE001 - classified, never propagated
            result = classify_resend_error(exc)
            logger.error("Failed to send email to %s: %s (%s)", email_address, result.error, result.error_kind)
            return result
        message_id = response.get("id")
        logger.info("Email sent to %s (Resend id: %s)", email_address, message_id)
        return SendResult.sent(message_id)

    def send_pdf(
        self,
        email_address: str,
        pdf_url: str,
        subject: Optional[str] = None,
        issue_title: Optional[str] = None,
    ) -> bool:
        """Boolean wrapper around `send`, kept for existing callers."""
        return self.send(email_address, pdf_url, subject, issue_title).ok

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    def _build_html(self, pdf_url: str, issue_title: str) -> str:
        """Return a minimal HTML email body with a prominent download link.

        Every interpolated value is escaped: the title is user-controlled."""
        issue_title = html.escape(issue_title)
        pdf_url = html.escape(pdf_url, quote=True)
        return f"""
        <!DOCTYPE html>
        <html lang="en">
        <head>
          <meta charset="UTF-8">
          <meta name="viewport" content="width=device-width, initial-scale=1.0">
          <title>Your newsletter PDF</title>
          <style>
            body {{ font-family: Georgia, serif; background: #f5f5f0;
                   color: #222; margin: 0; padding: 0; }}
            .container {{ max-width: 600px; margin: 40px auto;
                          background: #fff; border-radius: 4px;
                          padding: 40px; }}
            h1 {{ font-size: 22px; margin-bottom: 8px; }}
            p {{ line-height: 1.6; color: #444; }}
            .btn {{ display: inline-block; margin-top: 24px;
                   padding: 14px 28px; background: #111;
                   color: #fff; text-decoration: none;
                   border-radius: 3px; font-size: 15px; }}
            .footer {{ margin-top: 40px; font-size: 12px; color: #999; }}
          </style>
        </head>
        <body>
          <div class="container">
            <h1>&#128240; {issue_title}</h1>
            <p>Your newsletter PDF has been generated and is ready to read.</p>
            <p>The link is valid for <strong>30&nbsp;days</strong>.</p>
            <a class="btn" href="{pdf_url}">Download PDF</a>
            <p class="footer">You received this because you set up email
              delivery in Newsletter2Paper.</p>
          </div>
        </body>
        </html>
        """

    def _build_text(
        self, pdf_url: str, issue_title: str
    ) -> str:
        """Return a plain-text fallback email body."""
        return (
            f"{issue_title}\n\n"
            "Your newsletter PDF is ready.\n\n"
            f"Download: {pdf_url}\n\n"
            "This link is valid for 30 days.\n"
        )
