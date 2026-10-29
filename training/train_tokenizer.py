# train_tokenizer.py
# 在自己的语料上训练 BPE 分词器（ByteLevel），词表默认 30000
# 用法：
#   python train_tokenizer.py --corpus ./data/train.txt --vocab_size 30000
#   想用更小的语料快速试：--max_mb 20
import argparse
import os
import shutil

from tokenizers import Tokenizer
from tokenizers.decoders import ByteLevel as ByteLevelDecoder
from tokenizers.models import BPE
from tokenizers.pre_tokenizers import ByteLevel
from tokenizers.trainers import BpeTrainer


def line_iterator(path, max_mb):
    limit = int(max_mb * 1024 * 1024)
    size = 0
    with open(path, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            size += len(line.encode("utf-8")) + 1
            yield line
            if size >= limit:
                return


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--corpus", default="./data/train.txt")
    parser.add_argument("--vocab_size", type=int, default=8000)
    parser.add_argument("--output", default="./tokenizer/tokenizer.json")
    parser.add_argument("--max_mb", type=float, default=50.0, help="只用前多少 MB 语料训练分词器")
    args = parser.parse_args()

    os.makedirs(os.path.dirname(os.path.abspath(args.output)), exist_ok=True)
    # 覆盖前先备份，避免把旧分词器弄丢
    if os.path.exists(args.output):
        backup = args.output.replace(".json", ".bak.json")
        shutil.copyfile(args.output, backup)
        print(f"已备份旧分词器 → {backup}")

    tokenizer = Tokenizer(BPE(unk_token="[UNK]"))
    tokenizer.pre_tokenizer = ByteLevel()
    tokenizer.decoder = ByteLevelDecoder()

    trainer = BpeTrainer(
        vocab_size=args.vocab_size,
        special_tokens=["[UNK]", "[CLS]", "[SEP]", "[PAD]", "[MASK]"],
        # 必须把 256 个字节全部放进初始词表，否则语料里没出现过的字节会变成 [UNK]，
        # 解码时还原成 �，编解码不再可逆（这是之前中文变乱码的根因）
        initial_alphabet=ByteLevel.alphabet(),
        show_progress=True,
    )

    print(f"开始训练分词器：语料={args.corpus} 词表={args.vocab_size}")
    tokenizer.train_from_iterator(
        line_iterator(args.corpus, args.max_mb), trainer=trainer
    )
    tokenizer.save(args.output)
    print(f"完成，实际词表大小={tokenizer.get_vocab_size()} → {args.output}")

    # 随手做一次编解码自检
    test = "人工智能是计算机科学的一个重要分支"
    enc = tokenizer.encode(test)
    print("tokens:", enc.tokens[:30])
    print("decode:", tokenizer.decode(enc.ids))


if __name__ == "__main__":
    main()
