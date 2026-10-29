from __future__ import annotations

import json
import os
import sys
import threading
from dataclasses import dataclass
from pathlib import Path

import torch
from tokenizers import Tokenizer

from ..config import settings
from . import BaseProvider, ProviderStatus


def _ensure_training_path():
    """把自定义 GPTModel 训练代码目录加进 sys.path，便于 import model.py / config.py / lora.py"""
    tp = str(settings.training_path)
    if tp not in sys.path:
        sys.path.insert(0, tp)


@dataclass
class LocalModelConfig:
    """从 models_store/<key>/model_config.json 读出来的元信息。"""
    kind: str                       # "local_custom"
    name: str
    ckpt_path: str                  # 预训练 / 全量 SFT 权重（.pth）
    tokenizer_path: str             # tokenizer.json
    lora_path: str | None = None    # 可选 LoRA adapter（.pth）
    prompt_template: str = "问：{question}\n答："
    max_new_tokens: int = 64
    top_k: int = 10
    temperature: float = 0.8
    device: str = "cpu"
    max_seq_len: int = 128  # 运行时从 checkpoint 推导出的上下文窗口大小


def _load_local_config(dir_path: Path) -> LocalModelConfig:
    cfg_path = dir_path / "model_config.json"
    if not cfg_path.exists():
        raise FileNotFoundError(f"缺少 model_config.json：{cfg_path}")
    raw = json.loads(cfg_path.read_text(encoding="utf-8"))
    # 允许路径相对 config 目录自身
    resolve = lambda p: str((dir_path / p).resolve()) if p else None
    return LocalModelConfig(
        kind=raw.get("kind", "local_custom"),
        name=raw.get("name", dir_path.name),
        ckpt_path=resolve(raw["ckpt_path"]),
        tokenizer_path=resolve(raw["tokenizer_path"]),
        lora_path=resolve(raw.get("lora_path")),
        prompt_template=raw.get("prompt_template", "问：{question}\n答："),
        max_new_tokens=raw.get("max_new_tokens", 64),
        top_k=raw.get("top_k", 10),
        temperature=raw.get("temperature", 0.8),
        device=raw.get("device", "cpu"),
    )


class LocalPTProvider(BaseProvider):
    """加载自己训练的 GPTModel（自定义 nn.Module，原生 .pth）。"""

    kind = "local"

    def __init__(self, key: str, dir_path: Path):
        self.key = key
        self.dir_path = dir_path
        self.name = dir_path.name
        self.description = f"本地模型：{dir_path.name}"
        try:
            raw = json.loads((dir_path / "model_config.json").read_text(encoding="utf-8"))
            self.name = raw.get("name", self.name)
            self.description = raw.get("description") or self.description
        except Exception:
            pass
        self._lock = threading.Lock()
        self._tokenizer: Tokenizer | None = None
        self._model = None
        self._cfg: LocalModelConfig | None = None
        self._status = ProviderStatus(status="unloaded")

    def get_status(self) -> ProviderStatus:
        return self._status

    # ---- 懒加载 ----
    def _ensure_loaded(self) -> None:
        if self._model is not None:
            return
        with self._lock:
            if self._model is not None:
                return
            self._status = ProviderStatus(status="loading")
            try:
                _ensure_training_path()
                self._cfg = _load_local_config(self.dir_path)
                self.name = self._cfg.name  # 用 model_config.json 里的名字覆盖
                self._tokenizer = Tokenizer.from_file(self._cfg.tokenizer_path)

                import torch
                from config import TrainConfig
                from model import GPTModel, convert_old_state_dict

                ckpt = torch.load(self._cfg.ckpt_path, map_location=self._cfg.device)
                sd = convert_old_state_dict(ckpt["model"])

                cfg = TrainConfig()
                cfg = TrainConfig(
                    vocab_size=sd["token_emb.weight"].shape[0],
                    max_seq_len=sd["pos_emb.weight"].shape[0],
                )
                model = GPTModel(cfg).to(cfg.device)
                model.load_state_dict(sd)

                # 把从 checkpoint 推导出的上下文窗口回填进 LocalModelConfig
                self._cfg.max_seq_len = cfg.max_seq_len
                self._cfg.device = cfg.device

                if self._cfg.lora_path:
                    from lora import apply_lora, load_lora
                    apply_lora(model, rank=int(Path(self._cfg.lora_path).stem.split("rank")[-1]))
                    load_lora(model, self._cfg.lora_path)

                model.eval()
                self._model = model
                self._status = ProviderStatus(status="ready")
            except Exception as e:
                self._status = ProviderStatus(status="failed", error_msg=str(e)[:300])
                raise

    # ---- 推理 ----
    @torch.no_grad()
    def generate(self, messages: list[dict], **kwargs) -> str:
        self._ensure_loaded()
        cfg = self._cfg
        tokenizer = self._tokenizer
        model = self._model

        # 只取最后一条 user 消息，按 chat.py 里的 prompt_template 拼
        question = next((m["content"] for m in reversed(messages) if m.get("role") == "user"), "")
        prompt = cfg.prompt_template.format(question=question)
        ids = tokenizer.encode(prompt).ids
        x = torch.tensor(ids, dtype=torch.long, device=torch.device(cfg.device))[None, :]

        max_new = kwargs.get("max_new_tokens", cfg.max_new_tokens)
        top_k = kwargs.get("top_k", cfg.top_k)
        temp = kwargs.get("temperature", cfg.temperature)

        # 同 chat.py 的 top-k 采样生成，遇到换行就停
        for _ in range(max_new):
            logits = model(x[:, -cfg.max_seq_len:])[:, -1, :]
            if top_k > 0:
                values, indices = torch.topk(logits, min(top_k, logits.size(-1)))
                probs = torch.softmax(values / max(temp, 1e-6), dim=-1)
                next_id = indices.gather(-1, torch.multinomial(probs, 1))
            else:
                next_id = torch.argmax(logits, dim=-1, keepdim=True)
            x = torch.cat([x, next_id], dim=-1)
            new_text = tokenizer.decode(x[0, len(ids):].tolist())
            if "\n" in new_text:
                return new_text.split("\n")[0]
        return tokenizer.decode(x[0, len(ids):].tolist())
