"""Request authentication and authorization shared by the routers.

The backend talks to Supabase with the service key, so RLS does not protect anything on
this path; every route that reads or changes an issue must resolve the caller here.

Callers are one of:
  * a signed-in user: `Authorization: Bearer <Supabase access token>`; owns an issue when
    a `user_issues` row links them to it.
  * a guest: `x-guest-token: <secret>`, matching `issues.guest_token` of an issue whose
    status is 'guest' (the same rule RLS applies to the browser's direct Supabase calls).
"""
import hmac
import os
from dataclasses import dataclass
from typing import Optional
from uuid import UUID

from fastapi import Depends, Header, HTTPException, Request

from services.database_service import DatabaseService

GUEST_TOKEN_HEADER = "x-guest-token"
ADMIN_TOKEN_HEADER = "x-admin-token"


def get_db_service():
    return DatabaseService()


def _bearer_token(request: Request) -> Optional[str]:
    scheme, _, token = request.headers.get("Authorization", "").partition(" ")
    if scheme.lower() != "bearer" or not token:
        return None
    return token


def get_current_user_id(request: Request, db_service: DatabaseService = Depends(get_db_service)) -> str:
    """Resolve the caller's Supabase user from an `Authorization: Bearer <access token>` header."""
    token = _bearer_token(request)
    if not token:
        raise HTTPException(status_code=401, detail="Sign in to continue")
    try:
        user = db_service.client.auth.get_user(token).user
    except Exception:
        user = None
    if not user:
        raise HTTPException(status_code=401, detail="Session is invalid or expired")
    return str(user.id)


@dataclass(frozen=True)
class IssueAccess:
    issue_id: str
    user_id: Optional[str] = None  # set when the caller is the signed-in owner

    @property
    def is_owner(self) -> bool:
        return self.user_id is not None


def _is_owner(db_service: DatabaseService, issue_id: str, user_id: str) -> bool:
    rows = db_service.client.table("user_issues").select("issue_id")\
        .eq("issue_id", issue_id).eq("user_id", user_id).execute()
    return bool(rows.data)


def _holds_guest_token(db_service: DatabaseService, issue_id: str, token: str) -> bool:
    rows = db_service.client.table("issues").select("status, guest_token")\
        .eq("id", issue_id).execute()
    if not rows.data:
        return False
    row = rows.data[0]
    stored = row.get("guest_token")
    return (
        row.get("status") == "guest"
        and bool(stored)
        and hmac.compare_digest(str(stored), token)
    )


def require_issue_access(
    issue_id: UUID,
    request: Request,
    db_service: DatabaseService = Depends(get_db_service),
) -> IssueAccess:
    """Owner (Bearer token) or guest-token holder. 401 without credentials, 404 otherwise.

    "Missing" and "not yours" share the 404 so issue IDs can't be probed.
    """
    issue = str(issue_id)
    bearer = _bearer_token(request)
    guest_token = request.headers.get(GUEST_TOKEN_HEADER, "").strip()
    if not bearer and not guest_token:
        raise HTTPException(status_code=401, detail="Sign in to continue")

    if bearer:
        user_id = get_current_user_id(request, db_service)  # 401 on a bad token
        if _is_owner(db_service, issue, user_id):
            return IssueAccess(issue, user_id)
    if guest_token and _holds_guest_token(db_service, issue, guest_token):
        return IssueAccess(issue)
    raise HTTPException(status_code=404, detail="Issue not found")


def require_issue_owner(
    issue_id: UUID,
    user_id: str = Depends(get_current_user_id),
    db_service: DatabaseService = Depends(get_db_service),
) -> IssueAccess:
    """Signed-in owner only (guests are rejected). 401 without a valid token, 404 if not owned."""
    if not _is_owner(db_service, str(issue_id), user_id):
        raise HTTPException(status_code=404, detail="Issue not found")
    return IssueAccess(str(issue_id), user_id)


def require_admin(x_admin_token: Optional[str] = Header(default=None)) -> None:
    """Internal/debug routes: `X-Admin-Token` must equal ADMIN_API_TOKEN.

    With ADMIN_API_TOKEN unset the routes behave as if they do not exist.
    """
    expected = os.getenv("ADMIN_API_TOKEN", "")
    if not expected:
        raise HTTPException(status_code=404, detail="Not found")
    if not x_admin_token or not hmac.compare_digest(x_admin_token, expected):
        raise HTTPException(status_code=401, detail="Admin token required")


def resolve_new_issue_owner(request: Request, db_service: DatabaseService) -> tuple[Optional[str], Optional[str]]:
    """Identify the caller creating an issue: (user_id, None) or (None, guest_token).

    A signed-in user wins over a guest token; without either there is no one to own the
    issue, so 401.
    """
    if _bearer_token(request):
        return get_current_user_id(request, db_service), None
    guest_token = request.headers.get(GUEST_TOKEN_HEADER, "").strip()
    if guest_token:
        return None, guest_token
    raise HTTPException(status_code=401, detail="Sign in to continue")
