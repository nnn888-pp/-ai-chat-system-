# scripts/test_qwen_lora.py
# 测试 Qwen2.5-1.5B + LoRA 模型是否能正常加载和推理
import sys
from pathlib import Path

# 添加 backend 到路径
sys.path.insert(0, str(Path(__file__).parent.parent))

from transformers import AutoModelForCausalLM, AutoTokenizer
from peft import PeftModel
import torch


def main():
    models_store = Path(__file__).parent.parent / "models_store"
    lora_path = models_store / "qwen-lora-wukong"

    print("=" * 50)
    print("测试 Qwen2.5-1.5B + LoRA (孙悟空风格)")
    print("=" * 50)

    # 1. 加载基座模型
    print("\n[1/4] 加载基座模型 Qwen/Qwen2.5-1.5B ...")
    print("      (首次运行会自动从 ModelScope 下载，约 3GB)")
    try:
        base = AutoModelForCausalLM.from_pretrained(
            "Qwen/Qwen2.5-1.5B",
            cache_dir=str(models_store),
            torch_dtype=torch.float32,
            trust_remote_code=True,
        )
        tokenizer = AutoTokenizer.from_pretrained(
            "Qwen/Qwen2.5-1.5B",
            cache_dir=str(models_store),
            trust_remote_code=True,
        )
        print("      ✓ 基座加载成功")
    except Exception as e:
        print(f"      ✗ 基座加载失败: {e}")
        return

    # 2. 加载 LoRA 权重
    print(f"\n[2/4] 加载 LoRA 权重: {lora_path} ...")
    try:
        model = PeftModel.from_pretrained(base, str(lora_path))
        model.eval()
        print("      ✓ LoRA 加载成功")
    except Exception as e:
        print(f"      ✗ LoRA 加载失败: {e}")
        return

    # 3. 测试生成
    print("\n[3/4] 测试生成 (问题: 你是谁) ...")
    prompt = "<|im_start|>user\n你是谁<|im_end|>\n<|im_start|>assistant\n"
    try:
        inputs = tokenizer(prompt, return_tensors="pt")
        with torch.no_grad():
            out = model.generate(
                **inputs,
                max_new_tokens=80,
                do_sample=True,
                temperature=0.7,
                top_p=0.9,
            )
        result = tokenizer.decode(out[0], skip_special_tokens=True)
        # 只取 assistant 部分
        reply = result.split("<|im_start|>assistant\n")[-1].strip()
        print(f"      ✓ 生成成功")
        print(f"\n      回复: {reply}")
    except Exception as e:
        print(f"      ✗ 生成失败: {e}")
        return

    # 4. 再测一个问题
    print("\n[4/4] 再测一个问题 (问题: 介绍一下你自己) ...")
    prompt2 = "<|im_start|>user\n介绍一下你自己<|im_end|>\n<|im_start|>assistant\n"
    try:
        inputs2 = tokenizer(prompt2, return_tensors="pt")
        with torch.no_grad():
            out2 = model.generate(
                **inputs2,
                max_new_tokens=100,
                do_sample=True,
                temperature=0.7,
                top_p=0.9,
            )
        result2 = tokenizer.decode(out2[0], skip_special_tokens=True)
        reply2 = result2.split("<|im_start|>assistant\n")[-1].strip()
        print(f"      ✓ 生成成功")
        print(f"\n      回复: {reply2}")
    except Exception as e:
        print(f"      ✗ 生成失败: {e}")
        return

    print("\n" + "=" * 50)
    print("测试完成！模型可以正常加载和推理。")
    print("=" * 50)


if __name__ == "__main__":
    main()
