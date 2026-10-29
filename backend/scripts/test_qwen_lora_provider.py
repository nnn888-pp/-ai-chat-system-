"""测试 Qwen 基座 + LoRA 两个模型的推理。"""
from __future__ import annotations

import sys
from pathlib import Path

# 把 backend/app 加进 path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.providers.qwen_lora import QwenLoRAProvider


def test(key: str, name: str):
    print(f"\n===== 测试 {name} ({key}) =====")
    dir_path = Path(__file__).resolve().parent.parent.parent / "models_store" / key
    if not dir_path.exists():
        print(f"[SKIP] 目录不存在: {dir_path}")
        return

    p = QwenLoRAProvider(key=f"local:{key}", dir_path=dir_path)
    st = p.get_status()
    print(f"初始状态: {st.status}")

    try:
        out = p.generate([{"role": "user", "content": "你是谁"}])
        print(f"输出: {out}")
    except Exception as e:
        print(f"[FAIL] 推理失败: {e}")


if __name__ == "__main__":
    test("qwen-base", "Qwen 基座")
    test("qwen-lora-wukong", "Qwen + 孙悟空 LoRA")
    print("\n全部完成。")
