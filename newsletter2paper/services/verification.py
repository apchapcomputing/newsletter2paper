"""Recipient verification: prove the owner of a delivery address agreed to receive newspapers there.

An issue's address is verified when it is the owner's account address (Supabase Auth checked it) or
when someone opened a link we emailed to it and pressed confirm. Tokens are random, single-use,
expire after 24 hours and are stored only as SHA-256 hashes. The link opens a page; only the
button on that page confirms, so a mail scanner that prefetches the link cannot verify an address.
"""
import hashlib
import secrets
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Optional

TOKEN_TTL = timedelta(hours=24)
# Each request sends an email to an address nobody has vouched for. The caps (3 per issue, 3 per
# address, 10 per account, each per hour) are enforced inside the database function
# issue_email_verification, atomically with the insert.


class RateLimited(Exception):
    pass


def normalize(email: Optional[str]) -> str:
    return (email or '').strip().lower()


def hash_token(token: str) -> str:
    return hashlib.sha256(token.encode()).hexdigest()


def account_email(db_service, user_id: Optional[str]) -> Optional[str]:
    """The signed-in owner's Supabase Auth email, or None when it cannot be determined."""
    if not user_id:
        return None
    try:
        email = db_service.client.auth.admin.get_user_by_id(user_id).user.email
    except Exception:
        return None
    return email if isinstance(email, str) else None


def is_account_email(db_service, user_id: Optional[str], email: Optional[str]) -> bool:
    mine = normalize(account_email(db_service, user_id))
    return bool(mine) and mine == normalize(email)


def issue_token(db_service, issue_id: str, email: str, user_id: Optional[str] = None,
                now: Optional[datetime] = None) -> str:
    """Create a verification token for `email` on the issue; raises RateLimited when the issue, the
    address or the account has asked for too many confirmation emails in the last hour."""
    now = now or datetime.now(timezone.utc)
    token = secrets.token_urlsafe(32)
    issued = db_service.client.rpc('issue_email_verification', {
        'p_issue_id': issue_id,
        'p_email': email,
        'p_user_id': user_id,
        'p_token_hash': hash_token(token),
        'p_expires_at': (now + TOKEN_TTL).isoformat(),
    }).execute()
    if issued.data is not True:
        raise RateLimited()
    return token


@dataclass(frozen=True)
class Outcome:
    ok: bool
    title: Optional[str] = None
    issue_id: Optional[str] = None
    reason: Optional[str] = None  # why it failed, in words safe to show the visitor


INVALID = "This confirmation link is invalid or has expired. Request a new one from the newspaper's settings."
CHANGED = "The address on this newspaper has changed since this email was sent. Request a new confirmation link."


def peek(db_service, token: str, now: Optional[datetime] = None) -> Outcome:
    """Is the token usable? Does not consume it."""
    now = now or datetime.now(timezone.utc)
    row = _find(db_service, token)
    if not row or row.get('consumed_at') or _expired(row, now):
        return Outcome(False, reason=INVALID)
    issue = _issue(db_service, row['issue_id'])
    if not issue or normalize(issue.get('target_email')) != normalize(row['email']):
        return Outcome(False, reason=CHANGED)
    return Outcome(True, title=issue.get('title'), issue_id=str(issue['id']))


def confirm(db_service, token: str, now: Optional[datetime] = None) -> Outcome:
    """Consume the token and mark the issue's address verified."""
    now = now or datetime.now(timezone.utc)
    # Single use: only one caller can flip consumed_at from NULL.
    consumed = db_service.client.table('email_verifications')\
        .update({'consumed_at': now.isoformat()})\
        .eq('token_hash', hash_token(token)).is_('consumed_at', 'null').gte('expires_at', now.isoformat())\
        .execute()
    if not consumed.data:
        return Outcome(False, reason=INVALID)
    row = consumed.data[0]
    issue = _issue(db_service, row['issue_id'])
    if not issue or normalize(issue.get('target_email')) != normalize(row['email']):
        return Outcome(False, reason=CHANGED)
    # Conditional on the address still matching, so a change after the check above wins.
    updated = db_service.client.table('issues')\
        .update({'target_email_verified_at': now.isoformat()})\
        .eq('id', str(issue['id'])).eq('target_email', issue['target_email']).execute()
    if not updated.data:
        return Outcome(False, reason=CHANGED)
    return Outcome(True, title=issue.get('title'), issue_id=str(issue['id']))


def _find(db_service, token: str) -> Optional[dict]:
    result = db_service.client.table('email_verifications').select('*')\
        .eq('token_hash', hash_token(token)).execute()
    return result.data[0] if result.data else None


def _issue(db_service, issue_id) -> Optional[dict]:
    result = db_service.client.table('issues').select('id, title, target_email').eq('id', str(issue_id)).execute()
    return result.data[0] if result.data else None


def _expired(row: dict, now: datetime) -> bool:
    expires = row.get('expires_at')
    if not expires:
        return True
    if isinstance(expires, str):
        expires = datetime.fromisoformat(expires.replace('Z', '+00:00'))
    return expires <= now
