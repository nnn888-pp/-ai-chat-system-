<template>
  <div class="chat-page">
    <!-- 左侧会话栏 -->
    <aside class="sidebar">
      <div class="brand">
        <span class="logo">AI</span>
        <div>
          <div class="brand-name">AI 对话</div>
          <div class="brand-sub">多模型聊天</div>
        </div>
      </div>

      <button class="btn btn-primary new-chat" type="button" @click="createConversation">
        ＋ 新建对话
      </button>

      <div class="conv-scroll">
        <div v-if="!conversations.length" class="conv-empty">
          还没有对话，<br />从右上角新建一个吧。
        </div>
        <button
          v-for="conv in conversations"
          :key="conv.id"
          class="conv-item"
          :class="{ active: conv.id === currentId }"
          type="button"
          @click="selectConversation(conv.id)"
        >
          <span class="conv-title">{{ conv.title }}</span>
          <span class="conv-meta">{{ modelShort(conv.model_key) }}</span>
          <span class="conv-preview">{{ conv.last_message || '暂无消息' }}</span>
          <span class="conv-actions" @click.stop>
            <button class="icon-btn" type="button" title="重命名" @click="openRename(conv)">
              改
            </button>
            <button class="icon-btn danger" type="button" title="删除" @click="openDelete(conv)">
              删
            </button>
          </span>
        </button>
      </div>

      <div class="user-block">
        <div class="avatar">{{ (store.user?.nickname || '?').slice(0, 1) }}</div>
        <div class="user-info">
          <div class="user-name">{{ store.user?.nickname || '未登录' }}</div>
          <div class="user-handle">@{{ store.user?.username }}</div>
        </div>
        <button class="btn btn-ghost btn-sm" type="button" @click="goProfile">设置</button>
      </div>
    </aside>

    <!-- 右侧对话区 -->
    <main class="main">
      <header class="chat-header">
        <div class="header-left">
          <h2>{{ currentConv?.title || '未选择对话' }}</h2>
          <span v-if="currentConv" class="header-sub">
            共 {{ messages.length }} 条消息
          </span>
        </div>

        <div class="header-right">
          <label class="model-picker">
            <span class="model-label">模型</span>
            <select v-model="selectedModel" class="model-select" :disabled="sending" @change="onModelChange">
              <option v-if="!models.length" value="">无可用模型</option>
              <option v-for="m in models" :key="m.key" :value="m.key">
                {{ m.name }}（{{ modelKindText(m.kind) }}）
              </option>
            </select>
          </label>
          <span v-if="modelMeta" class="status-dot" :class="modelMeta.status" :title="modelStatusText(modelMeta)">
            {{ modelStatusText(modelMeta) }}
          </span>
          <button
            v-if="currentConv && messages.length"
            class="btn btn-ghost btn-sm"
            type="button"
            :disabled="sending"
            @click="openClear"
          >
            清空消息
          </button>
          <button class="btn btn-ghost btn-sm" type="button" @click="refreshAll" :disabled="loadingModels">
            刷新模型
          </button>
        </div>
      </header>

      <div v-if="error" class="alert alert-error chat-alert">{{ error }}</div>

      <section ref="scrollBox" class="messages">
        <div v-if="!currentConv" class="placeholder">
          <h3>选一个对话，或新建一个</h3>
          <p>支持本地训练的 pt 模型与远端大模型，随时切换。</p>
        </div>

        <div v-else-if="!messages.length && !loadingMessages" class="placeholder">
          <h3>纸已铺好，落笔吧</h3>
          <p>当前模型：{{ selectedModelName }}</p>
          <div class="chips">
            <button
              v-for="chip in suggestions"
              :key="chip"
              class="chip"
              type="button"
              @click="useSuggestion(chip)"
            >
              {{ chip }}
            </button>
          </div>
        </div>

        <template v-else>
          <div v-if="loadingMessages" class="loading-line">正在载入消息…</div>
          <div
            v-for="msg in messages"
            :key="msg.id"
            class="bubble-row"
            :class="msg.role"
          >
            <div class="bubble">
              <div class="bubble-role">
                {{ msg.role === 'user' ? '我' : modelShort(msg.model_key || selectedModel) }}
              </div>
              <div class="bubble-text">{{ msg.content }}</div>
              <button
                v-if="msg.role === 'assistant' && msg.status !== 'error'"
                class="copy-btn"
                type="button"
                @click="copyText(msg, $event)"
              >
                复制
              </button>
            </div>
          </div>
          <div v-if="sending" class="bubble-row assistant">
            <div class="bubble typing">
              <div class="bubble-role">{{ modelShort(selectedModel) }}</div>
              <div class="dots"><span></span><span></span><span></span></div>
            </div>
          </div>
        </template>
      </section>

      <footer class="composer">
        <textarea
          v-model="input"
          class="textarea"
          rows="2"
          placeholder="输入消息，Enter 发送，Shift + Enter 换行"
          :disabled="sending || !models.length"
          @keydown.enter="handleEnter"
        ></textarea>
        <div class="composer-side">
          <span class="composer-hint">
            {{ selectedModelName }}
          </span>
          <button
            class="btn btn-primary"
            type="button"
            :disabled="sending || !input.trim() || !models.length"
            @click="send"
          >
            {{ sending ? '生成中' : '发送' }}
          </button>
        </div>
      </footer>
    </main>

    <!-- 重命名弹窗 -->
    <div v-if="modal?.type === 'rename'" class="modal-mask" @click.self="closeModal">
      <div class="modal">
        <h3>重命名对话</h3>
        <input v-model.trim="modal.text" class="input" maxlength="100" @keydown.enter="confirmRename" />
        <div class="modal-actions">
          <button class="btn btn-sm" type="button" @click="closeModal">取消</button>
          <button class="btn btn-primary btn-sm" type="button" @click="confirmRename">保存</button>
        </div>
      </div>
    </div>

    <!-- 删除确认 -->
    <div v-if="modal?.type === 'delete'" class="modal-mask" @click.self="closeModal">
      <div class="modal">
        <h3>删除对话</h3>
        <p class="modal-text">
          确定删除「{{ modal.conv.title }}」？该对话下的消息会一并清除，无法恢复。
        </p>
        <div class="modal-actions">
          <button class="btn btn-sm" type="button" @click="closeModal">取消</button>
          <button class="btn btn-primary btn-sm" type="button" @click="confirmDelete">删除</button>
        </div>
      </div>
    </div>

    <!-- 清空消息确认 -->
    <div v-if="modal?.type === 'clear'" class="modal-mask" @click.self="closeModal">
      <div class="modal">
        <h3>清空消息</h3>
        <p class="modal-text">将删除当前对话的全部消息，对话本身保留。</p>
        <div class="modal-actions">
          <button class="btn btn-sm" type="button" @click="closeModal">取消</button>
          <button class="btn btn-primary btn-sm" type="button" @click="confirmClear">清空</button>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { computed, nextTick, onMounted, ref } from 'vue'
import { useRouter } from 'vue-router'
import { api } from '../api'
import { store } from '../store'

const router = useRouter()

const models = ref([])
const conversations = ref([])
const currentId = ref(null)
const messages = ref([])
const selectedModel = ref('')
const input = ref('')
const sending = ref(false)
const loadingModels = ref(false)
const loadingMessages = ref(false)
const error = ref('')
const modal = ref(null)
const scrollBox = ref(null)

const suggestions = ['你是谁', '水的沸点是多少', '讲个故事']

const currentConv = computed(() => conversations.value.find((c) => c.id === currentId.value) || null)
const modelMeta = computed(() => models.value.find((m) => m.key === selectedModel.value) || null)
const selectedModelName = computed(() => modelMeta.value?.name || '未选择模型')

function modelShort(key) {
  if (!key) return '模型'
  const m = models.value.find((x) => x.key === key)
  return m ? m.name : key.replace(/^local:/, '').replace(/^remote:/, '')
}

function modelKindText(kind) {
  return kind === 'remote' ? '远端' : '本地'
}

function modelStatusText(meta) {
  const map = { ready: '就绪', unloaded: '待加载', loading: '加载中', failed: '异常' }
  return map[meta.status] || meta.status
}

function goProfile() {
  router.push({ name: 'profile' })
}

function handleEnter(e) {
  if (e.shiftKey) return
  e.preventDefault()
  send()
}

function copyFallback(text) {
  const ta = document.createElement('textarea')
  ta.value = text
  ta.style.position = 'fixed'
  ta.style.opacity = '0'
  document.body.appendChild(ta)
  ta.select()
  const ok = document.execCommand('copy')
  document.body.removeChild(ta)
  return ok
}

async function copyText(msg, e) {
  let ok = false
  try {
    ok = copyFallback(msg.content)
  } catch {
    ok = false
  }
  if (!ok) {
    setError(new Error('复制失败，请手动选中文字'))
    return
  }

  const btn = e?.currentTarget
  if (btn) {
    btn.textContent = '已复制'
    setTimeout(() => {
      btn.textContent = '复制'
    }, 2000)
  }
}

function useSuggestion(text) {
  input.value = text
  send()
}

function setError(e) {
  error.value = e?.message || String(e)
  setTimeout(() => {
    if (error.value) error.value = ''
  }, 8000)
}

async function scrollToBottom() {
  await nextTick()
  const el = scrollBox.value
  if (el) el.scrollTop = el.scrollHeight
}

async function loadModels() {
  loadingModels.value = true
  try {
    const data = await api.listModels()
    models.value = data.list || []
    if (!models.value.some((m) => m.key === selectedModel.value)) {
      selectedModel.value = models.value[0]?.key || ''
    }
  } catch (e) {
    setError(e)
  } finally {
    loadingModels.value = false
  }
}

async function loadConversations() {
  try {
    const data = await api.listConversations()
    conversations.value = data.list || []
    if (!conversations.value.some((c) => c.id === currentId.value)) {
      currentId.value = conversations.value[0]?.id ?? null
      if (currentId.value) await loadMessages(currentId.value)
    }
  } catch (e) {
    setError(e)
  }
}

async function loadMessages(id) {
  loadingMessages.value = true
  messages.value = []
  try {
    const data = await api.listMessages(id)
    messages.value = data.list || []
    scrollToBottom()
  } catch (e) {
    setError(e)
  } finally {
    loadingMessages.value = false
  }
}

async function selectConversation(id) {
  if (id === currentId.value) return
  currentId.value = id
  const conv = conversations.value.find((c) => c.id === id)
  if (conv?.model_key) selectedModel.value = conv.model_key
  await loadMessages(id)
}

async function createConversation() {
  if (!models.value.length) {
    setError('没有可用模型，请检查后端 models_store 目录')
    return
  }
  if (!selectedModel.value) selectedModel.value = models.value[0].key
  try {
    const conv = await api.createConversation({
      title: '新对话',
      model_key: selectedModel.value,
    })
    conversations.value.unshift({
      id: conv.id,
      title: conv.title,
      model_key: conv.model_key,
      last_message: null,
      updated_at: conv.updated_at,
    })
    currentId.value = conv.id
    messages.value = []
    input.value = ''
  } catch (e) {
    setError(e)
  }
}

async function onModelChange() {
  const conv = currentConv.value
  if (!conv) return
  try {
    await api.updateConversation(conv.id, { model_key: selectedModel.value })
    conv.model_key = selectedModel.value
  } catch (e) {
    setError(e)
  }
}

async function refreshAll() {
  await loadModels()
  await loadConversations()
}

function openRename(conv) {
  modal.value = { type: 'rename', conv, text: conv.title }
}

function openDelete(conv) {
  modal.value = { type: 'delete', conv }
}

function openClear() {
  modal.value = { type: 'clear' }
}

function closeModal() {
  modal.value = null
}

async function confirmRename() {
  if (!modal.value) return
  const { conv, text } = modal.value
  if (!text) {
    setError('标题不能为空')
    return
  }
  try {
    const updated = await api.updateConversation(conv.id, { title: text })
    conv.title = updated.title
    closeModal()
  } catch (e) {
    setError(e)
  }
}

async function confirmDelete() {
  if (!modal.value) return
  const conv = modal.value.conv
  try {
    await api.deleteConversation(conv.id)
    conversations.value = conversations.value.filter((c) => c.id !== conv.id)
    if (currentId.value === conv.id) {
      currentId.value = conversations.value[0]?.id ?? null
      messages.value = []
      if (currentId.value) await loadMessages(currentId.value)
    }
    closeModal()
  } catch (e) {
    setError(e)
  }
}

async function confirmClear() {
  if (!currentConv.value) return
  try {
    await api.clearMessages(currentConv.value.id)
    messages.value = []
    currentConv.value.last_message = null
    closeModal()
  } catch (e) {
    setError(e)
  }
}

async function send() {
  const text = input.value.trim()
  if (!text || sending.value || !models.value.length) return

  error.value = ''
  if (!currentConv.value) {
    await createConversation()
    if (!currentConv.value) return
  }

  const conv = currentConv.value
  const tempId = `tmp-${Date.now()}`
  messages.value.push({
    id: tempId,
    role: 'user',
    content: text,
    model_key: null,
    status: 'ok',
    created_at: new Date().toISOString(),
  })
  input.value = ''
  sending.value = true
  scrollToBottom()

  try {
    const data = await api.sendMessage(conv.id, { content: text, model_key: selectedModel.value })
    const idx = messages.value.findIndex((m) => m.id === tempId)
    if (idx >= 0) messages.value.splice(idx, 1, data.user_message)
    messages.value.push(data.assistant_message)
    conv.last_message = data.assistant_message.content
    conv.model_key = selectedModel.value
    conversations.value.sort((a, b) => (a.id === conv.id ? -1 : b.id === conv.id ? 1 : 0))
    scrollToBottom()
  } catch (e) {
    messages.value = messages.value.filter((m) => m.id !== tempId)
    input.value = text
    setError(e)
  } finally {
    sending.value = false
    scrollToBottom()
  }
}

onMounted(async () => {
  await loadModels()
  await loadConversations()
})
</script>

<style scoped>
.chat-page {
  display: flex;
  height: 100%;
  overflow: hidden;
}

/* ========== 侧栏 ========== */
.sidebar {
  width: 272px;
  flex-shrink: 0;
  display: flex;
  flex-direction: column;
  background: #fdf7f9;
  border-right: 1px solid var(--border);
  padding: 18px 14px 12px;
}

.brand {
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 0 6px 16px;
}

.logo {
  width: 32px;
  height: 32px;
  border-radius: 8px;
  background: linear-gradient(135deg, #e1739f 0%, #c94a7c 100%);
  color: #fff;
  font-size: 12px;
  font-weight: 700;
  display: flex;
  align-items: center;
  justify-content: center;
  flex-shrink: 0;
}

.brand-name {
  font-size: 15px;
  font-weight: 600;
  letter-spacing: 0.02em;
}

.brand-sub {
  font-size: 11px;
  color: var(--text-3);
}

.new-chat {
  width: 100%;
  margin-bottom: 14px;
}

.conv-scroll {
  flex: 1;
  overflow-y: auto;
  display: flex;
  flex-direction: column;
  gap: 6px;
  padding-right: 2px;
}

.conv-empty {
  padding: 28px 12px;
  font-size: 12px;
  line-height: 1.9;
  color: var(--text-3);
  text-align: center;
}

.conv-item {
  position: relative;
  display: grid;
  grid-template-columns: 1fr auto;
  grid-template-areas:
    'title meta'
    'preview preview';
  gap: 3px 8px;
  padding: 10px 12px;
  border-radius: 10px;
  border: 1px solid transparent;
  background: transparent;
  text-align: left;
  transition: all 0.16s ease;
}

.conv-item:hover {
  background: rgba(255, 255, 255, 0.9);
  border-color: var(--border);
}

.conv-item.active {
  background: var(--surface);
  border-color: rgba(209, 86, 138, 0.25);
  box-shadow: var(--shadow-sm);
}

.conv-title {
  grid-area: title;
  font-size: 13.5px;
  font-weight: 500;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.conv-meta {
  grid-area: meta;
  font-size: 10px;
  color: var(--text-3);
  max-width: 92px;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.conv-preview {
  grid-area: preview;
  font-size: 11.5px;
  color: var(--text-3);
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.conv-actions {
  position: absolute;
  right: 6px;
  bottom: 6px;
  display: none;
  gap: 4px;
  background: var(--surface);
  border-radius: 8px;
  padding: 2px;
  box-shadow: var(--shadow-sm);
}

.conv-item:hover .conv-actions,
.conv-item.active .conv-actions {
  display: flex;
}

.icon-btn {
  border: none;
  background: transparent;
  font-size: 11px;
  color: var(--text-2);
  padding: 3px 6px;
  border-radius: 6px;
}

.icon-btn:hover {
  background: rgba(209, 86, 138, 0.1);
  color: var(--primary);
}

.icon-btn.danger:hover {
  background: rgba(201, 74, 85, 0.12);
  color: #b23a45;
}

.user-block {
  display: flex;
  align-items: center;
  gap: 9px;
  padding: 10px 8px 4px;
  margin-top: 10px;
  border-top: 1px solid var(--border);
}

.avatar {
  width: 32px;
  height: 32px;
  border-radius: 50%;
  background: rgba(209, 86, 138, 0.12);
  color: var(--primary);
  font-family: var(--font-ui);
  display: flex;
  align-items: center;
  justify-content: center;
  flex-shrink: 0;
}

.user-info {
  flex: 1;
  min-width: 0;
}

.user-name {
  font-size: 13px;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.user-handle {
  font-size: 10.5px;
  color: var(--text-3);
}

/* ========== 主区 ========== */
.main {
  position: relative;
  flex: 1;
  min-width: 0;
  display: flex;
  flex-direction: column;
  background:
    radial-gradient(900px 380px at 88% -12%, rgba(209, 86, 138, 0.07), transparent 62%),
    var(--bg);
  overflow: hidden;
}

.chat-header {
  position: relative;
  z-index: 1;
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 16px;
  padding: 14px 24px;
  border-bottom: 1px solid var(--border);
  background: rgba(255, 251, 253, 0.78);
  backdrop-filter: blur(6px);
}

.header-left h2 {
  margin: 0;
  font-family: var(--font-ui);
  font-size: 17px;
  font-weight: 600;
  letter-spacing: 0.04em;
}

.header-sub {
  font-size: 11px;
  color: var(--text-3);
}

.header-right {
  display: flex;
  align-items: center;
  gap: 10px;
  flex-wrap: wrap;
}

.model-picker {
  display: flex;
  align-items: center;
  gap: 7px;
}

.model-label {
  font-size: 12px;
  color: var(--text-2);
}

.model-select {
  max-width: 210px;
  padding: 7px 10px;
  border-radius: 9px;
  border: 1px solid var(--border);
  background: var(--surface);
  outline: none;
}

.model-select:focus {
  border-color: rgba(209, 86, 138, 0.45);
}

.status-dot {
  font-size: 11px;
  padding: 2px 8px;
  border-radius: 999px;
  border: 1px solid var(--border);
  color: var(--text-2);
}

.status-dot.ready {
  border-color: rgba(93, 139, 87, 0.4);
  color: #4c7a47;
  background: rgba(93, 139, 87, 0.08);
}

.status-dot.unloaded {
  border-color: rgba(184, 137, 74, 0.4);
  color: #8a6528;
  background: rgba(184, 137, 74, 0.08);
}

.status-dot.loading {
  border-color: rgba(184, 137, 74, 0.4);
  color: #8a6528;
}

.status-dot.failed {
  border-color: rgba(201, 74, 85, 0.4);
  color: #b23a45;
  background: rgba(201, 74, 85, 0.08);
}

.chat-alert {
  margin: 12px 24px 0;
}

.messages {
  position: relative;
  z-index: 1;
  flex: 1;
  overflow-y: auto;
  padding: 26px 28px 18px;
  display: flex;
  flex-direction: column;
  gap: 16px;
}

.placeholder {
  position: relative;
  margin: auto;
  text-align: center;
  padding: 40px 20px;
}

.placeholder h3 {
  font-family: var(--font-ui);
  font-size: 20px;
  letter-spacing: 0.1em;
  margin: 0 0 8px;
}

.placeholder p {
  margin: 0;
  font-size: 12.5px;
  color: var(--text-3);
}

.chips {
  display: flex;
  gap: 8px;
  justify-content: center;
  flex-wrap: wrap;
  margin-top: 18px;
}

.chip {
  padding: 7px 14px;
  border-radius: 999px;
  border: 1px solid var(--border);
  background: var(--surface);
  font-size: 12.5px;
  color: var(--text-2);
  transition: all 0.16s;
}

.chip:hover {
  border-color: rgba(209, 86, 138, 0.35);
  color: var(--primary);
}

.loading-line {
  text-align: center;
  font-size: 12px;
  color: var(--text-3);
}

.bubble-row {
  display: flex;
}

.bubble-row.user {
  justify-content: flex-end;
}

.bubble {
  max-width: min(72%, 720px);
  padding: 11px 15px;
  border-radius: 14px;
  background: var(--surface);
  border: 1px solid var(--border);
  box-shadow: var(--shadow-sm);
}

.bubble-row.user .bubble {
  background: rgba(209, 86, 138, 0.09);
  border-color: rgba(209, 86, 138, 0.22);
  border-bottom-right-radius: 4px;
}

.bubble-row.assistant .bubble {
  border-bottom-left-radius: 4px;
}

.bubble-role {
  font-size: 10.5px;
  color: var(--text-3);
  margin-bottom: 5px;
  letter-spacing: 0.04em;
}

.copy-btn {
  display: block;
  margin-top: 6px;
  padding: 2px 7px;
  border: none;
  border-radius: 6px;
  background: transparent;
  color: var(--text-3);
  font-size: 11px;
  opacity: 0;
  transition: opacity 0.16s ease, color 0.16s ease, background 0.16s ease;
}

.bubble-row:hover .copy-btn {
  opacity: 1;
}

.copy-btn:hover {
  color: var(--primary);
  background: rgba(209, 86, 138, 0.08);
}

.bubble-text {
  font-size: 14px;
  line-height: 1.8;
  white-space: pre-wrap;
  word-break: break-word;
}

.typing .dots {
  display: flex;
  gap: 4px;
  padding: 4px 0 2px;
}

.typing .dots span {
  width: 6px;
  height: 6px;
  border-radius: 50%;
  background: var(--primary-soft);
  animation: blink 1.2s infinite ease-in-out;
}

.typing .dots span:nth-child(2) {
  animation-delay: 0.15s;
}

.typing .dots span:nth-child(3) {
  animation-delay: 0.3s;
}

@keyframes blink {
  0%, 80%, 100% { opacity: 0.25; transform: translateY(0); }
  40% { opacity: 1; transform: translateY(-2px); }
}

.composer {
  position: relative;
  z-index: 1;
  display: flex;
  gap: 12px;
  align-items: flex-end;
  padding: 14px 24px 18px;
  border-top: 1px solid var(--border);
  background: rgba(255, 255, 255, 0.8);
  backdrop-filter: blur(6px);
}

.composer .textarea {
  flex: 1;
  min-height: 52px;
  max-height: 150px;
  line-height: 1.6;
}

.composer-side {
  display: flex;
  flex-direction: column;
  align-items: flex-end;
  gap: 6px;
}

.composer-hint {
  font-size: 10.5px;
  color: var(--text-3);
  max-width: 150px;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.modal-text {
  font-size: 13px;
  line-height: 1.8;
  color: var(--text-2);
  margin: 0;
}

@media (max-width: 900px) {
  .sidebar {
    width: 220px;
  }

  .header-right {
    gap: 6px;
  }

  .model-select {
    max-width: 150px;
  }
}
</style>
