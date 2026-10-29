# AI 聊天对话系统

支持**多模型接入**的聊天系统：既可接入远端第三方大模型（OpenAI 兼容协议），也能直接加载本地训练模型（自研 GPT 的 `.pth` 预训练/全量微调/LoRA 权重，以及 Qwen2.5 + LoRA adapter）。本地模型通过扫描目录自动识别加载，新增模型无需改代码。

- 前端：Vue 3 + Vite
- 后端：FastAPI + SQLAlchemy
- 数据库：SQLite（改连接串即可切 MySQL）
- 推理：OpenAI 兼容 API / PyTorch / HuggingFace Transformers / PEFT

---

## 功能

| 模块 | 能力 |
| --- | --- |
| 账号 | 注册、登录、退出；密码前端 SHA-256 加盐传输，后端 bcrypt 存储 |
| 个人信息 | 修改昵称、邮箱、头像 |
| 密码 | 修改密码（校验原密码、禁止新旧相同，改后需重新登录） |
| 对话 | 新建、重命名、删除、切换模型；删除时同步清理消息 |
| 消息 | 发送、持久化、上下文续聊、复制回复、清空会话、失败提示 |
| 模型 | 列表 / 状态 / 刷新；对话内自由切换；本地目录自动扫描 |

---

## 目录结构

```
ai-chat-system/
├─ backend/                 # FastAPI 后端
│  ├─ app/
│  │  ├─ api/               # auth / users / conversations / messages / models
│  │  ├─ services/          # auth / chat / model 业务逻辑
│  │  ├─ providers/         # remote_openai / local_pt / qwen_lora / mock / registry
│  │  ├─ models/            # ORM：User / Conversation / Message
│  │  ├─ utils/             # 密码哈希、JWT
│  │  └─ main.py            # 入口
│  ├─ scripts/              # 接口与模型自测脚本
│  ├─ requirements.txt
│  └─ .env.example
├─ frontend/                # Vue 3 前端
│  └─ src/{api,router,store,utils,views,style.css}
├─ models_store/            # 本地模型注册目录（运行时扫描，权重不入库）
├─ training/                # 预训练 / SFT / LoRA 训练脚本与语料
└─ docs/                    # PRD、技术方案、API 设计
```

---

## 快速开始

### 1. 后端

```bash
cd backend
python -m venv .venv
.venv\Scripts\activate          # Windows；Linux/macOS 用 source .venv/bin/activate
pip install -r requirements.txt
copy .env.example .env          # 填写 SECRET_KEY 与远端模型 api_key
uvicorn app.main:app --reload --port 8000
```

接口文档：<http://127.0.0.1:8000/docs>

`.env` 关键配置：

| 键 | 说明 |
| --- | --- |
| `DATABASE_URL` | 默认 `sqlite:///./app.db`；切 MySQL 改这一行 |
| `SECRET_KEY` | JWT 签名密钥，务必改成随机长串 |
| `SHA256_SALT` | 前端密码预处理使用的盐，需与 `frontend/src/utils/crypto.js` 一致 |
| `REMOTE_MODELS_JSON` | 远端模型数组（OpenAI 兼容协议：`base_url` / `api_key` / `model`） |
| `LOCAL_MODELS_DIR` | 本地模型目录，默认 `../models_store` |

### 2. 前端

```bash
cd frontend
npm install
npm run dev        # http://localhost:5173，/api 已代理到 8000
```

在登录页注册账号后使用。注意：密码由前端先做 SHA-256（加盐），直接用接口明文注册的账号在前端登录会失败。

---

## 已接入模型

| key | 展示名 | 类型 | 权重位置 |
| --- | --- | --- | --- |
| `remote:deepseek-chat` | DeepSeek V3（远端） | 远端 API | 云端，Key 存 `backend/.env` |
| `local:pretrain-v2` | 小GPT预训练(三国演义+西游记) | 自研 GPT | `training/checkpoints_v2/step_1894.pth` |
| `local:sft-v2` | 小GPT全量SFT | 自研 GPT | `training/checkpoints_sft_v2/step_18.pth` |
| `local:lora-v2-wukong` | 小GPT LoRA SFT (孙悟空) | 自研 GPT + LoRA | `training/checkpoints_lora_v2/lora_rank8.pth` |
| `local:qwen-base` | Qwen2.5-1.5B（基座） | HuggingFace | `models_store/models/Qwen--Qwen2.5-1.5B/` |
| `local:qwen-lora-wukong` | Qwen2.5-1.5B + 孙悟空 LoRA | HF + PEFT | `models_store/qwen-lora-wukong/` |

权重体积较大，未纳入 git，需本地放置。

---

## 接入自己的模型

在 `models_store/` 下新建目录，放入 `model_config.json`，后端启动或点击「刷新模型」时自动识别。

自研小 GPT（原生 `.pth`，不转 GGUF）：

```json
{
  "kind": "local_custom",
  "name": "我的模型",
  "description": "说明文字",
  "ckpt_path": "../../training/checkpoints_v2/step_1894.pth",
  "tokenizer_path": "../../training/tokenizer/tokenizer.json",
  "prompt_template": "问：{question}\n答：",
  "max_new_tokens": 40,
  "top_k": 10,
  "temperature": 0.8,
  "device": "cpu"
}
```

Qwen + LoRA：

```json
{
  "kind": "hf_qwen_lora",
  "name": "Qwen2.5-1.5B + LoRA",
  "base_model_path": "../models/Qwen--Qwen2.5-1.5B/snapshots/master",
  "lora_path": "../qwen-lora-wukong",
  "prompt_format": "raw_completion",
  "prepend_text": "",
  "max_new_tokens": 160,
  "temperature": 0.0,
  "top_p": 0.9,
  "device": "cpu"
}
```

要点：

- `prompt_format` 为 `chat` 时走 chat template，**仅 Instruct 基座可用**；基座模型必须用 `raw_completion` 裸续写，否则会输出生僻字乱码。
- 小数据量 LoRA 建议 `temperature: 0`（贪婪解码），输出更稳定。
- 远端模型只需在 `.env` 的 `REMOTE_MODELS_JSON` 中追加一条 OpenAI 兼容配置。

---

## 主要接口

| 方法 | 路径 | 说明 |
| --- | --- | --- |
| POST | `/api/auth/register` | 注册 |
| POST | `/api/auth/login` | 登录，返回 JWT |
| GET / PUT | `/api/users/me` | 查询 / 修改个人信息 |
| PUT | `/api/users/me/password` | 修改密码 |
| GET / POST | `/api/conversations` | 会话列表 / 新建 |
| PATCH / DELETE | `/api/conversations/{id}` | 重命名、切换模型 / 删除 |
| GET / POST | `/api/conversations/{id}/messages` | 历史消息 / 发送消息 |
| GET | `/api/models` | 模型列表与状态 |
| POST | `/api/models/refresh` | 重新扫描模型目录 |
| POST | `/api/models/{key}/load` | 预加载指定模型 |

统一响应结构与错误码见 [docs/API设计.md](docs/API设计.md)。

---

## 训练（可选）

```bash
cd training
python train_tokenizer.py     # 训练 tokenizer
python train.py               # 预训练
python sft_train.py           # 全量 SFT
python lora.py                # LoRA 微调（自研 GPT）
python sft_qwen_lora.py       # Qwen LoRA（GPU 环境）
```

SFT 数据格式为逐行 JSON：`{"question": "...", "answer": "..."}`，见 `training/data/`。

---

## 已知限制

- 自研 GPT 参数量与语料都很小（文本约 4.5MB），只会机械续写，回复质量有限，主要用于验证"本地训练模型成功接入"。
- Qwen 基座为续写模型，且 LoRA 仅用约 20 条语料训练，只能回答语料覆盖范围内的问题，超出范围会自由续写。
- 本地模型在 CPU 上推理，首次调用需加载权重（Qwen2.5-1.5B 约 80 秒），之后走进程内缓存。
- 暂未实现流式输出、Markdown 渲染、消息重试，规划在 V2。

---

## 文档

- [PRD](docs/PRD.md)
- [技术方案](docs/技术方案.md)
- [API 设计](docs/API设计.md)
