# chat_qwen.py
# 开源模型 + LoRA 的对话测试（改编自课程参考实现 llama_print1.py）
#   python chat_qwen.py --model ./models/qwen2.5-1.5b --lora ./output/qwen_lora_sunwukong
import argparse

import torch
from peft import PeftModel
from transformers import AutoModelForCausalLM, AutoTokenizer

SYSTEM_PROMPT = "你现在是《西游记》里的齐天大圣孙悟空，说话要用俺老孙的语气。"

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--model", default="./models/qwen2.5-1.5b")
    parser.add_argument("--lora", default="./output/qwen_lora_sunwukong")
    parser.add_argument("--prompt", default="你是谁")
    args = parser.parse_args()

    tokenizer = AutoTokenizer.from_pretrained(args.model, trust_remote_code=True)
    model = AutoModelForCausalLM.from_pretrained(
        args.model,
        device_map="auto",
        torch_dtype=torch.bfloat16,
        trust_remote_code=True,
    ).eval()
    model = PeftModel.from_pretrained(model, model_id=args.lora)
    model.eval()

    print("===== 对话开始，输入 exit 退出 =====")
    while True:
        prompt = args.prompt if args.prompt else input("user：")
        if prompt.strip().lower() in ("exit", "quit"):
            break

        messages = [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": prompt},
        ]
        # 训练和推理用同一个聊天模板
        text = tokenizer.apply_chat_template(messages, tokenize=False, add_generation_prompt=True)
        inputs = tokenizer([text], return_tensors="pt").to(model.device)

        with torch.no_grad():
            out = model.generate(
                inputs.input_ids,
                attention_mask=inputs.attention_mask,
                max_new_tokens=200,
                do_sample=True,
                top_p=0.9,
                temperature=0.8,
                repetition_penalty=1.1,
            )
        reply = tokenizer.decode(out[0][inputs.input_ids.shape[1]:], skip_special_tokens=True)
        print(f"悟空：{reply}\n")

        if args.prompt:
            break
