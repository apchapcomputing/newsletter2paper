import logging
from typing import Optional

import resend

from config.settings import RESEND_API_KEY, EMAIL_FROM

logger = logging.getLogger(__name__)


class EmailService:
    """Service for sending emails via the Resend API."""

    def __init__(self) -> None:
        """Initialise the Resend client with the configured API key."""
        if not RESEND_API_KEY:
            raise ValueError(
                "RESEND_API_KEY environment variable is not set. "
                "Please add it to your .env file."
            )
        resend.api_key = RESEND_API_KEY

    def send_pdf(
        self,
        email_address: str,
        pdf_url: str,
        subject: Optional[str] = None,
        issue_title: Optional[str] = None,
    ) -> bool:
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

        Returns:
        --------
        bool
            True if the email was sent successfully, False otherwise.
        """
        if not email_address:
            logger.warning("send_pdf called with no email address – skipping.")
            return False

        resolved_subject = subject or f"Your newsletter PDF is ready"
        display_title = issue_title or "Your newsletter"

        html_body = self._build_html(
            pdf_url=pdf_url, issue_title=display_title
        )
        text_body = self._build_text(
            pdf_url=pdf_url, issue_title=display_title
        )

        try:
            params: resend.Emails.SendParams = {
                "from": EMAIL_FROM,
                "to": [email_address],
                "subject": resolved_subject,
                "html": html_body,
                "text": text_body,
            }
            response = resend.Emails.send(params)
            logger.info(
                "Email sent to %s (Resend id: %s)",
                email_address,
                response.get("id"),
            )
            return True
        except Exception as exc:  # noqa: BLE001
            logger.error(
                "Failed to send email to %s: %s", email_address, exc
            )
            return False

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    def _build_html(self, pdf_url: str, issue_title: str) -> str:
        """Return a minimal HTML email body with a prominent download link."""
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
