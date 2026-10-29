# Agent.md — AI 聊天对话系统开发约定

## 项目定位
本地化 AI 聊天系统：Vue 3 + Vite 前端，FastAPI 后端，支持远端第三方大模型与本地训练模型（原生 `.pt` / LoRA，不转 GGUF）。

## 必读文档（改代码前先看）
- `docs/PRD.md`：需求与验收标准，功能范围以它为准
- `docs/技术方案.md`：架构、目录、数据库、模型适配层
- `docs/API设计.md`：接口契约，前后端字段以它为准，不得自行改字段名

## 技术栈约束
- 前端只能是 Vue 3（Composition API + `<script setup>`），不得换成 React
- 后端只能是 Python + FastAPI，因为要直接用 transformers 加载 `.pt`
- 数据库通过 SQLAlchemy 访问；开发用 SQLite，切 MySQL 只改 `DATABASE_URL`
- 自己的训练模型禁止用 Ollama / llama.cpp 加载；Ollama 只用于 V2 接入第三方开源模型

## 开发顺序
后端优先：鉴权 → 会话 → 消息 → 模型适配 → 前端联调。每完成一个模块立即用 curl / Swagger 验证再往下做。

## 编码规范
- 分层：`api`（路由与参数校验）→ `services`（业务）→ `models`（ORM），路由里不写业务逻辑，也不直接拼 SQL
- 所有涉及会话/消息的查询必须带 `user_id` 条件，不允许只按 id 查
- 密码：入库只用 bcrypt 哈希，任何日志不得打印密码或 token
- 远端模型 API Key 只从环境变量读取，响应中必须脱敏
- 模型调用统一走 `providers/base.py` 抽象，新增模型不修改 `chat_service`
- 错误统一抛业务异常并映射到 `API设计.md` 的 code 表，不把 Python 堆栈返回给前端

## 本地模型接入约定
- 模型目录：`backend/models_store/<key>/`，必须有 `model_config.json`
- 配置字段：`name / type(full|lora) / base_model / adapter_path / tokenizer_dir / device / max_new_tokens / temperature`
- 首次调用懒加载，进程内单例缓存，同 provider 生成加锁
- 加载失败只标记 `failed` 并记录原因，不得让进程退出
- 写系统接入代码前，先保证 `scripts/local_model_demo.py` 能在命令行独立跑通

## 常用命令
```bash
# 后端
cd backend && python -m venv .venv && .venv\Scripts\activate
pip install -r requirements.txt
uvicorn app.main:app --reload --port 8000

# 前端
cd frontend && npm install && npm run dev   # http://localhost:5173
```

## 禁止事项
- 不实现 PRD 中"明确排除"的功能（RAG、文件上传、管理后台、计费、移动端适配）
- 不引入未在技术方案中列出的重型依赖（如 Celery、Redis、Docker 编排）
- 不修改已定稿的接口路径与字段名；确需变更时先改 `docs/API设计.md`
- 不在前端硬编码 API Key 或后端地址以外的敏感信息
- 不提交 `.env`、模型权重文件、`node_modules`、`__pycache__`

## Git 约定
- 初始化后先提交一次保底版本
- 每个可运行模块单独提交，提交信息用中文，说明"做了什么 + 为什么"
- 改坏时优先回退到上一个可运行提交，不在错误方向上反复修补
