# AI 聊天对话系统 API 设计

| 项 | 值 |
| --- | --- |
| 版本 | v1.1（实现后同步） |
| Base URL（开发） | `http://127.0.0.1:8000/api` |
| 内容类型 | `application/json; charset=utf-8` |
| 鉴权 | `Authorization: Bearer <JWT>`（除注册/登录外全部必填） |
| 在线文档 | `http://127.0.0.1:8000/docs`（FastAPI 自动生成） |

## 1. 通用约定

### 1.1 成功响应

```json
{
  "code": 0,
  "message": "ok",
  "data": {}
}
```

### 1.2 失败响应

```json
{
  "code": 1002,
  "message": "用户名或密码错误",
  "data": null
}
```

> HTTP 状态码同时保持语义（401/403/404/422/500），`code` 为业务码，前端以 `code !== 0` 判断失败。

### 1.3 业务码表

| code | HTTP | 含义 |
| --- | --- | --- |
| 0 | 200 | 成功 |
| 1001 | 422 | 参数校验失败 |
| 1002 | 401 | 用户名或密码错误 |
| 1003 | 401 | 未登录 / token 失效 |
| 1004 | 403 | 无权访问该资源 |
| 1005 | 409 | 用户名已存在 |
| 1006 | 400 | 原密码错误 |
| 1007 | 404 | 资源不存在 |
| 2001 | 502 | 模型调用失败（远端） |
| 2002 | 500 | 模型加载失败（本地） |
| 2003 | 409 | 模型正忙，请稍后 |
| 2004 | 404 | 模型不存在或未加载 |

## 2. 鉴权模块

### 2.1 注册 `POST /auth/register`

请求：

```json
{ "username": "alice", "password": "123456", "nickname": "爱丽丝" }
```

响应 `data`：

```json
{ "id": 1, "username": "alice", "nickname": "爱丽丝" }
```

失败：`1005` 用户名已存在；密码少于 6 位返回 `1001`。

### 2.2 登录 `POST /auth/login`

请求（`password` 为前端 SHA-256 后的十六进制串）：

```json
{ "username": "alice", "password": "8d969eef6ecad3c29a3a629280e686cf0c3f5d5a86aff3ca12020c923adc6c92" }
```

响应 `data`：

```json
{
  "token": "eyJhbGciOiJIUzI1NiIs...",
  "user": { "id": 1, "username": "alice", "nickname": "爱丽丝", "avatar": "#D1568A" }
}
```

失败：`1002`。

### 2.3 退出 `POST /auth/logout`

无请求体。前端清除本地 token 即可，后端返回 `{"code":0,"data":null}`。

## 3. 用户模块

### 3.1 获取当前用户 `GET /users/me`

响应 `data`：

```json
{
  "id": 1,
  "username": "alice",
  "nickname": "爱丽丝",
  "email": "a@b.com",
  "avatar": "#D1568A",
  "created_at": "2026-10-28T10:00:00"
}
```

### 3.2 修改个人信息 `PUT /users/me`

请求（字段均可选，只传要改的）：

```json
{ "nickname": "Alice", "email": "alice@x.com", "avatar": "#FF8A65" }
```

响应：同 `GET /users/me`。`username` 不允许修改。

### 3.3 修改密码 `PUT /users/me/password`

请求：

```json
{ "old_password": "<sha256>", "new_password": "<sha256>" }
```

响应 `data`：`null`。失败：`1006` 原密码错误；新旧相同返回 `1001`。

## 4. 会话模块

### 4.1 会话列表 `GET /conversations`

响应 `data`：

```json
{
  "list": [
    {
      "id": 12,
      "title": "关于 LoRA 微调的问题",
      "model_key": "local:qwen-lora-wukong",
      "last_message": "LoRA 是一种低秩适配方法……",
      "updated_at": "2026-10-28T15:30:00"
    }
  ]
}
```

按 `updated_at` 倒序，只返回当前用户的数据。

### 4.2 新建会话 `POST /conversations`

请求：

```json
{ "title": "新对话", "model_key": "remote:deepseek-chat" }
```

响应 `data`：完整会话对象（含 `id`、`created_at`）。

### 4.3 会话详情 `GET /conversations/{id}`

响应 `data`：会话对象。不存在或非本人返回 `1004`/`1007`。

### 4.4 重命名 `PATCH /conversations/{id}`

请求：

```json
{ "title": "新标题" }
```

响应 `data`：更新后的会话对象。标题为空或超 50 字返回 `1001`。

### 4.5 切换模型 `PATCH /conversations/{id}`

同一接口，请求体：

```json
{ "model_key": "local:qwen-lora-wukong" }
```

`title` 与 `model_key` 可同时提交。

### 4.6 删除会话 `DELETE /conversations/{id}`

删除会话及其全部消息，响应 `data`：`null`。

> 表间未声明外键级联，服务层**显式删除**该会话的消息后再删会话。否则 SQLite 会复用被删会话的自增 id，新会话可能"继承"旧会话的孤儿消息。

### 4.7 清空消息 `DELETE /conversations/{id}/messages`

保留会话本身，删除全部消息。响应 `data`：`null`。

## 5. 消息模块

### 5.1 消息历史 `GET /conversations/{id}/messages`

查询参数：`limit`（默认 50，最大 200）、`before_id`（分页用，可选）。

响应 `data`：

```json
{
  "list": [
    { "id": 101, "role": "user", "content": "你好", "model_key": null, "status": "ok", "created_at": "..." },
    { "id": 102, "role": "assistant", "content": "你好，有什么可以帮你？", "model_key": "local:qwen-lora-wukong", "status": "ok", "created_at": "..." }
  ]
}
```

按 `created_at` 升序返回。

### 5.2 发送消息 `POST /conversations/{id}/messages`

请求：

```json
{ "content": "介绍一下 LoRA", "model_key": "local:qwen-lora-wukong" }
```

`model_key` 可省略，省略时使用会话当前模型。

响应 `data`（同步返回，V1 无流式）：

```json
{
  "user_message": { "id": 101, "role": "user", "content": "介绍一下 LoRA", "status": "ok", "created_at": "..." },
  "assistant_message": { "id": 102, "role": "assistant", "content": "LoRA……", "model_key": "local:qwen-lora-wukong", "status": "ok", "created_at": "..." }
}
```

失败语义：
- 模型不存在 → `2004`
- 远端报错/超时 → `2001`，但**用户消息已落库**，并写入一条 `status=error` 的 assistant 消息
- 本地模型加载失败 → `2002`
- 同一本地模型正在生成 → `2003`

### 5.3 重试 `POST /messages/{id}/retry`（V2）

以该失败消息之前的上下文重新生成，返回新的 assistant 消息。

## 6. 模型模块

### 6.1 模型列表 `GET /models`

响应 `data`：

```json
{
  "list": [
    {
      "key": "remote:deepseek-chat",
      "name": "DeepSeek V3（远端）",
      "kind": "remote",
      "status": "ready",
      "description": "DeepSeek V3，OpenAI 兼容协议",
      "api_key_masked": "sk-****9d70"
    },
    {
      "key": "local:qwen-lora-wukong",
      "name": "Qwen2.5-1.5B + 孙悟空 LoRA",
      "kind": "local",
      "status": "unloaded",
      "description": "魔塔社区训练的孙悟空风格 LoRA（基座续写式，贪婪解码）",
      "error_msg": null
    }
  ]
}
```

`status` 枚举：`ready` / `unloaded` / `loading` / `failed`。**不返回 API Key 明文与本地绝对路径。**

当前实际接入的模型：

| key | 展示名 | kind |
| --- | --- | --- |
| `remote:deepseek-chat` | DeepSeek V3（远端） | remote |
| `local:pretrain-v2` | 小GPT预训练(三国演义+西游记) | local |
| `local:sft-v2` | 小GPT全量SFT | local |
| `local:lora-v2-wukong` | 小GPT LoRA SFT (孙悟空) | local |
| `local:qwen-base` | Qwen2.5-1.5B（基座） | local |
| `local:qwen-lora-wukong` | Qwen2.5-1.5B + 孙悟空 LoRA | local |

### 6.2 刷新模型 `POST /models/refresh`

重新扫描项目根目录 `models_store/` 与远端配置（`.env` 的 `REMOTE_MODELS_JSON`），返回同 6.1 的列表。

### 6.3 加载本地模型 `POST /models/{key}/load`

主动触发加载（预热），避免首次对话等待。

- 成功：`data.status = "ready"`
- 失败：`2002`，`data.error_msg` 带失败原因
- 已就绪：直接返回 `ready`，不重复加载

### 6.4 卸载本地模型 `POST /models/{key}/unload`（V2）

释放显存。V1 可不实现。

## 7. 前端调用约定

1. `fetch` 封装统一注入 `Authorization`，`code === 1003` 时清 token 并跳 `/login`。
2. 所有请求失败统一弹 `message` 提示，文案直接使用后端 `message`。
3. 登录密码处理顺序：`sha256(明文 + 固定盐)` → 提交（密钥见 `frontend/src/utils/crypto.js`）。
4. 会话切换模型时调 `PATCH /conversations/{id}`，不要在前端本地保存状态后丢失。
5. 发送消息期间禁用输入框并显示"生成中"，收到响应后再恢复。
6. 复制 AI 回复：前端本地完成（`document.execCommand('copy')` 优先，`navigator.clipboard` 兜底），不新增后端接口。
