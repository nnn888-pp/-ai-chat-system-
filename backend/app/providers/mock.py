from __future__ import annotations

from . import BaseProvider, ProviderStatus


class MockProvider(BaseProvider):
    """纯本地假模型，离线测试整个链路用。不走任何实际推理。"""

    kind = "local"

    def __init__(self, key: str, name: str = "Mock Model", description: str = ""):
        self.key = key
        self.name = name
        self.description = description

    def get_status(self) -> ProviderStatus:
        return ProviderStatus(status="ready")

    def generate(self, messages: list[dict], **kwargs) -> str:
        last = next((m["content"] for m in reversed(messages) if m.get("role") == "user"), "")
        return f"（Mock 回复）收到了你的消息：{last[:50]}。这是离线测试响应。"
