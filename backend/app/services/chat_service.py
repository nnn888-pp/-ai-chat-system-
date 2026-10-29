from __future__ import annotations

import threading
from datetime import datetime

from sqlalchemy.orm import Session

from ..models import Conversation, Message, User
from ..providers.registry import registry
from .. import exc


class ChatService:
    """会话 / 消息 / 模型调用的整合层。

    设计要点：
    - 所有查询都必须带 user_id，防止越权。
    - 本地模型的 generate 是阻塞线程的 CPU 推理，先在 FastAPI 默认线程池里执行即可；
      同一 provider 的内部线程锁保证不会并发打爆同一份模型。
    """

    # 最多带最近多少轮历史（用户 + 助手算一轮）
    HISTORY_ROUNDS = 10

    @staticmethod
    def _get_owned_conversation(db: Session, conv_id: int, user_id: int) -> Conversation:
        conv = (
            db.query(Conversation)
            .filter(Conversation.id == conv_id, Conversation.user_id == user_id)
            .first()
        )
        if not conv:
            raise exc.BizError(1004, "无权访问该会话")
        return conv

    # ---- 会话 ----
    @staticmethod
    def list_conversations(db: Session, user_id: int) -> list[dict]:
        convs = (
            db.query(Conversation)
            .filter(Conversation.user_id == user_id)
            .order_by(Conversation.updated_at.desc())
            .all()
        )
        out = []
        for c in convs:
            last = (
                db.query(Message.content)
                .filter(Message.conversation_id == c.id)
                .order_by(Message.created_at.desc())
                .limit(1)
                .scalar()
            )
            out.append({
                "id": c.id,
                "title": c.title,
                "model_key": c.model_key,
                "last_message": last[:80] if last else None,
                "updated_at": c.updated_at,
            })
        return out

    @staticmethod
    def create_conversation(db: Session, user_id: int, *, title: str, model_key: str) -> Conversation:
        conv = Conversation(user_id=user_id, title=title, model_key=model_key)
        db.add(conv)
        db.commit()
        db.refresh(conv)
        return conv

    @staticmethod
    def rename_conversation(db: Session, conv_id: int, user_id: int, *, title: str | None, model_key: str | None) -> Conversation:
        conv = ChatService._get_owned_conversation(db, conv_id, user_id)
        if title is not None:
            if not title.strip():
                raise exc.BizError(1001, "标题不能为空")
            if len(title) > 100:
                raise exc.BizError(1001, "标题过长")
            conv.title = title
        if model_key is not None:
            conv.model_key = model_key
        conv.updated_at = datetime.utcnow()
        db.commit()
        db.refresh(conv)
        return conv

    @staticmethod
    def delete_conversation(db: Session, conv_id: int, user_id: int) -> None:
        conv = ChatService._get_owned_conversation(db, conv_id, user_id)
        # 表间没有外键级联，必须显式删掉消息；否则 SQLite 复用自增 id 时，
        # 新会话会"继承"到已删会话的孤儿消息
        db.query(Message).filter(Message.conversation_id == conv.id).delete()
        db.delete(conv)
        db.commit()

    # ---- 消息 ----
    @staticmethod
    def list_messages(db: Session, conv_id: int, user_id: int) -> list[Message]:
        ChatService._get_owned_conversation(db, conv_id, user_id)  # 只做归属校验
        return (
            db.query(Message)
            .filter(Message.conversation_id == conv_id)
            .order_by(Message.created_at.asc())
            .all()
        )

    @staticmethod
    def clear_messages(db: Session, conv_id: int, user_id: int) -> None:
        ChatService._get_owned_conversation(db, conv_id, user_id)
        db.query(Message).filter(Message.conversation_id == conv_id).delete()
        db.commit()

    # ---- 发送消息（核心）----
    @staticmethod
    def send_message(
        db: Session,
        conv_id: int,
        user_id: int,
        content: str,
        model_key: str | None,
    ) -> tuple[Message, Message]:
        conv = ChatService._get_owned_conversation(db, conv_id, user_id)
        final_model = model_key or conv.model_key

        provider = registry.get(final_model)
        if not provider:
            raise exc.BizError(2004, f"模型不存在或未加载: {final_model}")

        # 1) 落库用户消息
        user_msg = Message(conversation_id=conv.id, role="user", content=content)
        db.add(user_msg)
        db.flush()

        # 2) 组装上下文（只保留最后 HISTORY_ROUNDS * 2 条）
        #    同一会话里可能切换过模型，只带当前模型自己的回复，避免把别的模型
        #    的输出当成上下文（尤其小 GPT 的续写结果会污染对话）
        history = (
            db.query(Message.role, Message.content, Message.model_key)
            .filter(Message.conversation_id == conv.id, Message.role.in_(["user", "assistant"]))
            .order_by(Message.created_at.asc())
            .all()
        )
        trimmed = [
            (r, c) for r, c, mk in history
            if r == "user" or mk == final_model
        ][-(ChatService.HISTORY_ROUNDS * 2):]
        messages = [{"role": r, "content": c} for r, c in trimmed]

        # 3) 调模型
        status = "ok"
        reply = ""
        try:
            reply = provider.generate(messages)
        except RuntimeError as e:
            # 远端 / 本地推理异常，业务码细分
            msg = str(e)
            if "远端" in msg or "HTTP" in msg:
                raise exc.BizError(2001, msg[:300])
            raise exc.BizError(2002, msg[:300])
        except Exception as e:
            raise exc.BizError(2002, f"模型调用异常: {e}")

        if not reply:
            reply = "(模型未返回内容)"

        # 4) 落库助手回复
        assistant_msg = Message(
            conversation_id=conv.id,
            role="assistant",
            content=reply,
            model_key=final_model,
            status=status,
        )
        db.add(assistant_msg)
        conv.updated_at = datetime.utcnow()
        db.commit()
        db.refresh(user_msg)
        db.refresh(assistant_msg)
        return user_msg, assistant_msg
