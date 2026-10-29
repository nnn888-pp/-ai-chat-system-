# train.py
# 主训练入口：数据加载 → 模型 → 优化器/调度器 → 训练循环 → 日志 → 保存 checkpoint
# 支持断点续训：python train.py --resume
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
from torch.utils.tensorboard import SummaryWriter
from tqdm import tqdm

from config import TrainConfig
from dataset import TextDataset
from model import GPTModel


def get_lr_scheduler(optimizer, total_steps, warmup_steps, min_lr_ratio=0.0):
    """WarmUp 线性上升，之后余弦退火衰减"""

    def lr_lambda(step):
        if step < warmup_steps:
            return float(step) / float(max(1, warmup_steps))
        progress = float(step - warmup_steps) / float(max(1, total_steps - warmup_steps))
        progress = min(1.0, max(0.0, progress))
        cosine = 0.5 * (1.0 + math.cos(math.pi * progress))
        return max(min_lr_ratio, cosine)

    return torch.optim.lr_scheduler.LambdaLR(optimizer, lr_lambda)


def latest_checkpoint(ckpt_dir):
    files = glob.glob(os.path.join(ckpt_dir, "step_*.pth"))
    if not files:
        return None

    def step_of(path):
        m = re.search(r"step_(\d+)", os.path.basename(path))
        return int(m.group(1)) if m else -1

    return max(files, key=step_of)


def save_checkpoint(path, model, optimizer, scheduler, scaler, global_step):
    torch.save(
        {
            "model": model.state_dict(),
            "opt": optimizer.state_dict(),
            "sched": scheduler.state_dict(),
            "scaler": scaler.state_dict(),
            "step": global_step,
        },
        path,
    )


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--resume", nargs="?", const="auto", default=None,
                        help="断点续训：--resume 自动取最新；--resume path 指定文件")
    parser.add_argument("--epochs", type=int, default=None, help="临时覆盖 config.epochs")
    args = parser.parse_args()

    cfg = TrainConfig()
    if args.epochs is not None:
        cfg.epochs = args.epochs

    device = torch.device(cfg.device)
    os.makedirs(cfg.ckpt_dir, exist_ok=True)
    os.makedirs(cfg.log_dir, exist_ok=True)
    writer = SummaryWriter(cfg.log_dir)

    # 1. 数据集
    dataset = TextDataset(
        txt_path=cfg.train_txt,
        tokenizer_path=cfg.tokenizer_path,
        max_len=cfg.max_seq_len,
        max_tokens=cfg.max_tokens,
    )
    # 词表大小：config 填 0 就自动取分词器真实值；填了就必须一致
    real_vocab = dataset.tokenizer.get_vocab_size()
    if cfg.vocab_size not in (0, real_vocab):
        raise ValueError(
            f"config.vocab_size={cfg.vocab_size} 与分词器实际词表 {real_vocab} 不一致！"
        )
    cfg = replace(cfg, vocab_size=real_vocab)

    assert len(dataset) > 0, "语料太短，切不出任何样本，请增加 train.txt 内容"

    loader = DataLoader(
        dataset,
        batch_size=cfg.batch_size,
        shuffle=True,
        num_workers=cfg.num_workers,
        drop_last=True,
        pin_memory=(device.type == "cuda"),
    )

    # 2. 模型 / 优化器 / 调度器
    model = GPTModel(cfg).to(device)
    optimizer = AdamW(model.parameters(), lr=cfg.lr)
    total_train_steps = max(1, cfg.epochs * len(loader) // cfg.grad_accum_steps)
    scheduler = get_lr_scheduler(
        optimizer, total_train_steps, cfg.warmup_steps, min_lr_ratio=cfg.min_lr / cfg.lr
    )

    # 3. 混合精度：CPU 上自动关闭
    use_amp = device.type == "cuda"
    amp_dtype = torch.bfloat16 if cfg.use_bf16 else torch.float16
    scaler = torch.amp.GradScaler("cuda", enabled=use_amp and amp_dtype == torch.float16)

    # 4. 断点续训
    global_step = 0
    if args.resume:
        resume_path = latest_checkpoint(cfg.ckpt_dir) if args.resume == "auto" else args.resume
        if not resume_path:
            raise FileNotFoundError(f"{cfg.ckpt_dir} 下没有可续训的 step_*.pth")
        ckpt = torch.load(resume_path, map_location=device)
        model.load_state_dict(ckpt["model"])
        optimizer.load_state_dict(ckpt["opt"])
        if "sched" in ckpt:
            scheduler.load_state_dict(ckpt["sched"])
        if "scaler" in ckpt:
            scaler.load_state_dict(ckpt["scaler"])
        global_step = ckpt.get("step", 0)
        print(f"[resume] 从 {resume_path} 续训，已训练 {global_step} 步")

    print(f"[train] device={device} 参数量={sum(p.numel() for p in model.parameters()):,}")
    print(f"[train] vocab={real_vocab} 样本数={len(dataset)} batch数={len(loader)} "
          f"目标优化步数={total_train_steps}")
    if global_step >= total_train_steps:
        print("已训练的步数 >= 目标步数，无需继续。想多训就加大 --epochs")
        writer.close()
        return

    loss_fn = nn.CrossEntropyLoss()
    pbar = tqdm(total=total_train_steps, initial=global_step, desc="train")
    log_loss, log_cnt = 0.0, 0
    model.train()

    for epoch in range(cfg.epochs):
        if global_step >= total_train_steps:
            break
        for x, y in loader:
            x = x.to(device, non_blocking=True)
            y = y.to(device, non_blocking=True)

            # 前向传播
            with torch.amp.autocast(device_type=device.type, dtype=amp_dtype, enabled=use_amp):
                logits = model(x)                       # [B, T, vocab]
                loss = loss_fn(logits.reshape(-1, logits.size(-1)), y.reshape(-1))

            # 反向传播（梯度累积：每 accum 个微批才更新一次）
            scaler.scale(loss / cfg.grad_accum_steps).backward()
            global_step += 1

            if global_step % cfg.grad_accum_steps == 0:
                scaler.unscale_(optimizer)
                torch.nn.utils.clip_grad_norm_(model.parameters(), cfg.grad_clip_norm)
                scaler.step(optimizer)
                scaler.update()
                optimizer.zero_grad(set_to_none=True)
                scheduler.step()

            # 日志
            log_loss += loss.item()
            log_cnt += 1
            if global_step % cfg.log_step == 0:
                avg_loss = log_loss / log_cnt
                writer.add_scalar("train/loss", avg_loss, global_step)
                writer.add_scalar("train/lr", scheduler.get_last_lr()[0], global_step)
                pbar.set_postfix({"loss": f"{avg_loss:.4f}",
                                  "lr": f"{scheduler.get_last_lr()[0]:.1e}"})
                log_loss, log_cnt = 0.0, 0

            # 保存 checkpoint
            if global_step % cfg.save_step == 0:
                save_path = os.path.join(cfg.ckpt_dir, f"step_{global_step}.pth")
                save_checkpoint(save_path, model, optimizer, scheduler, scaler, global_step)
                pbar.write(f"已保存 {save_path}")

            pbar.update(1)
            if global_step >= total_train_steps:
                break

    pbar.close()
    final_path = os.path.join(cfg.ckpt_dir, f"step_{global_step}.pth")
    save_checkpoint(final_path, model, optimizer, scheduler, scaler, global_step)
    writer.close()
    print(f"训练结束，共 {global_step} 步，最终权重：{final_path}")


if __name__ == "__main__":
    main()
