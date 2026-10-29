# chat.py
# 微调后的对话测试：和预训练不同，这次输入问题，模型应当作答而不是乱续写
#
# 全量 SFT 模型：
#   python chat.py --ckpt ./checkpoints_sft/step_xxx.pth --prompt "你是谁"
# LoRA 模型（base 用 SFT 权重）：
#   python chat.py --ckpt ./checkpoints_sft/step_xxx.pth --lora ./checkpoints_sft/lora_rank8.pth --prompt "你是谁"
import argparse
from dataclasses import replace

import torch
from tokenizers import Tokenizer

from config import TrainConfig
from model import GPTModel, convert_old_state_dict
from lora import apply_lora, load_lora

PROMPT_TMPL = "问：{}\n答："


@torch.no_grad()
def chat(model, tokenizer, question, cfg, max_new_tokens=60, top_k=10, temperature=0.8):
    model.eval()
    prompt = PROMPT_TMPL.format(question)
    ids = tokenizer.encode(prompt).ids
    x = torch.tensor(ids, dtype=torch.long, device=cfg.device)[None, :]

    for _ in range(max_new_tokens):
        logits = model(x[:, -cfg.max_seq_len:])[:, -1, :]
        if top_k > 0:
            values, indices = torch.topk(logits, min(top_k, logits.size(-1)))
            probs = torch.softmax(values / temperature, dim=-1)
            next_id = indices.gather(-1, torch.multinomial(probs, 1))
        else:
            next_id = torch.argmax(logits, dim=-1, keepdim=True)
        x = torch.cat([x, next_id], dim=-1)

        # 生成到换行就停，说明一句话说完了
        new_text = tokenizer.decode(x[0, len(ids):].tolist())
        if "\n" in new_text:
            return new_text.split("\n")[0]

    return tokenizer.decode(x[0, len(ids):].tolist())


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--ckpt", required=True)
    parser.add_argument("--lora", default="", help="LoRA 权重路径，不填则只用全量权重")
    parser.add_argument("--rank", type=int, default=8)
    parser.add_argument("--prompt", default="你是谁")
    parser.add_argument("--max_new_tokens", type=int, default=60)
    parser.add_argument("--top_k", type=int, default=10)
    parser.add_argument("--temperature", type=float, default=0.8)
    args = parser.parse_args()

    cfg = TrainConfig()
    tokenizer = Tokenizer.from_file(cfg.tokenizer_path)
    ckpt = torch.load(args.ckpt, map_location="cpu")
    state_dict = convert_old_state_dict(ckpt["model"])

    cfg = replace(
        cfg,
        vocab_size=state_dict["token_emb.weight"].shape[0],
        max_seq_len=state_dict["pos_emb.weight"].shape[0],
    )
    model = GPTModel(cfg).to(cfg.device)
    model.load_state_dict(state_dict)

    if args.lora:
        apply_lora(model, rank=args.rank)
        load_lora(model, args.lora)
        print(f"已加载 LoRA 权重 {args.lora}")

    print(f"已加载 {args.ckpt}")
    print("-" * 40)
    if args.prompt.strip():
        print(f"问：{args.prompt}")
        print(f"答：{chat(model, tokenizer, args.prompt, cfg, args.max_new_tokens, args.top_k, args.temperature)}")
    else:
        while True:
            q = input("问：")
            if q.strip().lower() in ("exit", "quit"):
                break
            print(f"答：{chat(model, tokenizer, q, cfg, args.max_new_tokens, args.top_k, args.temperature)}\n")
    print("-" * 40)
