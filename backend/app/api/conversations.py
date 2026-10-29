from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from ..database import get_db
from ..models import User
from ..schemas import (
    UnifiedResponse,
    ConversationCreateIn, ConversationUpdateIn,
)
from ..services.chat_service import ChatService
from .deps import get_current_user

router = APIRouter(prefix="/conversations", tags=["conversations"])


def _ok(data):
    return UnifiedResponse(code=0, message="ok", data=data)


@router.get("", response_model=UnifiedResponse)
def list_conversations(current: User = Depends(get_current_user), db: Session = Depends(get_db)):
    items = ChatService.list_conversations(db, current.id)
    return _ok({"list": items})


@router.post("", response_model=UnifiedResponse)
def create(body: ConversationCreateIn, current: User = Depends(get_current_user), db: Session = Depends(get_db)):
    conv = ChatService.create_conversation(db, current.id, title=body.title, model_key=body.model_key)
    return _ok({
        "id": conv.id, "title": conv.title, "model_key": conv.model_key,
        "created_at": conv.created_at, "updated_at": conv.updated_at,
    })


@router.get("/{conv_id}", response_model=UnifiedResponse)
def detail(conv_id: int, current: User = Depends(get_current_user), db: Session = Depends(get_db)):
    conv = ChatService._get_owned_conversation(db, conv_id, current.id)
    return _ok({
        "id": conv.id, "title": conv.title, "model_key": conv.model_key,
        "created_at": conv.created_at, "updated_at": conv.updated_at,
    })


@router.patch("/{conv_id}", response_model=UnifiedResponse)
def update(conv_id: int, body: ConversationUpdateIn, current: User = Depends(get_current_user), db: Session = Depends(get_db)):
    conv = ChatService.rename_conversation(
        db, conv_id, current.id,
        title=body.title, model_key=body.model_key,
    )
    return _ok({
        "id": conv.id, "title": conv.title, "model_key": conv.model_key,
        "created_at": conv.created_at, "updated_at": conv.updated_at,
    })


@router.delete("/{conv_id}", response_model=UnifiedResponse)
def delete(conv_id: int, current: User = Depends(get_current_user), db: Session = Depends(get_db)):
    ChatService.delete_conversation(db, conv_id, current.id)
    return _ok(None)
