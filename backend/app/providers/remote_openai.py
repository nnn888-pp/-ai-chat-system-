from __future__ import annotations

import asyncio
import threading
import time

from ..config import RemoteModelConf
from . import BaseProvider, ProviderStatus


class RemoteOpenAIProvider(BaseProvider):
    """走 OpenAI 兼容协议的远端大模型。同步 httpx 调用（服务内部放线程池）。"""

    kind = "remote"

    def __init__(self, conf: RemoteModelConf):
        self.conf = conf
        self.key = conf.key
        self.name = conf.name
        self.description = conf.description or f"远端 {conf.model}"
        self._status = ProviderStatus(status="ready")
        self._lock = threading.Lock()

    def get_status(self) -> ProviderStatus:
        return self._status

    def generate(self, messages: list[dict], **kwargs) -> str:
        import httpx

        payload = {
            "model": self.conf.model,
            "messages": messages,
            "temperature": kwargs.get("temperature", 0.7),
            "max_tokens": kwargs.get("max_new_tokens", 512),
        }
        url = self.conf.base_url.rstrip("/") + "/chat/completions"
        headers = {
            "Authorization": f"Bearer {self.conf.api_key}",
            "Content-Type": "application/json",
        }

        try:
            with httpx.Client(timeout=30) as client:
                resp = client.post(url, json=payload, headers=headers)
            if resp.status_code != 200:
                self._status = ProviderStatus(status="failed", error_msg=f"HTTP {resp.status_code}: {resp.text[:200]}")
                raise RuntimeError(f"远端模型 {self.conf.name} 返回 {resp.status_code}")
            data = resp.json()
            return data["choices"][0]["message"]["content"] or ""
        except Exception as e:
            self._status = ProviderStatus(status="failed", error_msg=str(e)[:200])
            raise RuntimeError(f"调用远端模型失败: {e}")
