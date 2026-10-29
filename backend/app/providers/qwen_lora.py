"""加载 Qwen 基座 + 可选 LoRA（peft + transformers）。"""
from __future__ import annotations

import json
import re
import threading
from dataclasses import dataclass
from pathlib import Path

import torch

from . import BaseProvider, ProviderStatus


@dataclass
class QwenConfig:
    kind: str
    name: str
    base_model_path: str
    lora_path: str | None = None
    device: str = "cpu"
    max_new_tokens: int = 128
    temperature: float = 0.7
    top_p: float = 0.9
    lora_scale: float = 1.0
    # chat = 走 chat template（仅 Instruct 模型可用）；
    # raw_completion = 裸文本续写（基座/基座LoRA 对 im_start 格式 OOD，必须用此模式）
    prompt_format: str = "chat"
    # raw_completion 模式下拼接在对话前的身份/风格前缀
    prepend_text: str = ""


def _resolve(dir_path: Path, p: str | None) -> str | None:
    if not p:
        return None
    q = Path(p)
    return str(q.resolve()) if q.is_absolute() else str((dir_path / q).resolve())


def _load_qwen_config(dir_path: Path) -> QwenConfig:
    cfg_path = dir_path / "model_config.json"
    if not cfg_path.exists():
        raise FileNotFoundError(f"缺少 model_config.json：{cfg_path}")
    raw = json.loads(cfg_path.read_text(encoding="utf-8"))
    return QwenConfig(
        kind=raw.get("kind", "hf_qwen"),
        name=raw.get("name", dir_path.name),
        base_model_path=_resolve(dir_path, raw["base_model_path"]),
        lora_path=_resolve(dir_path, raw.get("lora_path")),
        device=raw.get("device", "cpu"),
        max_new_tokens=raw.get("max_new_tokens", 128),
        temperature=raw.get("temperature", 0.7),
        top_p=raw.get("top_p", 0.9),
        lora_scale=raw.get("lora_scale", 1.0),
        prompt_format=raw.get("prompt_format", "chat"),
        prepend_text=raw.get("prepend_text", ""),
    )


class QwenLoRAProvider(BaseProvider):
    kind = "local_hf"

    def __init__(self, key: str, dir_path: Path):
        self.key = key
        self.dir_path = dir_path
        self.name = dir_path.name
        self.description = "Qwen 本地模型"
        try:
            raw = json.loads((dir_path / "model_config.json").read_text(encoding="utf-8"))
            self.name = raw.get("name", self.name)
            self.description = raw.get("description") or self.description
        except Exception:
            pass
        self._lock = threading.Lock()
        self._model = None
        self._tokenizer = None
        self._cfg: QwenConfig | None = None
        self._status = ProviderStatus(status="unloaded")

    def get_status(self) -> ProviderStatus:
        return self._status

    def _ensure_loaded(self) -> None:
        if self._model is not None:
            return
        with self._lock:
            if self._model is not None:
                return
            self._status = ProviderStatus(status="loading")
            try:
                from transformers import AutoModelForCausalLM, AutoTokenizer
                from peft import PeftModel

                self._cfg = _load_qwen_config(self.dir_path)
                self.name = self._cfg.name

                base_dir = str(Path(self._cfg.base_model_path).resolve())
                print(f"[QwenLoRAProvider] 加载基座: {base_dir}")

                base = AutoModelForCausalLM.from_pretrained(
                    base_dir,
                    torch_dtype=torch.float32,
                    trust_remote_code=True,
                    local_files_only=True,
                )
                self._tokenizer = AutoTokenizer.from_pretrained(
                    base_dir,
                    trust_remote_code=True,
                    local_files_only=True,
                )

                if self._cfg.lora_path and Path(self._cfg.lora_path).exists():
                    print(f"[QwenLoRAProvider] 加载 LoRA: {self._cfg.lora_path}")
                    lora_dir = str(Path(self._cfg.lora_path).resolve())
                    base = PeftModel.from_pretrained(base, lora_dir)

                base.eval()
                self._model = base
                self._status = ProviderStatus(status="ready")
                print("[QwenLoRAProvider] 加载完成")
            except Exception as e:
                self._status = ProviderStatus(status="failed", error_msg=str(e)[:300])
                raise

    def _build_prompt(self, messages: list[dict]) -> str:
        cfg = self._cfg
        tokenizer = self._tokenizer
        if cfg.prompt_format == "raw_completion":
            # 基座/基座LoRA：裸文本续写，不用 chat template
            parts = []
            for m in messages:
                role = m.get("role", "user")
                content = (m.get("content") or "").strip()
                if not content:
                    continue
                if role == "user":
                    parts.append(f"问：{content}")
                elif role == "assistant":
                    parts.append(f"答：{content}")
                else:
                    parts.append(content)
            parts.append("答：")
            body = "\n".join(parts)
            return (cfg.prepend_text + "\n" + body) if cfg.prepend_text else body
        # chat 模式：Instruct 模型走模板
        if getattr(tokenizer, "chat_template", None):
            return tokenizer.apply_chat_template(
                messages, tokenize=False, add_generation_prompt=True
            )
        prompt_parts = []
        for m in messages:
            role = m.get("role", "user")
            content = m.get("content", "")
            prompt_parts.append(f"<|im_start|>{role}\n{content}<|im_end|>")
        prompt_parts.append("<|im_start|>assistant\n")
        return "\n".join(prompt_parts)

    @torch.no_grad()
    def generate(self, messages: list[dict], **kwargs) -> str:
        self._ensure_loaded()
        cfg = self._cfg
        model = self._model
        tokenizer = self._tokenizer

        prompt = self._build_prompt(messages)

        inputs = tokenizer(prompt, return_tensors="pt")
        max_new = kwargs.get("max_new_tokens", cfg.max_new_tokens)
        temp = kwargs.get("temperature", cfg.temperature)
        top_p = kwargs.get("top_p", cfg.top_p)

        eos_id = tokenizer.eos_token_id
        if tokenizer.pad_token_id is None:
            tokenizer.pad_token_id = eos_id

        out = model.generate(
            **inputs,
            max_new_tokens=max_new,
            do_sample=temp > 0,
            temperature=max(temp, 1e-5),
            top_p=top_p,
            pad_token_id=tokenizer.pad_token_id,
            eos_token_id=eos_id,
            no_repeat_ngram_size=3,
        )
        gen_ids = out[0, inputs["input_ids"].shape[1]:].tolist()
        if eos_id is not None:
            stop_idx = None
            for i, tid in enumerate(gen_ids):
                if tid == eos_id:
                    stop_idx = i
                    break
            if stop_idx is not None:
                gen_ids = gen_ids[:stop_idx]
        text = tokenizer.decode(gen_ids, skip_special_tokens=True).strip()
        # raw_completion 续写会带出下一轮"问：…答：…"，切到第一个对话标记之前
        if cfg.prompt_format == "raw_completion":
            text = re.sub(r"^\s*(?:问|答)[：:；;]\s*", "", text)
            # 生成里只要再冒出"问：/答："，说明模型开始自问自答下一轮，直接截断
            m = re.search(r"(?:问|答)[：:；;]", text)
            if m and m.start() > 0:
                text = text[:m.start()]
            text = text.rstrip("，,。.、；;：: \n\t")
        return text.strip()
