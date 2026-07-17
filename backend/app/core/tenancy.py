"""Multi-tenancy — who is asking.

The engine has no user model and does not authenticate anyone: the HUB owns identity. Its
gateway authenticates the session, then forwards the caller's org and user as headers
(hub/backend/gateway.py):

    X-Goalcert-Org   -> the tenant
    X-Goalcert-User  -> the person

We trust those headers, and that trust is only sound because of where this engine sits: it
is reachable ONLY through the gateway (private VPC on AWS; the gateway injects the
X-API-Key shared secret server-side, so a browser never holds it). Anything that can reach
this engine directly could set any org header it likes — which is precisely why
SCENARIO_API_KEY must be set on a deployed engine. Unset, `verify_api_key` allows all,
and then tenancy is decoration rather than isolation.

No header => org is None. That is the SAFE direction, not a bypass: a request with no org
sees only shared seed scenarios and its own org-less runs, never another tenant's data.
Standalone (`npm run dev`, or the engine serving its own UI) is exactly this case, and
works because everything it authors is likewise org-less.
"""
from __future__ import annotations

from fastapi import Header


def current_org(x_goalcert_org: str = Header(default="")) -> str | None:
    """The calling tenant, or None when there is no tenant context.

    Empty string and whitespace normalise to None so a header the gateway set to "" can't
    become a tenant literally named "" that owns rows.
    """
    org = (x_goalcert_org or "").strip()
    return org or None


def current_user(x_goalcert_user: str = Header(default="")) -> str | None:
    """The calling user. Not used for isolation — scoping is per-ORG, not per-user, so a
    colleague can see scenarios their teammate authored. Available for attribution."""
    user = (x_goalcert_user or "").strip()
    return user or None
