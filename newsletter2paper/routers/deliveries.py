"""Tracked links in delivery emails: GET /d/{delivery_id} records the open and redirects to the PDF.

The delivery id is a random UUID, so the link is as private as the signed PDF URL it replaces.
"""
import logging
from datetime import timedelta
from uuid import UUID

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import RedirectResponse

from services import analytics_service as analytics

router = APIRouter(tags=["deliveries"])

# Mail scanners (Outlook Safe Links, Gmail) fetch links within seconds of delivery.
SCANNER_WINDOW = timedelta(seconds=30)


def _store(request: Request):
    scheduler = getattr(request.app.state, 'scheduler', None)
    return scheduler.store if scheduler else None


@router.get("/d/{delivery_id}", include_in_schema=False)
def open_delivery(delivery_id: UUID, request: Request):
    store = _store(request)
    if store is None:
        raise HTTPException(status_code=503, detail="Delivery links are temporarily unavailable")
    info = store.record_open(delivery_id, SCANNER_WINDOW)
    if not info:
        raise HTTPException(status_code=404, detail="Delivery not found")

    if analytics.enabled():
        try:
            owner = store.owner_id(info['issue_id'])
        except Exception:
            logging.exception("Could not look up delivery owner for analytics")
            owner = None
        sent_at = info.get('sent_at')
        analytics.capture('edition_opened', owner or f"issue:{info['issue_id']}", {
            'issue_id': str(info['issue_id']),
            'delivery_id': str(delivery_id),
            'trigger': info.get('trigger'),
            'first_open': info['first_open'],
            'likely_scanner': info['likely_scanner'],
            'hours_since_sent': round((info['db_now'] - sent_at).total_seconds() / 3600, 1) if sent_at else None,
        })
    return RedirectResponse(info['pdf_url'], status_code=302)
