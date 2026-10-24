"""Public pages behind links in emails: confirm a delivery address, and unsubscribe.

Both follow the same rule: GET only shows a page, and a POST (the button, or a mail client's
RFC 8058 one-click request) does the work. Mail scanners prefetch links with GET, and a prefetch
must never confirm an address or cancel a subscription.
"""
import html
import logging
from uuid import UUID

from fastapi import APIRouter, Depends
from fastapi.responses import HTMLResponse

from services import analytics_service as analytics
from services import verification
from services.auth import get_db_service
from services.database_service import DatabaseService

router = APIRouter(tags=["email-links"], include_in_schema=False)

_PAGE = """<!DOCTYPE html>
<html lang="en"><head><meta charset="UTF-8"><meta name="viewport" content="width=device-width, initial-scale=1">
<meta name="robots" content="noindex"><title>{title}</title></head>
<body style="font-family: Georgia, serif; color: #222; background: #f5f5f0; margin: 0;">
<main style="max-width: 520px; margin: 64px auto; background: #fff; padding: 32px; border-radius: 4px;">
<h1 style="font-size: 22px; margin-top: 0;">{title}</h1>{body}</main></body></html>"""

_BUTTON = ('<form method="post" action="{action}"><button type="submit" style="padding:12px 24px;'
           'background:#111;color:#fff;border:0;border-radius:3px;font-size:15px;cursor:pointer;">{label}</button></form>')


def _page(title: str, body: str, status: int = 200) -> HTMLResponse:
    return HTMLResponse(_PAGE.format(title=html.escape(title), body=body), status_code=status,
                        headers={"Cache-Control": "no-store", "Referrer-Policy": "no-referrer"})


@router.get("/email/verify")
def show_verification(token: str = "", db_service: DatabaseService = Depends(get_db_service)):
    outcome = verification.peek(db_service, token)
    if not outcome.ok:
        return _page("Link not valid", f"<p>{html.escape(outcome.reason)}</p>", 400)
    action = html.escape(f"/email/verify?token={token}", quote=True)
    return _page("Confirm your email address",
                 f"<p>Confirm that &ldquo;{html.escape(outcome.title or 'your newspaper')}&rdquo; may be "
                 f"emailed to this address on its schedule.</p>" + _BUTTON.format(action=action, label="Confirm"))


@router.post("/email/verify")
def confirm_verification(token: str = "", db_service: DatabaseService = Depends(get_db_service)):
    outcome = verification.confirm(db_service, token)
    if not outcome.ok:
        return _page("Link not valid", f"<p>{html.escape(outcome.reason)}</p>", 400)
    if analytics.enabled():
        analytics.capture('recipient_verified', f"issue:{outcome.issue_id}", {'issue_id': outcome.issue_id})
    return _page("Address confirmed", "<p>Thanks. Scheduled newspapers can now be sent to this address.</p>")


@router.get("/u/{token}")
def show_unsubscribe(token: UUID, db_service: DatabaseService = Depends(get_db_service)):
    found = db_service.client.table('issues').select('id, title').eq('unsubscribe_token', str(token)).execute()
    if not found.data:
        return _page("Link not valid", "<p>This unsubscribe link is not valid.</p>", 404)
    title = html.escape(found.data[0].get('title') or 'this newspaper')
    return _page("Stop these emails?", f"<p>Stop automatic delivery of &ldquo;{title}&rdquo;?</p>"
                 + _BUTTON.format(action=html.escape(f"/u/{token}", quote=True), label="Unsubscribe"))


@router.post("/u/{token}")
def unsubscribe(token: UUID, db_service: DatabaseService = Depends(get_db_service)):
    """One-click unsubscribe (RFC 8058): turns automatic delivery off. The schedule's trigger
    abandons any edition still waiting, so nothing more is sent."""
    updated = db_service.client.table('issues').update({'auto_send': False})\
        .eq('unsubscribe_token', str(token)).execute()
    if not updated.data:
        return _page("Link not valid", "<p>This unsubscribe link is not valid.</p>", 404)
    issue_id = str(updated.data[0]['id'])
    logging.info("Issue %s unsubscribed via email link", issue_id)
    if analytics.enabled():
        analytics.capture('delivery_unsubscribed', f"issue:{issue_id}", {'issue_id': issue_id})
    return _page("You're unsubscribed", "<p>Automatic delivery has been turned off. No more emails will be sent.</p>")
