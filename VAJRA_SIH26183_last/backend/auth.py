"""
Auth -- Technical Defense Document section 10.

JWT-based stateless auth with short-lived access tokens, role-based
access control (Officer / Supervisor / Admin / Reporter). Uses real
PyJWT (HS256) -- the previous build hand-rolled the same token shape
with only hmac/hashlib/base64 to avoid a pip install; that dependency
is cheap and standard, so this build takes it instead of reinventing
JWT signing/verification by hand. Every function below keeps the exact
same name and signature as before, so nothing calling into this module
had to change.
"""
import os
import time

import jwt as _pyjwt

SECRET = os.environ.get("VAJRA_JWT_SECRET", "vajra-dev-secret-change-in-production-9f21a")
_DEFAULT_SECRET = "vajra-dev-secret-change-in-production-9f21a"
ACCESS_TOKEN_TTL_SECONDS = 15 * 60  # 15 min, per Technical Defense Document section 10
REFRESH_TOKEN_TTL_SECONDS = 7 * 24 * 3600  # 7 days
ALGORITHM = "HS256"


def using_default_secret() -> bool:
    """True unless VAJRA_JWT_SECRET has been set to something else. server.py
    checks this at startup -- refuses to boot in VAJRA_ENV=production with the
    default secret still in place, and warns loudly otherwise."""
    return SECRET == _DEFAULT_SECRET

# All four officer-side permissions map to a real route:
# "reassign_case" -> GET /api/officers + POST /api/cases/{id}/reassign.
# "system_config" -> GET /api/system/config (read-only by design; see
# that route's docstring for why live config editing is roadmap, not built).
# "cross_jurisdiction_view" is honoured via admin + ?scope=all on
# /api/cases, /api/cases/network, /api/exchanges/risk-board, even though
# no route calls has_permission() for it by that literal name.
#
# "reporter" is a citizen/victim-facing role, distinct from the three
# investigator-side roles above -- it can only submit a suspect-address
# report (POST /api/public/report); it has no case-list, trace, or
# jurisdiction visibility of any kind. Added because the PS is literally
# titled "Victim-Reported Suspect Wallet Addresses" -- until now every
# role in this system was investigator-side, with no citizen-facing
# intake path at all.
ROLE_PERMISSIONS = {
    "reporter": {"submit_case"},
    "officer": {"run_trace", "draft_notice", "view_own_jurisdiction"},
    "supervisor": {"run_trace", "draft_notice", "approve_notice", "view_own_jurisdiction", "reassign_case"},
    "admin": {"run_trace", "draft_notice", "approve_notice", "view_own_jurisdiction",
              "reassign_case", "cross_jurisdiction_view", "view_audit_log", "system_config"},
}


def issue_token(officer_id, role, officer_code, jurisdiction, ttl=ACCESS_TOKEN_TTL_SECONDS):
    now = int(time.time())
    payload = {
        "sub": officer_id, "role": role, "officer_code": officer_code,
        "jurisdiction": jurisdiction, "iat": now, "exp": now + ttl,
    }
    return _pyjwt.encode(payload, SECRET, algorithm=ALGORITHM)


def issue_refresh_token(officer_id):
    # Longer-lived opaque refresh token; in production this is stored
    # server-side (revocable) -- here it's a signed token for the same
    # reason the access token is. Real PyJWT now, same as the access token.
    return issue_token(officer_id, "refresh", "", "", ttl=REFRESH_TOKEN_TTL_SECONDS)


class TokenError(Exception):
    pass


def verify_token(token):
    try:
        payload = _pyjwt.decode(token, SECRET, algorithms=[ALGORITHM])
    except _pyjwt.ExpiredSignatureError:
        raise TokenError("token expired")
    except _pyjwt.InvalidTokenError as e:
        # Covers bad signature, malformed token, wrong algorithm, etc. --
        # PyJWT's own exception hierarchy; we collapse it to the same
        # TokenError callers already handle, so main.py needed no changes.
        raise TokenError(str(e) or "invalid token")
    return payload


def has_permission(role, permission):
    return permission in ROLE_PERMISSIONS.get(role, set())
