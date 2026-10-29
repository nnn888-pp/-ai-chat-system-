from __future__ import annotations

import abc
from dataclasses import dataclass


@dataclass
class ProviderStatus:
    status: str           # ready / unloaded / loading / failed
    error_msg: str | None = None


class BaseProvider(abc.ABC):
    """所有模型 Provider 的共同接口。"""

    key: str
    name: str
    kind: str = "local"
    description: str = ""

    @abc.abstractmethod
    def get_status(self) -> ProviderStatus: ...

    @abc.abstractmethod
    def generate(
        self,
        messages: list[dict],  # [{"role": "user", "content": "..."}]
        *,
        max_new_tokens: int = 256,
        temperature: float = 0.7,
        top_k: int = 20,
    ) -> str: ...

    def load(self) -> None:
        """主动加载；默认 generate 里懒加载。"""
        self.generate([{"role": "user", "content": "ping"}])
