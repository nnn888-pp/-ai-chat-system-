<template>
  <div class="login-page">
    <div class="login-card">
      <section class="brand-side">
        <div class="logo">AI</div>
        <h1>AI 对话系统</h1>
        <p class="subtitle">多模型 · 本地接入 · 会话管理</p>
        <ul class="feature-list">
          <li>本地训练模型（原生 pt）直接加载</li>
          <li>远端大模型与本地模型自由切换</li>
          <li>会话独立保存，随时继续</li>
          <li>密码 SHA-256 + bcrypt 双层加密</li>
        </ul>
        <p class="footnote">Vue 3 · FastAPI · SQLite / MySQL</p>
      </section>

      <section class="form-side">
        <div class="tabs">
          <button
            class="tab"
            :class="{ active: mode === 'login' }"
            type="button"
            @click="switchMode('login')"
          >
            登录
          </button>
          <button
            class="tab"
            :class="{ active: mode === 'register' }"
            type="button"
            @click="switchMode('register')"
          >
            注册
          </button>
        </div>

        <div v-if="error" class="alert alert-error">{{ error }}</div>
        <div v-if="notice" class="alert alert-ok">{{ notice }}</div>

        <form @submit.prevent="submit">
          <div class="field">
            <label for="username">用户名</label>
            <input
              id="username"
              v-model.trim="form.username"
              class="input"
              autocomplete="username"
              placeholder="请输入用户名"
              required
            />
          </div>

          <div v-if="mode === 'register'" class="field">
            <label for="nickname">昵称</label>
            <input
              id="nickname"
              v-model.trim="form.nickname"
              class="input"
              placeholder="界面中显示的名字"
              required
            />
          </div>

          <div class="field">
            <label for="password">密码</label>
            <input
              id="password"
              v-model="form.password"
              class="input"
              type="password"
              :autocomplete="mode === 'login' ? 'current-password' : 'new-password'"
              placeholder="至少 6 位"
              required
            />
          </div>

          <div v-if="mode === 'register'" class="field">
            <label for="confirm">确认密码</label>
            <input
              id="confirm"
              v-model="form.confirm"
              class="input"
              type="password"
              autocomplete="new-password"
              placeholder="再次输入密码"
              required
            />
          </div>

          <button class="btn btn-primary submit" type="submit" :disabled="loading">
            {{ loading ? '处理中…' : mode === 'login' ? '登录' : '注册' }}
          </button>
        </form>

        <p class="hint">密码在浏览器端先做 SHA-256 摘要再提交，服务端以 bcrypt 存储。</p>
      </section>
    </div>
  </div>
</template>

<script setup>
import { reactive, ref } from 'vue'
import { useRouter } from 'vue-router'
import { api } from '../api'
import { hashPassword } from '../utils/crypto'
import { saveLogin } from '../store'

const router = useRouter()
const mode = ref('login')
const loading = ref(false)
const error = ref('')
const notice = ref('')

const form = reactive({
  username: '',
  nickname: '',
  password: '',
  confirm: '',
})

function switchMode(next) {
  mode.value = next
  error.value = ''
  notice.value = ''
}

async function submit() {
  error.value = ''
  notice.value = ''
  if (!form.username || !form.password) {
    error.value = '请填写用户名与密码'
    return
  }
  if (mode.value === 'register') {
    if (!form.nickname) {
      error.value = '请填写昵称'
      return
    }
    if (form.password.length < 6) {
      error.value = '密码至少 6 位'
      return
    }
    if (form.password !== form.confirm) {
      error.value = '两次输入的密码不一致'
      return
    }
  }

  loading.value = true
  try {
    const hashed = await hashPassword(form.password)
    if (mode.value === 'register') {
      await api.register({
        username: form.username,
        password: hashed,
        nickname: form.nickname,
      })
      notice.value = '注册成功，请登录'
      mode.value = 'login'
      form.password = ''
      form.confirm = ''
    } else {
      const data = await api.login({ username: form.username, password: hashed })
      saveLogin(data.token, data.user)
      router.replace({ name: 'chat' })
    }
  } catch (e) {
    error.value = e.message || '操作失败'
  } finally {
    loading.value = false
  }
}
</script>

<style scoped>
.login-page {
  min-height: 100%;
  display: flex;
  align-items: center;
  justify-content: center;
  padding: 40px 24px;
}

.login-card {
  display: grid;
  grid-template-columns: 330px 390px;
  max-width: 100%;
  background: var(--surface);
  border: 1px solid var(--border);
  border-radius: 16px;
  box-shadow: var(--shadow-md);
  overflow: hidden;
}

.brand-side {
  padding: 44px 34px;
  background:
    radial-gradient(300px 240px at 88% 6%, rgba(231, 138, 176, 0.24), transparent 70%),
    linear-gradient(160deg, #4a2438 0%, #2a1420 100%);
  color: #f7e8ee;
  display: flex;
  flex-direction: column;
}

.logo {
  width: 44px;
  height: 44px;
  border-radius: 11px;
  background: linear-gradient(135deg, #e1739f 0%, #c94a7c 100%);
  color: #fff;
  font-weight: 700;
  font-size: 16px;
  letter-spacing: 0.04em;
  display: flex;
  align-items: center;
  justify-content: center;
  margin-bottom: 24px;
}

.brand-side h1 {
  margin: 0;
  font-size: 26px;
  font-weight: 600;
  letter-spacing: 0.02em;
}

.subtitle {
  margin: 8px 0 30px;
  font-size: 13px;
  color: #d8b3c5;
}

.feature-list {
  list-style: none;
  padding: 0;
  margin: 0;
  font-size: 12.5px;
  line-height: 2.2;
  color: #eed8e2;
}

.feature-list li::before {
  content: '';
  display: inline-block;
  width: 5px;
  height: 5px;
  border-radius: 50%;
  background: var(--primary);
  margin-right: 9px;
  vertical-align: middle;
}

.footnote {
  margin: auto 0 0;
  font-size: 11px;
  color: #b391a1;
}

.form-side {
  padding: 38px 36px 28px;
}

.tabs {
  display: flex;
  gap: 4px;
  margin-bottom: 24px;
  border-bottom: 1px solid var(--border);
}

.tab {
  flex: 1;
  padding: 10px 0;
  background: transparent;
  border: none;
  border-bottom: 2px solid transparent;
  color: var(--text-3);
  font-size: 14.5px;
  margin-bottom: -1px;
  transition: all 0.16s;
}

.tab.active {
  color: var(--primary);
  border-bottom-color: var(--primary);
  font-weight: 500;
}

.submit {
  width: 100%;
  padding: 11px;
  font-size: 15px;
  margin-top: 4px;
}

.hint {
  margin: 16px 0 0;
  font-size: 11.5px;
  color: var(--text-3);
  line-height: 1.7;
}

@media (max-width: 780px) {
  .login-card {
    grid-template-columns: 1fr;
  }

  .brand-side {
    padding: 28px 26px;
  }

  .feature-list,
  .footnote {
    display: none;
  }
}
</style>
