from __future__ import annotations

import hashlib

import bcrypt

from ..config import settings


def pre_hash_sha256(plain: str) -> str:
    """前端 SHA-256 + 静态盐，用于传输层的基本保护。原始设计就是 sha256(plain + salt) 的十六进制串。"""
    m = hashlib.sha256()
    m.update((plain + settings.sha256_salt).encode("utf-8"))
    return m.hexdigest()


def hash_password(password: str) -> str:
    """入库用 bcrypt，输入为前端 SHA-256 后的十六进制串（或纯文本，都兼容）"""
    return bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")


def verify_password(password: str, hashed: str) -> bool:
    try:
        return bcrypt.checkpw(password.encode("utf-8"), hashed.encode("utf-8"))
    except Exception:
        return False


def mask_api_key(key: str) -> str:
    if not key:
        return ""
    if len(key) <= 8:
        return "****"
    return key[:3] + "****" + key[-4:]
