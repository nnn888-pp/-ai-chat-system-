# sft_qwen_lora.py
# 模型3：基于开源模型 + 封装库（transformers + peft）做 LoRA 微调
# 改编自课程参考实现 trainer_other.py，模型换成中文效果更好的 Qwen2.5
#
# 用法（魔塔 GPU 实例里）：
#   python sft_qwen_lora.py --model ./models/qwen2.5-1.5b --data ./data/sunwukong_mini.jsonl
import argparse
import json

import datasets  # noqa: F401  # Windows 下 pyarrow/torch 的 DLL 冲突规避
import torch
from datasets import Dataset
from peft import LoraConfig, TaskType, get_peft_model
from transformers import (
    AutoModelForCausalLM,
    AutoTokenizer,
    DataCollatorForSeq2Seq,
    Trainer,
    TrainingArguments,
)

MAX_LEN = 384


def build_dataset(path, tokenizer):
    rows = []
    with open(path, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                rows.append(json.loads(line))
    ds = Dataset.from_list(rows)

    def process(example):
        msgs = example["messages"]
        # 用模型自带的聊天模板拼接提问部分（训练与推理必须一致！）
        prompt = tokenizer.apply_chat_template(
            msgs[:-1], tokenize=False, add_generation_prompt=True
        )
        answer = msgs[-1]["content"] + tokenizer.eos_token

        p = tokenizer(prompt, add_special_tokens=False)
        r = tokenizer(answer, add_special_tokens=False)

        input_ids = (p["input_ids"] + r["input_ids"])[:MAX_LEN]
        # ✅ 只对助手回复计算 loss，提问部分遮盖为 -100
        labels = ([-100] * len(p["input_ids"]) + r["input_ids"])[:MAX_LEN]

        return {
            "input_ids": input_ids,
            "attention_mask": [1] * len(input_ids),
            "labels": labels,
        }

    ds = ds.map(process, remove_columns=ds.column_names)
    # 丢掉被截断到没有任何答案 token 的样本（否则 loss 为 nan）
    ds = ds.filter(lambda x: any(l != -100 for l in x["labels"]))
    return ds


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--model", default="./models/qwen2.5-1.5b")
    parser.add_argument("--data", default="./data/sunwukong_mini.jsonl")
    parser.add_argument("--out", default="./output/qwen_lora_sunwukong")
    parser.add_argument("--epochs", type=int, default=3)
    parser.add_argument("--rank", type=int, default=8)
    parser.add_argument("--lr", type=float, default=1e-4)
    parser.add_argument("--batch_size", type=int, default=2)
    parser.add_argument("--grad_accum", type=int, default=4)
    args = parser.parse_args()

    tokenizer = AutoTokenizer.from_pretrained(args.model, trust_remote_code=True)
    if tokenizer.pad_token is None:
        tokenizer.pad_token = tokenizer.eos_token

    model = AutoModelForCausalLM.from_pretrained(
        args.model, torch_dtype=torch.bfloat16, trust_remote_code=True
    )
    model.enable_input_require_grads()  # 开启梯度检查点时必须调用

    train_ds = build_dataset(args.data, tokenizer)
    print(f"[data] 样本数={len(train_ds)}")

    config = LoraConfig(
        task_type=TaskType.CAUSAL_LM,
        # 注意力的 q/k/v/o 全部注入（课程要求优先注入 Attention 层）
        target_modules=["q_proj", "k_proj", "v_proj", "o_proj",
                        "gate_proj", "up_proj", "down_proj"],
        inference_mode=False,
        r=args.rank,
        lora_alpha=32,
        lora_dropout=0.05,
    )
    model = get_peft_model(model, config)
    model.print_trainable_parameters()

    training_args = TrainingArguments(
        output_dir=args.out,
        per_device_train_batch_size=args.batch_size,
        gradient_accumulation_steps=args.grad_accum,
        logging_steps=5,
        num_train_epochs=args.epochs,
        save_steps=100,
        save_total_limit=2,
        learning_rate=args.lr,
        bf16=True,
        gradient_checkpointing=True,
        report_to="none",
    )

    trainer = Trainer(
        model=model,
        args=training_args,
        train_dataset=train_ds,
        data_collator=DataCollatorForSeq2Seq(tokenizer=tokenizer, padding=True),
    )
    trainer.train()

    # peft 模型 save_pretrained 只保存 LoRA 权重（adapter）
    model.save_pretrained(args.out)
    tokenizer.save_pretrained(args.out)
    print(f"LoRA 权重已保存到 {args.out}")
