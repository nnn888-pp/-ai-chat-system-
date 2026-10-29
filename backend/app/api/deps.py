from __future__ import annotations

from typing import Generator, Optional

from fastapi import Depends, Header, status
from fastapi.security import OAuth2PasswordBearer
from jose import JWTError
from sqlalchemy.orm import Session

from ..database import get_db
from ..models import User
from ..utils.jwt import decode_access_token
from .. import exc

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/auth/login", auto_error=False)


def _extract_token(authorization: Optional[str] = None) -> str | None:
    if authorization and authorization.lower().startswith("bearer "):
        return authorization.split(" ", 1)[1].strip()
    return None


def get_current_user(
    authorization: Optional[str] = Header(default=None),
    db: Session = Depends(get_db),
) -> User:
    token = _extract_token(authorization) or ""
    if not token:
        raise exc.BizError(1003, "未登录", http_status=401)
    try:
        payload = decode_access_token(token)
        user_id = int(payload.get("sub", "0"))
    except (JWTError, ValueError):
        raise exc.BizError(1003, "token 已失效", http_status=401)
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise exc.BizError(1003, "账号不存在", http_status=401)
    return user
