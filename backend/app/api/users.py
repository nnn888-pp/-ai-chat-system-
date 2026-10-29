from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from ..database import get_db
from ..models import User
from ..schemas import (
    UserOut, UserUpdateIn, PasswordUpdateIn, UnifiedResponse,
)
from ..services.auth_service import AuthService
from .deps import get_current_user

router = APIRouter(prefix="/users", tags=["users"])


def _ok(data):
    return UnifiedResponse(code=0, message="ok", data=data)


@router.get("/me", response_model=UnifiedResponse)
def me(current: User = Depends(get_current_user)):
    return _ok(UserOut.model_validate(current).model_dump())


@router.put("/me", response_model=UnifiedResponse)
def update_me(body: UserUpdateIn, current: User = Depends(get_current_user), db: Session = Depends(get_db)):
    if body.nickname is not None and body.nickname.strip():
        current.nickname = body.nickname.strip()
    if body.email is not None:
        current.email = body.email or None
    if body.avatar is not None:
        current.avatar = body.avatar or None
    db.commit()
    db.refresh(current)
    return _ok(UserOut.model_validate(current).model_dump())


@router.put("/me/password", response_model=UnifiedResponse)
def change_password(body: PasswordUpdateIn, current: User = Depends(get_current_user), db: Session = Depends(get_db)):
    AuthService.change_password(db, current, old_password=body.old_password, new_password=body.new_password)
    return _ok(None)
