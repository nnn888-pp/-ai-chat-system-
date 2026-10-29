const TOKEN_KEY = 'chat_token'
const USER_KEY = 'chat_user'

export function getToken() {
  return localStorage.getItem(TOKEN_KEY) || ''
}

export function setToken(token) {
  localStorage.setItem(TOKEN_KEY, token)
}

export function getCachedUser() {
  try {
    return JSON.parse(localStorage.getItem(USER_KEY) || 'null')
  } catch {
    return null
  }
}

export function setCachedUser(user) {
  localStorage.setItem(USER_KEY, JSON.stringify(user || null))
}

export function clearAuth() {
  localStorage.removeItem(TOKEN_KEY)
  localStorage.removeItem(USER_KEY)
}

export class ApiError extends Error {
  constructor(message, code) {
    super(message)
    this.code = code
    this.name = 'ApiError'
  }
}

/**
 * 统一请求：自动带 token、统一解析 { code, message, data }。
 * 业务码非 0 时抛 ApiError；401 时清登录态并回登录页。
 */
export async function request(path, { method = 'GET', body, auth = true } = {}) {
  const headers = {}
  if (body !== undefined) headers['Content-Type'] = 'application/json'
  if (auth) {
    const token = getToken()
    if (token) headers['Authorization'] = `Bearer ${token}`
  }

  let res
  try {
    res = await fetch(`/api${path}`, {
      method,
      headers,
      body: body !== undefined ? JSON.stringify(body) : undefined,
    })
  } catch (e) {
    throw new ApiError('无法连接后端服务，请确认 8000 端口已启动', -1)
  }

  let payload = null
  try {
    payload = await res.json()
  } catch {
    payload = null
  }

  if (res.status === 401 && auth) {
    clearAuth()
    if (window.location.pathname !== '/login') {
      window.location.href = '/login'
    }
  }

  if (!res.ok || !payload || payload.code !== 0) {
    const message = payload?.message || `请求失败（HTTP ${res.status}）`
    throw new ApiError(message, payload?.code ?? res.status)
  }
  return payload.data
}

export const api = {
  register: (data) => request('/auth/register', { method: 'POST', body: data, auth: false }),
  login: (data) => request('/auth/login', { method: 'POST', body: data, auth: false }),
  me: () => request('/users/me'),
  updateMe: (data) => request('/users/me', { method: 'PUT', body: data }),
  changePassword: (data) => request('/users/me/password', { method: 'PUT', body: data }),

  listModels: () => request('/models'),
  refreshModels: () => request('/models/refresh', { method: 'POST' }),

  listConversations: () => request('/conversations'),
  createConversation: (data) => request('/conversations', { method: 'POST', body: data }),
  updateConversation: (id, data) => request(`/conversations/${id}`, { method: 'PATCH', body: data }),
  deleteConversation: (id) => request(`/conversations/${id}`, { method: 'DELETE' }),

  listMessages: (id) => request(`/conversations/${id}/messages`),
  sendMessage: (id, data) => request(`/conversations/${id}/messages`, { method: 'POST', body: data }),
  clearMessages: (id) => request(`/conversations/${id}/messages`, { method: 'DELETE' }),
}
