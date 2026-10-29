# model.py
# Decoder-only Transformer（GPT 结构）
#
# 注意力层用 q/k/v/o 四个独立 Linear（而不是 nn.MultiheadAttention），原因：
#   nn.MultiheadAttention 内部直接使用权重做函数式调用，会绕过 out_proj 模块，
#   导致 LoRA 挂上去也不生效。拆开后 q/k/v/o 才能被 LoRA 正常注入。
import math

import torch
import torch.nn as nn
import torch.nn.functional as F


class Attention(nn.Module):
    def __init__(self, embed_dim, n_heads):
        super().__init__()
        assert embed_dim % n_heads == 0
        self.n_heads = n_heads
        self.head_dim = embed_dim // n_heads
        self.q_proj = nn.Linear(embed_dim, embed_dim)
        self.k_proj = nn.Linear(embed_dim, embed_dim)
        self.v_proj = nn.Linear(embed_dim, embed_dim)
        self.out_proj = nn.Linear(embed_dim, embed_dim)

    def forward(self, x, mask):
        B, T, _ = x.shape
        q = self.q_proj(x).view(B, T, self.n_heads, self.head_dim).transpose(1, 2)
        k = self.k_proj(x).view(B, T, self.n_heads, self.head_dim).transpose(1, 2)
        v = self.v_proj(x).view(B, T, self.n_heads, self.head_dim).transpose(1, 2)

        attn = torch.matmul(q, k.transpose(-2, -1)) / math.sqrt(self.head_dim)
        attn = attn + mask                       # 因果掩码，禁止看到未来
        attn = F.softmax(attn, dim=-1)

        out = torch.matmul(attn, v).transpose(1, 2).reshape(B, T, -1)
        return self.out_proj(out)


class TransformerBlock(nn.Module):
    def __init__(self, embed_dim, n_heads):
        super().__init__()
        self.attn = Attention(embed_dim, n_heads)
        self.ln1 = nn.LayerNorm(embed_dim)
        self.ln2 = nn.LayerNorm(embed_dim)
        self.ffn = nn.Sequential(
            nn.Linear(embed_dim, embed_dim * 4),
            nn.GELU(),
            nn.Linear(embed_dim * 4, embed_dim),
        )

    def forward(self, x, mask):
        attn_out = self.attn(x, mask)
        x = self.ln1(x + attn_out)
        ffn_out = self.ffn(x)
        x = self.ln2(x + ffn_out)
        return x


class GPTModel(nn.Module):
    def __init__(self, cfg):
        super().__init__()
        self.cfg = cfg
        self.token_emb = nn.Embedding(cfg.vocab_size, cfg.embed_dim)
        self.pos_emb = nn.Embedding(cfg.max_seq_len, cfg.embed_dim)
        self.blocks = nn.Sequential(*[
            TransformerBlock(cfg.embed_dim, cfg.n_heads) for _ in range(cfg.n_layers)
        ])
        self.ln_final = nn.LayerNorm(cfg.embed_dim)
        self.head = nn.Linear(cfg.embed_dim, cfg.vocab_size)

    def forward(self, idx):
        B, T = idx.shape
        pos = torch.arange(0, T, device=idx.device)[None, :]
        x = self.token_emb(idx) + self.pos_emb(pos)
        mask = torch.full((T, T), float("-inf"), device=idx.device).triu(1)
        for block in self.blocks:
            x = block(x, mask)
        x = self.ln_final(x)
        return self.head(x)


def convert_old_state_dict(state_dict):
    """兼容改版前的 checkpoint：把 in_proj_weight 拆成 q/k/v 三个投影的权重"""
    if "blocks.0.attn.in_proj_weight" not in state_dict:
        return state_dict

    sd = dict(state_dict)
    i = 0
    while f"blocks.{i}.attn.in_proj_weight" in sd:
        w = sd.pop(f"blocks.{i}.attn.in_proj_weight")
        b = sd.pop(f"blocks.{i}.attn.in_proj_bias", None)
        n = w.shape[0] // 3
        sd[f"blocks.{i}.attn.q_proj.weight"] = w[:n]
        sd[f"blocks.{i}.attn.k_proj.weight"] = w[n:2 * n]
        sd[f"blocks.{i}.attn.v_proj.weight"] = w[2 * n:]
        if b is not None:
            sd[f"blocks.{i}.attn.q_proj.bias"] = b[:n]
            sd[f"blocks.{i}.attn.k_proj.bias"] = b[n:2 * n]
            sd[f"blocks.{i}.attn.v_proj.bias"] = b[2 * n:]
        i += 1
    return sd
