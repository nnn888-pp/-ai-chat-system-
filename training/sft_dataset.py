# sft_dataset.py
# 监督微调数据集：问答格式 + Loss 遮盖（只对"答"的部分算 loss）
#
# 为什么不用 <|user|> 这类特殊 token：
#   分词器已经和预训练权重绑定了词表（30000），临时加特殊 token 会让词表变大，
#   导致昨天训好的权重加载不上。这里用普通文本标记"问："/"答："代替，
#   作用完全一样：告诉模型哪里是提问、哪里该回答。
import json

import torch
from tokenizers import Tokenizer
from torch.utils.data import Dataset

PROMPT_TMPL = "问：{}\n答："


class SFTDataset(Dataset):
    def __init__(self, jsonl_path, tokenizer_path, max_len):
        self.tok = Tokenizer.from_file(tokenizer_path)
        self.max_len = max_len
        self.samples = []

        with open(jsonl_path, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                msgs = json.loads(line)["messages"]
                # 只取第一轮：user 提问 + assistant 回答
                self.samples.append((msgs[0]["content"], msgs[1]["content"]))

        pad_id = self.tok.token_to_id("[PAD]")
        self.pad_id = 0 if pad_id is None else pad_id

    def __len__(self):
        return len(self.samples)

    def __getitem__(self, idx):
        question, answer = self.samples[idx]

        prompt_ids = self.tok.encode(PROMPT_TMPL.format(question)).ids
        # 末尾补一个换行，作为"回答结束"的信号
        answer_ids = self.tok.encode(answer + "\n").ids

        # 截断保护：保证至少留一半位置给答案，否则整条样本没有 loss
        if len(prompt_ids) + len(answer_ids) > self.max_len:
            keep = max(self.max_len // 2, 1)
            answer_ids = answer_ids[:keep]
            prompt_ids = prompt_ids[-(self.max_len - len(answer_ids)):]

        input_ids = prompt_ids + answer_ids
        # ✅ 核心：提问部分填 -100，不参与 loss；只有答案参与
        labels = [-100] * len(prompt_ids) + answer_ids

        return (
            torch.tensor(input_ids, dtype=torch.long),
            torch.tensor(labels, dtype=torch.long),
        )


def make_collate(pad_id):
    """动态 padding，labels 的填充位置保持 -100（不参与 loss）"""
    def collate(batch):
        max_len = max(len(x) for x, _ in batch)
        input_ids, labels = [], []
        for x, y in batch:
            pad = max_len - len(x)
            input_ids.append(torch.cat([x, torch.full((pad,), pad_id, dtype=torch.long)]))
            labels.append(torch.cat([y, torch.full((pad,), -100, dtype=torch.long)]))
        return torch.stack(input_ids), torch.stack(labels)

    return collate
