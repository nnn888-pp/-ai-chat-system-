# dataset.py
# 文本编码 + 自回归数据集（核心：输入取 [:-1]，标签取 [1:]）
from array import array

import numpy as np
import torch
from torch.utils.data import Dataset
from tokenizers import Tokenizer


class TextDataset(Dataset):
    def __init__(self, txt_path, tokenizer_path, max_len, max_tokens=20_000_000):
        # 加载自己训练的分词器
        self.tokenizer = Tokenizer.from_file(tokenizer_path)
        self.max_len = max_len

        # 分块读取 + 分块编码，避免一次性 read() 把大语料读进内存
        ids = array("i")
        buf, buf_chars = [], 0
        with open(txt_path, "r", encoding="utf-8") as f:
            for line in f:
                buf.append(line)
                buf_chars += len(line)
                if buf_chars >= 2_000_000:          # 约 2MB 文本编码一次
                    ids.extend(self.tokenizer.encode("".join(buf)).ids)
                    buf, buf_chars = [], 0
                    if len(ids) >= max_tokens:
                        break
            if buf and len(ids) < max_tokens:
                ids.extend(self.tokenizer.encode("".join(buf)).ids)

        # 用 int32 numpy 数组存 token，比 Python list 省 7 倍内存
        self.tokens = np.frombuffer(ids, dtype=np.int32)
        print(f"[dataset] token数={len(self.tokens)}  "
              f"最大样本长度={self.max_len}  样本数={len(self)}")

    def __len__(self):
        # 每个样本需要 max_len+1 个 token（多出来的一位用来做标签）
        return (len(self.tokens) - 1) // self.max_len

    def __getitem__(self, idx):
        start = idx * self.max_len
        end = start + self.max_len + 1
        chunk = self.tokens[start:end].astype(np.int64)

        # 自回归关键：输入是前 N 个，标签整体后移一位
        x = torch.from_numpy(chunk[:-1])
        y = torch.from_numpy(chunk[1:])
        return x, y
