from __future__ import annotations

from sqlalchemy.orm import Session

from ..models import User
from ..utils.security import hash_password, verify_password, pre_hash_sha256
from ..utils.jwt import create_access_token
from .. import exc


class AuthService:
    @staticmethod
    def register(db: Session, *, username: str, password: str, nickname: str) -> User:
        if db.query(User).filter(User.username == username).first():
            raise exc.BizError(1005, "用户名已存在")
        hashed = hash_password(password)
        user = User(username=username, password=hashed, nickname=nickname)
        db.add(user)
        db.commit()
        db.refresh(user)
        return user

    @staticmethod
    def login(db: Session, *, username: str, password: str) -> tuple[str, User]:
        user = db.query(User).filter(User.username == username).first()
        if not user or not verify_password(password, user.password):
            raise exc.BizError(1002, "用户名或密码错误")
        token = create_access_token(user.id)
        return token, user

    @staticmethod
    def change_password(db: Session, user: User, *, old_password: str, new_password: str) -> None:
        if not verify_password(old_password, user.password):
            raise exc.BizError(1006, "原密码错误")
        if old_password == new_password:
            raise exc.BizError(1001, "新密码不能与旧密码相同")
        user.password = hash_password(new_password)
        db.commit()
        db.refresh(user)
