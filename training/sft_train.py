# sft_train.py
# 监督微调（SFT）：加载预训练权重，用问答数据继续训练
#
# 全量微调：
#   python sft_train.py --data ./data/sft_mini.jsonl --epochs 3
# LoRA 微调（只训练 LoRA 参数）：
#   python sft_train.py --lora 1 --data ./data/sunwukong_mini.jsonl --epochs 10
import argparse
import glob
import math
import os
import re
from dataclasses import replace

import torch
import torch.nn as nn
from torch.optim import AdamW
from torch.utils.data import DataLoader
from tokenizers import Tokenizer

from config import TrainConfig
from model import GPTModel, convert_old_state_dict
from sft_dataset import SFTDataset, make_collate
from lora import apply_lora, save_lora


def pick_latest(ckpt_dir, pattern="step_*.pth"):
    files = glob.glob(os.path.join(ckpt_dir, pattern))
    if not files:
        raise FileNotFoundError(f"{ckpt_dir} 下没有 {pattern}")
    return max(files, key=lambda p: int(re.search(r"(\d+)", os.path.basename(p)).group(1)))


def build_scheduler(optimizer, total_steps, warmup=10):
    """微调步数少，warmup 也短；之后余弦衰减到初始学习率的 10%"""
    def lr_lambda(step):
        if step < warmup:
            return (step + 1) / warmup
        progress = (step - warmup) / max(1, total_steps - warmup)
        return 0.1 + 0.9 * 0.5 * (1 + math.cos(math.pi * progress))

    return torch.optim.lr_scheduler.LambdaLR(optimizer, lr_lambda)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--ckpt", default="", help="初始权重，不填则自动选预训练最新 checkpoint")
    parser.add_argument("--data", default="./data/sft_mini.jsonl")
    parser.add_argument("--epochs", type=int, default=3)
    parser.add_argument("--lr", type=float, default=5e-5, help="微调学习率，必须比预训练小")
    parser.add_argument("--batch_size", type=int, default=8)
    parser.add_argument("--max_seq_len", type=int, default=128)
    parser.add_argument("--lora", type=int, default=0, choices=[0, 1], help="1 = 只训练 LoRA 参数")
    parser.add_argument("--rank", type=int, default=8, help="LoRA 秩，经验值 4~16")
    parser.add_argument("--out_dir", default="./checkpoints_sft")
    parser.add_argument("--save_step", type=int, default=200)
    parser.add_argument("--log_step", type=int, default=5)
    args = parser.parse_args()

    cfg = TrainConfig()
    os.makedirs(args.out_dir, exist_ok=True)

    # ===== 1. 分词器与模型（词表/位置长度以 checkpoint 为准，避免形状对不上）=====
    tokenizer = Tokenizer.from_file(cfg.tokenizer_path)
    ckpt_path = args.ckpt or pick_latest(cfg.ckpt_dir)
    ckpt = torch.load(ckpt_path, map_location="cpu")
    state_dict = convert_old_state_dict(ckpt["model"])

    cfg = replace(
        cfg,
        vocab_size=state_dict["token_emb.weight"].shape[0],
        max_seq_len=state_dict["pos_emb.weight"].shape[0],
    )
    if tokenizer.get_vocab_size() != cfg.vocab_size:
        raise SystemExit(
            f"词表不一致：分词器={tokenizer.get_vocab_size()}，权重={cfg.vocab_size}。"
            "请确认 tokenizer.json 和 checkpoint 是同一次预训练产物。"
        )

    model = GPTModel(cfg).to(cfg.device)
    model.load_state_dict(state_dict)
    print(f"[sft] 初始权重 {ckpt_path}（预训练第 {ckpt.get('step')} 步）")
    print(f"[sft] device={cfg.device} 词表={cfg.vocab_size} 位置上限={cfg.max_seq_len}")

    # ===== 2. LoRA：冻结原参数，只留 LoRA 可训练 =====
    if args.lora:
        apply_lora(model, rank=args.rank)
        trainable = []
        for name, p in model.named_parameters():
            p.requires_grad = "lora" in name
            if p.requires_grad:
                trainable.append(p)
        total = sum(p.numel() for p in model.parameters())
        n_lora = sum(p.numel() for p in trainable)
        print(f"[lora] 总参数 {total / 1e6:.3f}M | LoRA 参数 {n_lora / 1e6:.3f}M "
              f"| 占比 {n_lora / total * 100:.2f}% | rank={args.rank}")
    else:
        trainable = [p for p in model.parameters() if p.requires_grad]
        print(f"[sft] 全量微调，可训练参数 {sum(p.numel() for p in trainable) / 1e6:.3f}M")

    # ===== 3. 数据 =====
    max_len = min(args.max_seq_len, cfg.max_seq_len)
    dataset = SFTDataset(args.data, cfg.tokenizer_path, max_len)
    loader = DataLoader(
        dataset,
        batch_size=args.batch_size,
        shuffle=True,
        num_workers=cfg.num_workers,
        collate_fn=make_collate(dataset.pad_id),
        drop_last=False,
    )
    print(f"[sft] 样本数={len(dataset)} max_len={max_len} batch={args.batch_size}")

    # ===== 4. 训练前自检：确认 user 部分被遮盖 =====
    x, y = next(iter(loader))
    kept = y[0][y[0] != -100]
    print(f"[check] 该样本 {y.shape[1]} 个位置中，参与 loss 的有 {int((y[0] != -100).sum())} 个")
    print(f"[check] 参与 loss 的文本：{tokenizer.decode(kept.tolist())[:60]!r}")

    optimizer = AdamW(trainable, lr=args.lr, weight_decay=0.01)
    total_steps = max(1, len(loader) * args.epochs)
    scheduler = build_scheduler(optimizer, total_steps)
    loss_fn = nn.CrossEntropyLoss(ignore_index=-100)

    use_amp = cfg.device.startswith("cuda")
    amp_dtype = torch.bfloat16 if cfg.use_bf16 else torch.float16
    scaler = torch.amp.GradScaler("cuda", enabled=use_amp and not cfg.use_bf16)

    # ===== 5. 训练循环 =====
    global_step = 0
    model.train()
    for epoch in range(args.epochs):
        for x, y in loader:
            x, y = x.to(cfg.device), y.to(cfg.device)

            with torch.amp.autocast("cuda", dtype=amp_dtype, enabled=use_amp):
                logits = model(x)
                loss = loss_fn(logits.reshape(-1, logits.size(-1)), y.reshape(-1))

            scaler.scale(loss).backward()
            scaler.unscale_(optimizer)
            torch.nn.utils.clip_grad_norm_(trainable, 1.0)
            scaler.step(optimizer)
            scaler.update()
            optimizer.zero_grad(set_to_none=True)
            scheduler.step()

            if global_step % args.log_step == 0:
                print(f"epoch {epoch + 1}/{args.epochs} step {global_step} "
                      f"loss={loss.item():.4f} lr={scheduler.get_last_lr()[0]:.2e}")
            global_step += 1

        # 每个 epoch 结束保存
        if args.lora:
            save_path = os.path.join(args.out_dir, f"lora_rank{args.rank}.pth")
            save_lora(model, save_path)
        else:
            save_path = os.path.join(args.out_dir, f"step_{global_step}.pth")
            torch.save({"model": model.state_dict(), "opt": optimizer.state_dict(), "step": global_step}, save_path)
        print(f"[sft] 已保存 {save_path}")

    print(f"训练结束，共 {global_step} 步，最终权重：{save_path}")


if __name__ == "__main__":
    main()
