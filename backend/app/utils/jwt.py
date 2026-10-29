from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any

from jose import jwt

from ..config import settings


def create_access_token(subject: str | int, expires_days: int | None = None) -> str:
    expire = datetime.now(timezone.utc) + timedelta(
        days=expires_days or settings.access_token_expire_days
    )
    payload: dict[str, Any] = {"sub": str(subject), "exp": expire}
    return jwt.encode(payload, settings.secret_key, algorithm=settings.jwt_algorithm)


def decode_access_token(token: str) -> dict[str, Any]:
    return jwt.decode(token, settings.secret_key, algorithms=[settings.jwt_algorithm])
