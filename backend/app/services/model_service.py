from __future__ import annotations

from .. import exc
from ..config import settings
from ..providers.registry import registry
from ..utils.security import mask_api_key


class ModelService:
    @staticmethod
    def list_models() -> list[dict]:
        out = []
        remote_by_key = {m.key: m for m in settings.remote_models}
        for meta in registry.list_meta():
            item = dict(meta)
            if meta["kind"] == "remote" and meta["key"] in remote_by_key:
                item["api_key_masked"] = mask_api_key(remote_by_key[meta["key"]].api_key)
            out.append(item)
        return out

    @staticmethod
    def refresh_models() -> list[dict]:
        registry.refresh()
        return ModelService.list_models()

    @staticmethod
    def load_model(key: str) -> dict:
        p = registry.get(key)
        if not p:
            raise exc.BizError(2004, f"模型不存在: {key}")
        p.load()
        return {
            "key": key,
            "status": p.get_status().status,
            "error_msg": p.get_status().error_msg,
        }
