from __future__ import annotations

import json
from pathlib import Path

from pydantic import BaseModel
from pydantic_settings import BaseSettings, SettingsConfigDict


class RemoteModelConf(BaseModel):
    key: str
    name: str
    kind: str = "remote"
    base_url: str
    api_key: str
    model: str
    description: str = ""


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    # 数据库
    database_url: str = "sqlite:///./app.db"

    # JWT
    secret_key: str = "dev-secret-change-me"
    jwt_algorithm: str = "HS256"
    access_token_expire_days: int = 7

    # 密码
    sha256_salt: str = "chat-system-static-salt"

    # 远端模型
    remote_models_json: str = "[]"

    # 本地模型目录（相对 backend/ 的路径或绝对路径）
    local_models_dir: str = "../models_store"

    # 本地训练代码目录（自定义 GPTModel 训练脚本的位置）
    training_dir: str = "../training"

    @property
    def remote_models(self) -> list[RemoteModelConf]:
        try:
            data = json.loads(self.remote_models_json)
            return [RemoteModelConf(**item) for item in data]
        except Exception:
            return []

    @property
    def local_models_path(self) -> Path:
        p = Path(self.local_models_dir)
        if not p.is_absolute():
            p = (Path(__file__).resolve().parent.parent / p).resolve()
        return p

    @property
    def training_path(self) -> Path:
        p = Path(self.training_dir)
        if not p.is_absolute():
            p = (Path(__file__).resolve().parent.parent / p).resolve()
        return p


settings = Settings()
