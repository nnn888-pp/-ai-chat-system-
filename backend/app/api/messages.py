from __future__ import annotations

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from ..database import get_db
from ..models import User
from ..schemas import UnifiedResponse, MessageSendIn, MessageOut
from ..services.chat_service import ChatService
from .deps import get_current_user

router = APIRouter(prefix="/conversations", tags=["messages"])


def _ok(data):
    return UnifiedResponse(code=0, message="ok", data=data)


@router.get("/{conv_id}/messages", response_model=UnifiedResponse)
def list_messages(
    conv_id: int,
    limit: int = Query(default=200, le=200),
    current: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    rows = ChatService.list_messages(db, conv_id, current.id)
    return _ok({"list": [MessageOut.model_validate(m).model_dump() for m in rows[-limit:]]})


@router.post("/{conv_id}/messages", response_model=UnifiedResponse)
def send_message(
    conv_id: int,
    body: MessageSendIn,
    current: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    user_msg, assistant_msg = ChatService.send_message(
        db, conv_id, current.id, content=body.content, model_key=body.model_key,
    )
    return _ok({
        "user_message": MessageOut.model_validate(user_msg).model_dump(),
        "assistant_message": MessageOut.model_validate(assistant_msg).model_dump(),
    })


@router.delete("/{conv_id}/messages", response_model=UnifiedResponse)
def clear_messages(conv_id: int, current: User = Depends(get_current_user), db: Session = Depends(get_db)):
    ChatService.clear_messages(db, conv_id, current.id)
    return _ok(None)
