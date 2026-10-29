"""精准诊断 Qwen 基座乱码根因 —— 逐层打印"""
from transformers import AutoModelForCausalLM, AutoTokenizer
import torch

model_path = r"C:\Users\ping1\Desktop\ai-chat-system\models_store\models\Qwen--Qwen2.5-1.5B\snapshots\master"

print("=" * 60)
print("[Step 1] 加载 tokenizer")
print("=" * 60)
tok = AutoTokenizer.from_pretrained(model_path, local_files_only=True, trust_remote_code=True)
print(f"  eos_token = {tok.eos_token!r}  id = {tok.eos_token_id}")
print(f"  pad_token = {tok.pad_token!r}  id = {tok.pad_token_id}")
print(f"  chat_template 存在 = {tok.chat_template is not None}")
print(f"  vocab_size = {tok.vocab_size}")

print("\n" + "=" * 60)
print("[Step 2] 加载模型")
print("=" * 60)
model = AutoModelForCausalLM.from_pretrained(
    model_path, local_files_only=True, trust_remote_code=True, torch_dtype=torch.float32
)
model.eval()
print(f"  模型加载完成，参数 dtype = {next(model.parameters()).dtype}")

print("\n" + "=" * 60)
print("[Step 3] 用 chat_template 拼 prompt")
print("=" * 60)
msgs = [{"role": "user", "content": "你好"}]
prompt = tok.apply_chat_template(msgs, tokenize=False, add_generation_prompt=True)
print(f"  prompt = {prompt!r}")

inputs = tok(prompt, return_tensors="pt")
print(f"  input_ids shape = {inputs['input_ids'].shape}")
print(f"  input_ids = {inputs['input_ids'][0].tolist()}")

print("\n" + "=" * 60)
print("[Step 4] 推理：只生成前 5 个 token，看每个 token id 是什么")
print("=" * 60)
with torch.no_grad():
    # 先跑一次 forward，看 logits 分布
    logits = model(**inputs).logits[0, -1, :]
    top5 = torch.topk(logits, 5)
    print("  第一个位置 top-5 候选 token:")
    for score, tid in zip(top5.values.tolist(), top5.indices.tolist()):
        decoded = tok.decode([tid], skip_special_tokens=False)
        print(f"    id={tid:>6}  score={score:>8.2f}  decoded={decoded!r}")

    # 然后正常生成 10 个 token
    out = model.generate(
        **inputs,
        max_new_tokens=10,
        do_sample=False,  # greedy，排除采样干扰
        pad_token_id=tok.eos_token_id,
        eos_token_id=tok.eos_token_id,
    )

gen_ids = out[0, inputs["input_ids"].shape[1]:].tolist()
print(f"\n  greedy 生成的 token ids (前10): {gen_ids}")
for tid in gen_ids:
    decoded_no_skip = tok.decode([tid], skip_special_tokens=False)
    decoded_skip = tok.decode([tid], skip_special_tokens=True)
    print(f"    id={tid:>6}  skip_special=False → {decoded_no_skip!r}  skip_special=True → {decoded_skip!r}")

text = tok.decode(out[0][inputs["input_ids"].shape[1]:], skip_special_tokens=True)
print(f"\n  完整解码结果: {text!r}")

print("\n" + "=" * 60)
print("[Step 5] 同样的输入，用 sampling 生成 30 个 token")
print("=" * 60)
torch.manual_seed(42)
with torch.no_grad():
    out2 = model.generate(
        **inputs,
        max_new_tokens=30,
        do_sample=True,
        temperature=0.7,
        top_p=0.9,
        pad_token_id=tok.eos_token_id,
        eos_token_id=tok.eos_token_id,
    )

gen2 = out2[0, inputs["input_ids"].shape[1]:].tolist()
text2 = tok.decode(out2[0][inputs["input_ids"].shape[1]:], skip_special_tokens=True)
print(f"  sampled 输出 ids: {gen2}")
print(f"  sampled 输出文本: {text2!r}")
