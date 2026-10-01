"""Supabase JWT validation.

The frontend signs in with Supabase Auth and sends the access token as a Bearer token.
We verify it here and use the ``sub`` claim as the user id. The user id is never taken
from request bodies or query strings.

Supports both legacy HS256 projects (SUPABASE_JWT_SECRET) and projects using asymmetric
signing keys (RS256/ES256), which are verified against the project's JWKS endpoint.
"""

import uuid
from functools import lru_cache
from typing import Annotated

import jwt
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from app.config import Settings, get_settings

_bearer = HTTPBearer(auto_error=False)


def _unauthorized(detail: str = "Not authenticated") -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED, detail=detail, headers={"WWW-Authenticate": "Bearer"}
    )


@lru_cache
def _jwks_client(supabase_url: str) -> jwt.PyJWKClient:
    return jwt.PyJWKClient(f"{supabase_url.rstrip('/')}/auth/v1/.well-known/jwks.json", cache_keys=True)


def decode_supabase_token(token: str, settings: Settings) -> dict:
    try:
        header = jwt.get_unverified_header(token)
    except jwt.PyJWTError as exc:
        raise _unauthorized("Invalid authentication token") from exc

    alg = header.get("alg")
    options = {"require": ["exp", "sub"]}
    try:
        if alg == "HS256":
            if not settings.supabase_jwt_secret:
                raise _unauthorized("Server is not configured for HS256 tokens")
            return jwt.decode(
                token,
                settings.supabase_jwt_secret,
                algorithms=["HS256"],
                audience=settings.jwt_audience,
                options=options,
            )
        if alg in {"RS256", "ES256"}:
            if not settings.supabase_url:
                raise _unauthorized("Server is not configured for asymmetric tokens")
            signing_key = _jwks_client(settings.supabase_url).get_signing_key_from_jwt(token)
            return jwt.decode(token, signing_key.key, algorithms=[alg], audience=settings.jwt_audience, options=options)
    except jwt.ExpiredSignatureError as exc:
        raise _unauthorized("Session expired, please sign in again") from exc
    except jwt.PyJWTError as exc:
        raise _unauthorized("Invalid authentication token") from exc
    raise _unauthorized("Unsupported token algorithm")


def get_current_user_id(
    credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(_bearer)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> uuid.UUID:
    if credentials is None or credentials.scheme.lower() != "bearer":
        raise _unauthorized()
    claims = decode_supabase_token(credentials.credentials, settings)
    try:
        return uuid.UUID(claims["sub"])
    except (KeyError, ValueError) as exc:
        raise _unauthorized("Invalid authentication token") from exc


CurrentUserId = Annotated[uuid.UUID, Depends(get_current_user_id)]
