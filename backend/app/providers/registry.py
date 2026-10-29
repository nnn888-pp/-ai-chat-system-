from __future__ import annotations

import json
from pathlib import Path

from ..config import settings
from . import BaseProvider
from .mock import MockProvider
from .local_pt import LocalPTProvider
from .qwen_lora import QwenLoRAProvider
from .remote_openai import RemoteOpenAIProvider


class ModelRegistry:
    """统一管理所有模型 Provider。远端从环境变量读；本地扫描 models_store/ 目录。"""

    def __init__(self):
        self._providers: dict[str, BaseProvider] = {}
        self.refresh()

    # ---- 扫描 ----
    def refresh(self) -> list[dict]:
        self._providers.clear()

        # 1) 远端
        for conf in settings.remote_models:
            self._providers[conf.key] = RemoteOpenAIProvider(conf)

        # 2) 本地扫描
        local_dir: Path = settings.local_models_path
        if local_dir.exists():
            for sub in sorted(local_dir.iterdir()):
                if sub.is_dir() and (sub / "model_config.json").exists():
                    key = f"local:{sub.name}"
                    try:
                        raw = json.loads((sub / "model_config.json").read_text(encoding="utf-8"))
                        kind = raw.get("kind", "local_custom")
                        if kind in ("hf_qwen", "hf_qwen_lora"):
                            self._providers[key] = QwenLoRAProvider(key=key, dir_path=sub)
                        else:
                            self._providers[key] = LocalPTProvider(key=key, dir_path=sub)
                    except Exception as e:
                        self._providers[key] = MockProvider(key=key, name=f"{sub.name}（异常）", description=str(e)[:120])

        # 3) 离线兜底的 Mock 模型，让空目录下系统也能用
        if not self._providers:
            self._providers["mock:default"] = MockProvider("mock:default", name="离线测试模型")

        return self.list_meta()

    # ---- 查询 ----
    def get(self, key: str) -> BaseProvider | None:
        return self._providers.get(key)

    def list_meta(self) -> list[dict]:
        out = []
        for key, p in self._providers.items():
            st = p.get_status()
            out.append({
                "key": key,
                "name": p.name,
                "kind": p.kind,
                "status": st.status,
                "description": p.description,
                "api_key_masked": None,
                "error_msg": st.error_msg,
            })
        return out

    def load(self, key: str) -> None:
        p = self._providers.get(key)
        if not p:
            raise KeyError(key)
        p.load()


registry = ModelRegistry()
