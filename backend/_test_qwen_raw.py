"""最简 Qwen 推理测试 —— 直接用 transformers 官方 API，不走任何 Provider 封装"""
from transformers import AutoModelForCausalLM, AutoTokenizer
import torch

model_path = r"C:\Users\ping1\Desktop\ai-chat-system\models_store\models\Qwen--Qwen2.5-1.5B\snapshots\master"

print(f"[1] 加载 tokenizer ...")
tokenizer = AutoTokenizer.from_pretrained(model_path, local_files_only=True)
print(f"    eos_token_id = {tokenizer.eos_token_id}")
print(f"    pad_token_id = {tokenizer.pad_token_id}")
print(f"    chat_template = {tokenizer.chat_template is not None}")

print(f"[2] 加载基座模型 ...")
model = AutoModelForCausalLM.from_pretrained(
    model_path, local_files_only=True, torch_dtype=torch.float32
)

messages = [{"role": "user", "content": "你是谁"}]

print(f"[3] 拼 prompt ...")
text = tokenizer.apply_chat_template(messages, tokenize=False, add_generation_prompt=True)
print(f"    prompt 预览: {repr(text[-80:])}")

inputs = tokenizer(text, return_tensors="pt")

print(f"[4] 开始推理 max_new_tokens=80 ...")
with torch.no_grad():
    out = model.generate(
        **inputs,
        max_new_tokens=80,
        do_sample=True,
        temperature=0.7,
        top_p=0.9,
        pad_token_id=tokenizer.eos_token_id,
        eos_token_id=tokenizer.eos_token_id,
    )

gen = out[0, inputs["input_ids"].shape[1]:]
raw_ids = gen.tolist()
print(f"[5] 原始 token ids: {raw_ids[:20]}")
result = tokenizer.decode(gen, skip_special_tokens=True)
print(f"[6] 解码结果: {repr(result)}")
