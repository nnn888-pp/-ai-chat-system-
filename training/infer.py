# infer.py
# 预训练模型效果测试：只能「续写」，不能对话
import argparse
import glob
import os
import re
from dataclasses import replace

import torch
from tokenizers import Tokenizer

from config import TrainConfig
from model import GPTModel, convert_old_state_dict


def pick_latest_ckpt(ckpt_dir):
    files = glob.glob(os.path.join(ckpt_dir, "step_*.pth"))
    if not files:
        raise FileNotFoundError(f"{ckpt_dir} 下没有 step_*.pth，请先运行 train.py")

    def step_of(path):
        m = re.search(r"step_(\d+)", os.path.basename(path))
        return int(m.group(1)) if m else -1

    return max(files, key=step_of)


@torch.no_grad()
def generate(model, tokenizer, prompt, cfg, max_new_tokens=64, top_k=20, temperature=0.8):
    device = torch.device(cfg.device)
    tokens = tokenizer.encode(prompt).ids
    x = torch.tensor(tokens, dtype=torch.long, device=device)[None, :]

    model.eval()
    for _ in range(max_new_tokens):
        x_cond = x[:, -cfg.max_seq_len:]
        logits = model(x_cond)[:, -1, :]          # 取最后一个位置

        if top_k > 0:
            # 只在概率最高的 top_k 个 token 里采样，避免生成乱码
            values, indices = torch.topk(logits, min(top_k, logits.size(-1)))
            probs = torch.softmax(values / temperature, dim=-1)
            next_id = indices.gather(-1, torch.multinomial(probs, 1))
        else:
            next_id = torch.argmax(logits, dim=-1, keepdim=True)

        x = torch.cat([x, next_id], dim=-1)

    return tokenizer.decode(x[0].cpu().tolist())


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--prompt", type=str, default="人工智能是")
    parser.add_argument("--ckpt", type=str, default="", help="不填则自动选步数最大的 checkpoint")
    parser.add_argument("--max_new_tokens", type=int, default=64)
    parser.add_argument("--top_k", type=int, default=20, help="0 = 贪心解码")
    parser.add_argument("--temperature", type=float, default=0.8)
    args = parser.parse_args()

    cfg = TrainConfig()
    tokenizer = Tokenizer.from_file(cfg.tokenizer_path)
    cfg = replace(cfg, vocab_size=tokenizer.get_vocab_size())

    ckpt_path = args.ckpt or pick_latest_ckpt(cfg.ckpt_dir)
    model = GPTModel(cfg).to(cfg.device)
    ckpt = torch.load(ckpt_path, map_location=cfg.device)
    model.load_state_dict(convert_old_state_dict(ckpt["model"]))
    print(f"已加载 {ckpt_path}（第 {ckpt.get('step')} 步）")

    print("-" * 40)
    print(generate(model, tokenizer, args.prompt, cfg,
                   args.max_new_tokens, args.top_k, args.temperature))
    print("-" * 40)
