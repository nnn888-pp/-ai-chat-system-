from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from ..database import get_db
from ..models import User
from ..schemas import RegisterIn, LoginIn, UserOut, UnifiedResponse
from ..services.auth_service import AuthService
from ..utils.jwt import create_access_token

router = APIRouter(prefix="/auth", tags=["auth"])


def _ok(data):
    return UnifiedResponse(code=0, message="ok", data=data)


@router.post("/register", response_model=UnifiedResponse)
def register(body: RegisterIn, db: Session = Depends(get_db)):
    user = AuthService.register(db, username=body.username, password=body.password, nickname=body.nickname)
    return _ok({"id": user.id, "username": user.username, "nickname": user.nickname})


@router.post("/login", response_model=UnifiedResponse)
def login(body: LoginIn, db: Session = Depends(get_db)):
    token, user = AuthService.login(db, username=body.username, password=body.password)
    return _ok({
        "token": token,
        "user": UserOut.model_validate(user).model_dump(),
    })


@router.post("/logout", response_model=UnifiedResponse)
def logout():
    # 前端清 token 即可
    return _ok(None)
