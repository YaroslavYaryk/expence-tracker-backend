from __future__ import annotations

import json
import time
import base64
from typing import Optional, Dict, Any

import jwt
import requests
from cachetools import TTLCache

from fastapi import Depends, Request
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.errors import AppError
from app.core.db import get_db
from app.services.users_service import UsersService


_JWKS_CACHE = TTLCache(maxsize=4, ttl=3600)  # 1 hour


def _fetch_jwks() -> dict:
    cached = _JWKS_CACHE.get("jwks")
    if cached:
        return cached
    r = requests.get(settings.jwks_url, timeout=5)
    if r.status_code != 200:
        raise AppError("UNAUTHORIZED", "Unable to fetch JWKS", status_code=401)
    jwks = r.json()
    _JWKS_CACHE["jwks"] = jwks
    return jwks


def _get_public_key(token: str):
    try:
        header = jwt.get_unverified_header(token)
    except Exception:
        raise AppError("UNAUTHORIZED", "Invalid token header", status_code=401)

    kid = header.get("kid")
    if not kid:
        raise AppError("UNAUTHORIZED", "Token missing kid", status_code=401)

    jwks = _fetch_jwks()
    keys = jwks.get("keys", [])
    for k in keys:
        if k.get("kid") == kid:
            return jwt.algorithms.RSAAlgorithm.from_jwk(json.dumps(k))

    # refresh once
    _JWKS_CACHE.pop("jwks", None)
    jwks = _fetch_jwks()
    for k in jwks.get("keys", []):
        if k.get("kid") == kid:
            return jwt.algorithms.RSAAlgorithm.from_jwk(json.dumps(k))

    raise AppError("UNAUTHORIZED", "Unknown token kid", status_code=401)


def _extract_bearer_token(request: Request) -> str:
    auth = request.headers.get("authorization") or request.headers.get("Authorization")
    if not auth:
        raise AppError("UNAUTHORIZED", "Missing Authorization header", status_code=401)
    parts = auth.split(" ")
    if len(parts) != 2 or parts[0].lower() != "bearer":
        raise AppError("UNAUTHORIZED", "Invalid Authorization header", status_code=401)
    return parts[1].strip()


def verify_jwt(token: str) -> Dict[str, Any]:
    key = _get_public_key(token)
    options = {"require": ["exp", "iss", "sub"]}
    kwargs: Dict[str, Any] = {
        "key": key,
        "algorithms": ["RS256"],
        "issuer": settings.jwt_issuer,
        "options": options,
    }
    if settings.jwt_audience:
        kwargs["audience"] = settings.jwt_audience

    try:
        payload = jwt.decode(token, **kwargs)
        return payload
    except jwt.ExpiredSignatureError:
        raise AppError("UNAUTHORIZED", "Token expired", status_code=401)
    except jwt.InvalidIssuerError:
        raise AppError("UNAUTHORIZED", "Invalid token issuer", status_code=401)
    except jwt.InvalidAudienceError:
        raise AppError("UNAUTHORIZED", "Invalid token audience", status_code=401)
    except Exception:
        raise AppError("UNAUTHORIZED", "Invalid token", status_code=401)


def get_current_user(
    request: Request,
    db: Session = Depends(get_db),
):
    token = _extract_bearer_token(request)
    payload = verify_jwt(token)

    external_auth_id = str(payload.get("sub"))
    email = payload.get("email") or payload.get("email_address") or ""
    full_name = payload.get("name")

    if not external_auth_id:
        raise AppError("UNAUTHORIZED", "Token missing sub", status_code=401)

    svc = UsersService(db)
    user = svc.get_or_create_by_external_auth(
        external_auth_id=external_auth_id,
        email=email,
        full_name=full_name,
    )
    return user
