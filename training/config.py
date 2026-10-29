# config.py
# 预训练配置文件：所有超参数集中管理
from dataclasses import dataclass

import torch


@dataclass
class TrainConfig:
    # ===== 基础配置 =====
    # 0 = 自动从 tokenizer.json 读取词表大小（推荐，永远不会写错）
    # 想写死也行，写大了浪费参数，写小了直接报 index out of range
    vocab_size: int = 0
    max_seq_len: int = 128          # 本地调试 128；上 GPU 可改 512
    batch_size: int = 8
    grad_accum_steps: int = 2       # 梯度累积，变相放大 batch
    epochs: int = 6                 # 小语料多跑几轮；大语料 1~2 轮即可

    # ===== 学习率：WarmUp + 余弦退火 =====
    lr: float = 3e-4
    warmup_steps: int = 20
    min_lr: float = 1e-5

    # ===== 混合精度 / 梯度裁剪 =====
    use_bf16: bool = True           # 仅 CUDA 下生效；CPU 自动关闭 AMP
    grad_clip_norm: float = 1.0

    # ===== 模型结构（Decoder-only GPT 式 Transformer）=====
    n_layers: int = 6
    n_heads: int = 8
    embed_dim: int = 256

    # ===== 保存与日志 =====
    save_step: int = 200
    log_step: int = 20
    ckpt_dir: str = "./checkpoints_v2"
    log_dir: str = "./runs_v2"

    # ===== 数据 =====
    train_txt: str = "./data/train_v2.txt"
    tokenizer_path: str = "./tokenizer/tokenizer.json"
    # 最多编码多少个 token（防止 1G 语料把内存撑爆）
    # CPU 训练约 0.23 秒/步（batch 8 × 128），150 万 token ≈ 1500 步/轮
    max_tokens: int = 1_500_000

    # ===== 设备 =====
    device: str = "cuda" if torch.cuda.is_available() else "cpu"
    num_workers: int = 2 if torch.cuda.is_available() else 0
