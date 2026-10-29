# prepare_data.py
# 把魔塔下载的 jsonl / txt 语料抽取成 train.txt（纯文本，一行一段）
# 用法：
#   python prepare_data.py --input ./data/zhixi --output ./data/train.txt --max_mb 100
import argparse
import glob
import json
import os

TEXT_KEYS = ("txt", "text", "content", "completion", "document")


def iter_docs(path):
    """遍历单文件或目录下的 jsonl/json/txt，逐条产出纯文本"""
    if os.path.isfile(path):
        files = [path]
    else:
        files = sorted(glob.glob(os.path.join(path, "**", "*"), recursive=True))

    for fp in files:
        if os.path.isdir(fp):
            continue
        name = fp.lower()
        if name.endswith((".jsonl", ".json", ".jsonlines")):
            with open(fp, "r", encoding="utf-8", errors="ignore") as f:
                for line in f:
                    line = line.strip()
                    if not line:
                        continue
                    try:
                        obj = json.loads(line)
                    except json.JSONDecodeError:
                        continue
                    if isinstance(obj, str):
                        yield obj
                    elif isinstance(obj, dict):
                        for key in TEXT_KEYS:
                            if isinstance(obj.get(key), str) and obj[key].strip():
                                yield obj[key]
                                break
        elif name.endswith(".txt"):
            with open(fp, "r", encoding="utf-8", errors="ignore") as f:
                for line in f:
                    line = line.strip()
                    if line:
                        yield line
        else:
            print(f"[skip] 不支持的文件类型（parquet 需先转 jsonl）：{fp}")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", required=True, help="下载的语料目录或单个文件")
    parser.add_argument("--output", default="./data/train.txt")
    parser.add_argument("--max_mb", type=float, default=100.0, help="写出的文本上限（MB）")
    parser.add_argument("--min_chars", type=int, default=20, help="过滤过短的文本")
    args = parser.parse_args()

    os.makedirs(os.path.dirname(os.path.abspath(args.output)), exist_ok=True)
    limit = int(args.max_mb * 1024 * 1024)

    written, docs = 0, 0
    with open(args.output, "w", encoding="utf-8") as out:
        for doc in iter_docs(args.input):
            doc = doc.strip()
            if len(doc) < args.min_chars:
                continue
            doc = doc.replace("\r", " ").replace("\n", " ")   # 一行一段
            out.write(doc + "\n")
            written += len(doc.encode("utf-8")) + 1
            docs += 1
            if written >= limit:
                print(f"达到 {args.max_mb}MB 上限，提前停止")
                break

    print(f"完成：{docs} 段，约 {written / 1024 / 1024:.1f}MB → {args.output}")


if __name__ == "__main__":
    main()
