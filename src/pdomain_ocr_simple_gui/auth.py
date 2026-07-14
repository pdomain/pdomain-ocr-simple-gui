"""Capability token authentication for pdomain-ocr-simple-gui.

When PDOMAIN_API_TOKEN is set and non-empty, all mutating endpoints (POST,
PUT, DELETE) plus the prefs GET and jobs list GET require a matching token
supplied as either:

    Authorization: Bearer <token>
    X-API-Token: <token>

When the env var is absent or empty, no auth is applied so local-dev
usability is preserved.

Suite routes (/api/suite/*) are external mounts and cannot accept FastAPI
Depends; they are protected via HTTP middleware in app.py instead.
"""

from __future__ import annotations

import os
from typing import TYPE_CHECKING

from fastapi import Depends, HTTPException, Request
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

if TYPE_CHECKING:
    from starlette.middleware.base import RequestResponseEndpoint
    from starlette.responses import Response

_bearer_scheme = HTTPBearer(auto_error=False)

# HTTP methods that mutate state; suite routes using any of these under the
# /api/suite/ prefix require the token (see suite_token_middleware). This
# replaces a hardcoded path set — new suite mounts are protected without a
# manual allowlist edit, and GETs stay open.
_SUITE_MUTATING_METHODS = frozenset({"POST", "PUT", "DELETE", "PATCH"})
_SUITE_PATH_PREFIX = "/api/suite/"


def _configured_token() -> str:
    """Return the configured API token, or '' if auth is disabled."""
    return os.environ.get("PDOMAIN_API_TOKEN", "").strip()


def _check_token(request: Request, credentials: HTTPAuthorizationCredentials | None) -> None:
    """Raise HTTP 401 if the configured token is set and the request doesn't supply it.

    Accepts the token via:
      - Authorization: Bearer <token>
      - X-API-Token: <token>
    """
    token = _configured_token()
    if not token:
        # Auth disabled — local-dev mode.
        return

    # Check X-API-Token header first (custom header).
    x_token = request.headers.get("X-API-Token")
    if x_token and x_token == token:
        return

    # Check Authorization: Bearer <token>.
    if credentials is not None and credentials.credentials == token:
        return

    raise HTTPException(status_code=401, detail="Invalid or missing API token")


async def require_token(
    request: Request,
    credentials: HTTPAuthorizationCredentials | None = Depends(_bearer_scheme),  # pyright: ignore[reportCallInDefaultInitializer]
) -> None:
    """FastAPI dependency that enforces the capability token when configured.

    Inject this into any route that should be protected:

        @router.post("", dependencies=[Depends(require_token)])

    No-ops when PDOMAIN_API_TOKEN is absent or empty.
    """
    _check_token(request, credentials)


async def suite_token_middleware(request: Request, call_next: RequestResponseEndpoint) -> Response:
    """Starlette middleware that protects mutating /api/suite/* paths.

    Suite routes are mounted externally (pdomain_ops.suite.routes) and
    cannot use FastAPI Depends. This middleware intercepts mutating requests
    (POST/PUT/DELETE/PATCH) under the suite prefix and applies the same
    token check before forwarding; GETs stay open.
    """
    path = request.url.path
    if path.startswith(_SUITE_PATH_PREFIX) and request.method in _SUITE_MUTATING_METHODS:
        token = _configured_token()
        if token:
            # Must carry a valid token.
            x_token = request.headers.get("X-API-Token")
            auth_header = request.headers.get("Authorization", "")
            bearer_value = ""
            if auth_header.startswith("Bearer "):
                bearer_value = auth_header[len("Bearer ") :]

            if token not in {x_token, bearer_value}:
                from fastapi.responses import JSONResponse

                return JSONResponse(
                    status_code=401,
                    content={"detail": "Invalid or missing API token"},
                )

    return await call_next(request)
