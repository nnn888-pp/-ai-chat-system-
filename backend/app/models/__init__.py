from datetime import datetime

from sqlalchemy import BigInteger, Column, DateTime, Integer, String, Text, UniqueConstraint, Index

from ..database import Base


class User(Base):
    __tablename__ = "users"

    id = Column(BigInteger().with_variant(Integer, "sqlite"), primary_key=True, autoincrement=True)
    username = Column(String(50), nullable=False, unique=True, index=True)
    password = Column(String(100), nullable=False)  # bcrypt 哈希，60 字符
    nickname = Column(String(50), nullable=False)
    email = Column(String(100), nullable=True)
    avatar = Column(String(255), nullable=True)
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    updated_at = Column(DateTime, nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow)


class Conversation(Base):
    __tablename__ = "conversations"

    id = Column(BigInteger().with_variant(Integer, "sqlite"), primary_key=True, autoincrement=True)
    user_id = Column(BigInteger, nullable=False, index=True)
    title = Column(String(100), nullable=False, default="新对话")
    model_key = Column(String(100), nullable=False)
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    updated_at = Column(DateTime, nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow)

    __table_args__ = (
        Index("ix_conv_user_updated", "user_id", "updated_at"),
    )


class Message(Base):
    __tablename__ = "messages"

    id = Column(BigInteger().with_variant(Integer, "sqlite"), primary_key=True, autoincrement=True)
    conversation_id = Column(BigInteger, nullable=False, index=True)
    role = Column(String(16), nullable=False)  # user / assistant
    content = Column(Text, nullable=False)
    model_key = Column(String(100), nullable=True)
    status = Column(String(16), nullable=False, default="ok")  # ok / error
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)

    __table_args__ = (
        Index("ix_msg_conv_created", "conversation_id", "created_at"),
    )
