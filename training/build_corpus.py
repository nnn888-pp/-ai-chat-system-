# build_corpus.py
# 把下载的原始语料（三国演义/西游记/豆棚闲话/成语词典）整理成 train_v2.txt
# 原始文件放在 ./data/raw/，输出到 ./data/train_v2.txt（一行一段，繁体统一转简体）
import json
import os
import random

RAW_DIR = "./data/raw"
OUT_PATH = "./data/train_v2.txt"
NOVELS = ["sanguo.txt", "xiyou.txt", "doupeng.txt"]


def load_ts_map(path):
    """读取 OpenCC 的繁→简字符映射：每行 “繁体<TAB>简体1 简体2 ...”"""
    mapping = {}
    with open(path, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            parts = line.split("\t")
            if len(parts) < 2:
                continue
            mapping[parts[0]] = parts[1].split(" ")[0]
    return mapping


def to_simplified(text, ts_map):
    return "".join(ts_map.get(ch, ch) for ch in text)


def clean_novel(path):
    """去掉 Project Gutenberg 的英文页首页尾，只留正文"""
    with open(path, "r", encoding="utf-8", errors="ignore") as f:
        text = f.read()

    start = text.find("*** START OF")
    if start != -1:
        text = text[text.find("\n", start) + 1:]
    end = text.find("*** END OF")
    if end != -1:
        text = text[:end]

    for line in text.splitlines():
        line = line.strip().replace("\u3000", " ")
        if len(line) < 6:
            continue
        # 英文页眉页脚、版权说明这类行直接丢掉
        ascii_letters = sum(ch.isascii() and ch.isalpha() for ch in line)
        if ascii_letters / len(line) > 0.3:
            continue
        yield line


def clean_idioms(path):
    with open(path, "r", encoding="utf-8") as f:
        data = json.load(f)
    for item in data:
        word = (item.get("word") or "").strip()
        expl = (item.get("explanation") or "").strip()
        example = (item.get("example") or "").strip()
        if not word or not expl:
            continue
        yield f"{word}：{expl}"
        if example:
            yield example


def main():
    os.makedirs(os.path.dirname(os.path.abspath(OUT_PATH)), exist_ok=True)
    ts_map = load_ts_map(os.path.join(RAW_DIR, "TSCharacters.txt"))

    lines, seen = [], set()

    for name in NOVELS:
        path = os.path.join(RAW_DIR, name)
        if not os.path.exists(path):
            print(f"[skip] 缺少 {path}")
            continue
        n = 0
        for line in clean_novel(path):
            line = to_simplified(line, ts_map)
            if line not in seen:
                seen.add(line)
                lines.append(line)
                n += 1
        print(f"[novel] {name}: {n} 行")

    idiom_path = os.path.join(RAW_DIR, "idiom.json")
    if os.path.exists(idiom_path):
        n = 0
        for line in clean_idioms(idiom_path):
            line = to_simplified(line.strip(), ts_map)
            if len(line) >= 6 and line not in seen:
                seen.add(line)
                lines.append(line)
                n += 1
        print(f"[idiom] {n} 行")

    random.seed(42)
    random.shuffle(lines)

    with open(OUT_PATH, "w", encoding="utf-8") as f:
        for line in lines:
            f.write(line + "\n")

    size = os.path.getsize(OUT_PATH)
    print(f"完成：{len(lines)} 行，{size / 1024 / 1024:.2f}MB → {OUT_PATH}")


if __name__ == "__main__":
    main()
