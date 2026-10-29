from __future__ import annotations

from datetime import datetime
from typing import Optional

from pydantic import BaseModel, Field


# ===== 统一响应 =====
class UnifiedResponse(BaseModel):
    code: int = 0
    message: str = "ok"
    data: Optional[object] = None


# ===== Auth =====
class RegisterIn(BaseModel):
    username: str = Field(min_length=2, max_length=50)
    password: str = Field(min_length=6)   # 已 SHA-256 的 64 字符十六进制串；纯文本场景也兼容
    nickname: str = Field(min_length=1, max_length=50)


class LoginIn(BaseModel):
    username: str
    password: str  # 前端 SHA-256 后的十六进制串


# ===== User =====
class UserOut(BaseModel):
    id: int
    username: str
    nickname: str
    email: Optional[str] = None
    avatar: Optional[str] = None
    created_at: datetime

    class Config:
        from_attributes = True


class TokenOut(BaseModel):
    token: str
    user: UserOut


class UserUpdateIn(BaseModel):
    nickname: Optional[str] = None
    email: Optional[str] = None
    avatar: Optional[str] = None


class PasswordUpdateIn(BaseModel):
    old_password: str
    new_password: str


# ===== Conversation =====
class ConversationOut(BaseModel):
    id: int
    user_id: int
    title: str
    model_key: str
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class ConversationListItem(BaseModel):
    id: int
    title: str
    model_key: str
    last_message: Optional[str] = None
    updated_at: datetime


class ConversationCreateIn(BaseModel):
    title: str = "新对话"
    model_key: str


class ConversationUpdateIn(BaseModel):
    title: Optional[str] = None
    model_key: Optional[str] = None


# ===== Message =====
class MessageOut(BaseModel):
    id: int
    role: str
    content: str
    model_key: Optional[str] = None
    status: str
    created_at: datetime

    class Config:
        from_attributes = True


class MessageSendIn(BaseModel):
    content: str = Field(min_length=1, max_length=8000)
    model_key: Optional[str] = None


class MessageSendOut(BaseModel):
    user_message: MessageOut
    assistant_message: MessageOut


class MessageListOut(BaseModel):
    list: list[MessageOut]


# ===== Model =====
class ModelMeta(BaseModel):
    key: str
    name: str
    kind: str              # remote / local
    status: str            # ready / unloaded / loading / failed
    description: str = ""
    api_key_masked: Optional[str] = None
    error_msg: Optional[str] = None


class ModelListOut(BaseModel):
    list: list[ModelMeta]
