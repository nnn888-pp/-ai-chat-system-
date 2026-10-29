<template>
  <div class="profile-page">
    <header class="topbar">
      <button class="btn btn-ghost btn-sm" type="button" @click="router.push({ name: 'chat' })">
        ← 返回对话
      </button>
      <h1>个人中心</h1>
      <button class="btn btn-ghost btn-sm" type="button" @click="handleLogout">退出登录</button>
    </header>

    <main class="content">
      <section class="card">
        <div class="card-head">
          <div class="avatar-lg">{{ (store.user?.nickname || '?').slice(0, 1) }}</div>
          <div>
            <h2>基本资料</h2>
            <p class="muted">@{{ store.user?.username }} · 注册于 {{ formatDate(profile.created_at) }}</p>
          </div>
        </div>

        <div v-if="infoMsg" class="alert" :class="infoOk ? 'alert-ok' : 'alert-error'">{{ infoMsg }}</div>

        <form @submit.prevent="saveProfile">
          <div class="field">
            <label for="nickname">昵称</label>
            <input id="nickname" v-model.trim="profileForm.nickname" class="input" maxlength="50" required />
          </div>
          <div class="field">
            <label for="email">邮箱</label>
            <input id="email" v-model.trim="profileForm.email" class="input" placeholder="选填" />
          </div>
          <button class="btn btn-primary" type="submit" :disabled="savingProfile">
            {{ savingProfile ? '保存中…' : '保存资料' }}
          </button>
        </form>
      </section>

      <section class="card">
        <div class="card-head">
          <div>
            <h2>修改密码</h2>
            <p class="muted">旧密码与新密码都会先做 SHA-256 摘要再提交，后端 bcrypt 存储。</p>
          </div>
        </div>

        <div v-if="pwdMsg" class="alert" :class="pwdOk ? 'alert-ok' : 'alert-error'">{{ pwdMsg }}</div>

        <form @submit.prevent="savePassword">
          <div class="field">
            <label for="oldpwd">当前密码</label>
            <input id="oldpwd" v-model="pwdForm.old_password" class="input" type="password" autocomplete="current-password" required />
          </div>
          <div class="field">
            <label for="newpwd">新密码</label>
            <input id="newpwd" v-model="pwdForm.new_password" class="input" type="password" autocomplete="new-password" placeholder="至少 6 位" required />
          </div>
          <div class="field">
            <label for="newpwd2">确认新密码</label>
            <input id="newpwd2" v-model="pwdForm.confirm" class="input" type="password" autocomplete="new-password" required />
          </div>
          <button class="btn btn-primary" type="submit" :disabled="savingPwd">
            {{ savingPwd ? '提交中…' : '修改密码' }}
          </button>
        </form>
      </section>
    </main>
  </div>
</template>

<script setup>
import { onMounted, reactive, ref } from 'vue'
import { useRouter } from 'vue-router'
import { api } from '../api'
import { hashPassword } from '../utils/crypto'
import { store, updateUser, logout } from '../store'

const router = useRouter()

const profile = reactive({ created_at: null })
const profileForm = reactive({ nickname: '', email: '' })
const pwdForm = reactive({ old_password: '', new_password: '', confirm: '' })

const savingProfile = ref(false)
const savingPwd = ref(false)
const infoMsg = ref('')
const pwdMsg = ref('')
const infoOk = ref(true)
const pwdOk = ref(true)

function formatDate(value) {
  if (!value) return '—'
  const d = new Date(value)
  if (Number.isNaN(d.getTime())) return '—'
  return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, '0')}-${String(d.getDate()).padStart(2, '0')}`
}

async function loadProfile() {
  try {
    const user = await api.me()
    profile.created_at = user.created_at
    profileForm.nickname = user.nickname
    profileForm.email = user.email || ''
    updateUser(user)
  } catch (e) {
    infoOk.value = false
    infoMsg.value = e.message
  }
}

async function saveProfile() {
  infoMsg.value = ''
  savingProfile.value = true
  try {
    const user = await api.updateMe({
      nickname: profileForm.nickname,
      email: profileForm.email || null,
    })
    updateUser(user)
    profile.created_at = user.created_at
    infoOk.value = true
    infoMsg.value = '资料已更新'
  } catch (e) {
    infoOk.value = false
    infoMsg.value = e.message
  } finally {
    savingProfile.value = false
  }
}

async function savePassword() {
  pwdMsg.value = ''
  if (pwdForm.new_password.length < 6) {
    pwdOk.value = false
    pwdMsg.value = '新密码至少 6 位'
    return
  }
  if (pwdForm.new_password !== pwdForm.confirm) {
    pwdOk.value = false
    pwdMsg.value = '两次输入的新密码不一致'
    return
  }

  savingPwd.value = true
  try {
    const oldHashed = await hashPassword(pwdForm.old_password)
    const newHashed = await hashPassword(pwdForm.new_password)
    await api.changePassword({ old_password: oldHashed, new_password: newHashed })
    pwdOk.value = true
    pwdMsg.value = '密码修改成功，请用新密码重新登录'
    pwdForm.old_password = ''
    pwdForm.new_password = ''
    pwdForm.confirm = ''
    setTimeout(() => handleLogout(), 1800)
  } catch (e) {
    pwdOk.value = false
    pwdMsg.value = e.message
  } finally {
    savingPwd.value = false
  }
}

function handleLogout() {
  logout()
  router.replace({ name: 'login' })
}

onMounted(loadProfile)
</script>

<style scoped>
.profile-page {
  position: relative;
  min-height: 100%;
  overflow: hidden;
  padding: 0 24px 48px;
}

.topbar {
  position: relative;
  z-index: 1;
  display: flex;
  align-items: center;
  justify-content: space-between;
  max-width: 860px;
  margin: 0 auto;
  padding: 18px 0 22px;
}

.topbar h1 {
  margin: 0;
  font-family: var(--font-ui);
  font-size: 20px;
  letter-spacing: 0.14em;
  font-weight: 600;
}

.content {
  position: relative;
  z-index: 1;
  max-width: 860px;
  margin: 0 auto;
  display: grid;
  gap: 20px;
}

.card {
  background: var(--surface);
  border: 1px solid var(--border);
  border-radius: var(--radius);
  box-shadow: var(--shadow-sm);
  padding: 26px 28px;
}

.card-head {
  display: flex;
  align-items: center;
  gap: 14px;
  margin-bottom: 20px;
  padding-bottom: 16px;
  border-bottom: 1px solid var(--border);
}

.card-head h2 {
  margin: 0 0 4px;
  font-family: var(--font-ui);
  font-size: 17px;
  font-weight: 600;
  letter-spacing: 0.06em;
}

.muted {
  margin: 0;
  font-size: 12px;
  color: var(--text-3);
  line-height: 1.6;
}

.avatar-lg {
  width: 52px;
  height: 52px;
  border-radius: 50%;
  background: rgba(209, 86, 138, 0.12);
  color: var(--primary);
  font-family: var(--font-ui);
  font-size: 22px;
  display: flex;
  align-items: center;
  justify-content: center;
  flex-shrink: 0;
}

form {
  max-width: 420px;
}
</style>
